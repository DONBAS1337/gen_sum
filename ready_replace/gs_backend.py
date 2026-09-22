# -*- coding: utf-8 -*-
"""Small Python 2.7/3 ChatGPT subscription client; no Codex installation needed.

Protocol reference: github.com/openai/codex, codex-rs/login/src/server.rs,
login/src/auth/manager.rs, codex-api/src/endpoint/{models,responses}.rs.
This backend is not the public, versioned OpenAI API and may change.
"""
from __future__ import unicode_literals

import base64
import binascii
import calendar
import glob
import hashlib
import hmac
import io
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser

try:
    from urllib.request import Request, build_opener, HTTPRedirectHandler, HTTPSHandler
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode, urlsplit, parse_qs
    from http.server import HTTPServer, BaseHTTPRequestHandler
except ImportError:
    from urllib2 import Request, build_opener, HTTPRedirectHandler, HTTPSHandler, HTTPError, URLError
    from urllib import urlencode
    from urlparse import urlsplit, parse_qs
    from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

# Ren'Py aliases urllib.request on Python 2; imports cannot identify text types.
try:
    text_type = unicode
except NameError:
    text_type = str

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
ISSUER = "https://auth.openai.com"
BACKEND = "https://chatgpt.com/backend-api/codex"
CLIENT_VERSION = "0.154.0"
DEFAULT_MODEL = "gpt-6-astra"
DEFAULT_EFFORT = "low"
NETWORK_TIMEOUT = 60
STREAM_TIMEOUT = 300
LOGIN_TIMEOUT = 300
GENERATION_TIMEOUT = 600
MAX_RESPONSE_BYTES = 8 * 1024 * 1024
MAX_IMAGE_RESPONSE_BYTES = 48 * 1024 * 1024
IMAGE_MODEL = "gpt-image-2.5-flare"


class ClientError(Exception):
    pass


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _claims(token):
    # Only extract routing/expiry hints. The HTTPS backend validates the token.
    if not isinstance(token, text_type):
        return {}
    try:
        payload = token.split(".")[1].encode("ascii")
        result = json.loads(base64.urlsafe_b64decode(payload + b"=" * (-len(payload) % 4)).decode("utf-8"))
        return result if isinstance(result, dict) else {}
    except (ValueError, TypeError, IndexError, UnicodeError):
        return {}


def _valid_token(value):
    return isinstance(value, text_type) and re.match(r"^[!-~]+\Z", value) is not None


def _release_time(model):
    for field in ("release_date", "released_at", "created_at", "created"):
        value = model.get(field)
        try:
            return float(value)
        except (ValueError, TypeError):
            if isinstance(value, text_type):
                try:
                    return calendar.timegm(time.strptime(value[:10], "%Y-%m-%d"))
                except ValueError:
                    pass
    return None


def default_model(models, preferred=None):
    """Honor the user's choice, then Astra, then newest available model."""
    models = [m for m in models if isinstance(m, dict) and m.get("slug")]
    if not models:
        raise ClientError("Аккаунт не вернул доступных моделей.")
    slugs = [m["slug"] for m in models]
    for wanted in (preferred, DEFAULT_MODEL):
        if wanted in slugs:
            return wanted
    if all(_release_time(m) is not None for m in models):
        return max(models, key=lambda m: (_release_time(m), m["slug"]))["slug"]
    # ponytail: absent release dates, numeric versions approximate recency; use dates when supplied.
    def version(model):
        numbers = re.search(r"(?:gpt-|^o)(\d+(?:\.\d+)*)", model["slug"])
        return (tuple(int(n) for n in numbers.group(1).split(".")) if numbers else (), model["slug"])
    return max(models, key=version)["slug"]


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward a bearer token to an unexpected redirect destination.
        return None


def _http_error(code):
    message = {
        400: "Сервис отклонил запрос. Обновите мод или выберите другую модель.",
        401: "Сессия ChatGPT истекла. Войдите в аккаунт ещё раз.",
        403: "ChatGPT отказал в доступе. Проверьте доступ к Codex в аккаунте.",
        404: "Модель или адрес сервиса больше недоступны. Обновите список моделей или мод.",
        429: "Лимит ChatGPT исчерпан. Повторите позже или смените модель.",
    }.get(code, "Сервис ChatGPT временно недоступен. Повторите позже.")
    return ClientError("%s (HTTP %s)" % (message, code))


def _read_json(response, limit=MAX_RESPONSE_BYTES):
    raw = response.read(limit + 1)
    if len(raw) > limit:
        raise ClientError("Сервис вернул слишком большой ответ.")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeError):
        raise ClientError("Сервис вернул некорректный JSON.")
    if not isinstance(result, dict):
        raise ClientError("Неожиданный формат ответа сервиса.")
    return result


def _ssl_context():
    context = ssl.create_default_context()
    # Ren'Py's bundled OpenSSL can point to its build machine's CA directory.
    # Reuse the game's CA bundle only when the system trust store is empty.
    if not context.cert_store_stats().get("x509_ca"):
        for directory in sys.path:
            path = os.path.join(directory, "certifi", "cacert.pem")
            if os.path.isfile(path):
                context.load_verify_locations(cafile=path)
                break
    if not context.cert_store_stats().get("x509_ca"):
        raise ClientError("Не найдены системные сертификаты HTTPS. Обновите игру или задайте SSL_CERT_FILE.")
    return context



def _curl_response_open(url, body, headers):
    """Use Windows curl.exe for the long Codex SSE response.

    Python's urllib/http.client path proved unreliable for long-lived SSE on
    this backend even under modern Python, while the system curl transport
    completes the same requests reliably.  curl is used only for /responses
    and only inside the external Python 3 worker.
    """
    if os.name != "nt" or sys.version_info[0] < 3:
        raise ClientError("curl transport доступен только во внешнем Python 3 на Windows.")

    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    curl = os.path.join(system_root, "System32", "curl.exe")
    if not os.path.isfile(curl):
        curl = "curl.exe"

    request_headers = dict(headers or {})
    request_headers.update({
        "User-Agent": "generative_summer/0.1 (codex-compatible)",
        "originator": "generative_summer",
    })

    # Append the HTTP status after the SSE body so _authorized can keep its
    # existing 401-refresh / HTTP error behaviour.
    marker = b"\n__GS_HTTP_CODE__:"
    args = [
        curl,
        "--http1.1",
        "--no-buffer",
        "--silent",
        "--show-error",
        "--connect-timeout", "30",
        "--max-time", str(int(GENERATION_TIMEOUT + 30)),
        "--request", "POST" if body is not None else "GET",
        url,
    ]
    for key, value in request_headers.items():
        args.extend(["--header", "%s: %s" % (key, value)])
    if body is not None:
        args.extend(["--data-binary", "@-"])
    args.extend(["--write-out", "\n__GS_HTTP_CODE__:%{http_code}"])

    options = {"creationflags": 0x08000000} if os.name == "nt" else {}
    process = subprocess.Popen(
        args,
        stdin=subprocess.PIPE if body is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=os.name != "nt",
        **options
    )
    output, errors = process.communicate(body if body is not None else None)

    # Keep an upper bound even though curl has already buffered the response.
    if len(output) > MAX_RESPONSE_BYTES + 1024:
        raise ClientError("Сервис вернул слишком большой ответ.")

    payload, sep, status_raw = output.rpartition(marker)
    if not sep:
        detail = errors.decode("utf-8", "replace").strip()
        raise ClientError(
            "curl завершился без HTTP-статуса." + ((" " + detail[-1200:]) if detail else "")
        )

    try:
        status = int(status_raw.strip())
    except (TypeError, ValueError):
        raise ClientError("curl вернул некорректный HTTP-статус.")

    if process.returncode != 0:
        detail = errors.decode("utf-8", "replace").strip()
        if process.returncode == 28:
            raise ClientError("Истекло время ожидания ответа ChatGPT через curl.")
        raise ClientError(
            "curl прервал соединение с ChatGPT (код %s).%s" %
            (process.returncode, (" " + detail[-1200:]) if detail else "")
        )

    if status >= 400:
        raise HTTPError(url, status, "Codex request failed", {}, io.BytesIO(payload))

    return io.BytesIO(payload)

def _http_open(url, body=None, headers=None):
    if not url.startswith((ISSUER + "/", BACKEND + "/")):
        raise ClientError("Недопустимый адрес сервиса.")

    # Only the external modern-Python text worker uses curl.  OAuth, model
    # listing and image requests keep the original urllib implementation.
    if (url.startswith(BACKEND + "/responses")
            and sys.version_info[0] >= 3
            and os.name == "nt"):
        return _curl_response_open(url, body, headers)

    headers = dict(headers or {})
    headers.update({"User-Agent": "generative_summer/0.1 (codex-compatible)",
                    "originator": "generative_summer"})
    opener = build_opener(_NoRedirect(), HTTPSHandler(context=_ssl_context()))
    if url.startswith(BACKEND + "/images/"):
        timeout = GENERATION_TIMEOUT
    elif url.startswith(BACKEND + "/responses"):
        timeout = STREAM_TIMEOUT
    else:
        timeout = NETWORK_TIMEOUT
    return opener.open(Request(url, data=body, headers=headers), timeout=timeout)


def python_executable():
    executable = os.path.join(os.path.dirname(sys.executable), "python.exe" if os.name == "nt" else "python")
    if not os.path.isfile(executable):
        if not os.path.basename(sys.executable).lower().startswith("python"):
            raise ClientError("Не найден встроенный Python игры. Проверьте целостность установки.")
        executable = sys.executable
    return executable


def _image_process(url, body, headers):
    # Ren'Py's bundled network stack drops one of two threaded image requests.
    # Keep authorization/refresh in the parent and isolate just each HTTP exchange.
    options = {"creationflags": 0x08000000} if os.name == "nt" else {}
    with open(os.devnull, "wb") as errors:
        process = subprocess.Popen([python_executable(), os.path.splitext(os.path.abspath(__file__))[0] + ".py"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors, close_fds=os.name != "nt", **options)
        try:
            request = {"url": url, "body": body.decode("utf-8"), "headers": headers}
            process.stdin.write((json.dumps(request) + "\n").encode("utf-8"))
            process.stdin.flush()
            line = process.stdout.readline(4096)
            if not line or not line.endswith(b"\n"):
                raise ClientError("Процесс генерации фона завершился без изображения.")
            try:
                result = json.loads(line.decode("utf-8"))
                if not isinstance(result, dict):
                    raise ValueError()
            except (ValueError, UnicodeError):
                raise ClientError("Процесс генерации фона вернул некорректный ответ.")
            if result.get("http_error"):
                raise HTTPError(url, result["http_error"], "Image request failed", {}, io.BytesIO(b""))
            if result.get("error"):
                raise ClientError(result["error"])
            data = process.stdout.read(MAX_IMAGE_RESPONSE_BYTES + 1)
            if process.wait() != 0 or len(data) > MAX_IMAGE_RESPONSE_BYTES:
                raise ClientError("Процесс генерации фона вернул неполное или слишком большое изображение.")
            return io.BytesIO(data)
        finally:
            process.stdin.close()
            process.stdout.close()
            if process.poll() is None:
                try:
                    process.terminate()
                except OSError:
                    if process.poll() is None:
                        raise
            process.wait()


def _image_worker():
    request = json.loads(sys.stdin.readline())
    # Keep stdin open after the request: EOF means the parent/game was closed.
    def watch_parent():
        sys.stdin.read()
        os._exit(0)
    watcher = threading.Thread(target=watch_parent)
    watcher.daemon = True
    watcher.start()
    result, data = {}, b""
    try:
        if not request["url"].startswith(BACKEND + "/images/"):
            raise ClientError("Недопустимый адрес генерации фона.")
        response = _http_open(request["url"], request["body"].encode("utf-8"), request["headers"])
        try:
            data = response.read(MAX_IMAGE_RESPONSE_BYTES + 1)
            if len(data) > MAX_IMAGE_RESPONSE_BYTES:
                raise ClientError("Сервис вернул слишком большое изображение.")
        finally:
            response.close()
    except HTTPError as exc:
        exc.close()
        result = {"http_error": exc.code}
    except (URLError, socket.error, ssl.SSLError):
        result = {"error": "Соединение прервалось при генерации фона."}
    except ClientError as exc:
        result = {"error": text_type(exc)}
    output = getattr(sys.stdout, "buffer", sys.stdout)
    output.write((json.dumps(result) + "\n").encode("utf-8"))
    if not result:
        output.write(data)
    output.flush()
    os._exit(0)  # Do not finalize Python's buffered stdin while the watchdog is reading it.


def _response_text(response, cancel=None, trace=None):
    """Require a completed SSE response; never accept a truncated scene."""
    deadline = time.time() + GENERATION_TIMEOUT
    size, data, chunks = 0, [], []
    trace = trace if trace is not None else {}
    trace["output_text_deltas"] = chunks
    trace["event_counts"] = {}
    while True:
        if cancel is not None and cancel.is_set():
            raise ClientError("Генерация отменена.")
        if time.time() > deadline:
            raise ClientError("Генерация заняла слишком много времени. Повторите запрос.")
        line = response.readline(MAX_RESPONSE_BYTES + 1)
        size += len(line)
        if size > MAX_RESPONSE_BYTES:
            raise ClientError("Сервис вернул слишком большой ответ.")
        if line and line.strip():
            if line.startswith(b"data:"):
                data.append(line[5:].strip())
            continue
        if data:
            raw = b"\n".join(data)
            data = []
            if raw == b"[DONE]":
                break
            try:
                event = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeError):
                raise ClientError("Не удалось разобрать поток ответа ChatGPT.")
            if not isinstance(event, dict):
                raise ClientError("Неожиданный формат потока ChatGPT.")
            kind = event.get("type")
            if isinstance(kind, text_type):
                trace["last_event"] = kind
                trace["event_counts"][kind] = trace["event_counts"].get(kind, 0) + 1
            result = event.get("response")
            if isinstance(result, dict):
                for key in ("id", "model", "status", "usage", "incomplete_details", "service_tier"):
                    if key in result:
                        trace[key] = result[key]
            if kind == "response.output_text.delta":
                delta = event.get("delta", "")
                if not isinstance(delta, text_type):
                    raise ClientError("Неожиданный формат текста ChatGPT.")
                chunks.append(delta)
            elif kind in ("error", "response.failed", "response.incomplete"):
                raise ClientError("ChatGPT не завершил сцену. Повторите запрос или выберите другую модель.")
            elif kind in ("response.refusal.delta", "response.refusal.done"):
                trace["refusal"] = event.get("refusal", event.get("delta", ""))
                trace["refusal_partial"] = kind == "response.refusal.delta"
                raise ClientError("ChatGPT отклонил этот сюжет. Измените описание истории.")
            elif kind == "response.completed":
                result = event.get("response", {})
                if not isinstance(result, dict) or result.get("status", "completed") != "completed":
                    raise ClientError("ChatGPT не завершил сцену. Повторите запрос.")
                final = []
                for item in result.get("output", []):
                    if isinstance(item, dict) and item.get("type") == "message":
                        for content in item.get("content", []):
                            if not isinstance(content, dict):
                                raise ClientError("Неожиданный формат текста ChatGPT.")
                            if content.get("type") == "refusal":
                                trace["refusal"] = content.get("refusal", "")
                                trace["refusal_partial"] = False
                                raise ClientError("ChatGPT отклонил этот сюжет. Измените описание истории.")
                            if content.get("type") == "output_text":
                                value = content.get("text", "")
                                if not isinstance(value, text_type):
                                    raise ClientError("Неожиданный формат текста ChatGPT.")
                                final.append(value)
                text = "".join(final or chunks)
                trace["output_text"] = text
                if not text.strip():
                    raise ClientError("ChatGPT вернул пустую сцену. Повторите запрос.")
                return text
        if not line:
            break
    raise ClientError("Соединение прервалось до завершения сцены. Повторите запрос.")


def _external_python3():
    """Find an optional modern Python for long-lived SSE requests."""
    candidates = []
    configured = os.environ.get("GS_PYTHON3")
    if configured:
        candidates.append(configured)

    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            candidates.extend(sorted(glob.glob(os.path.join(
                local, "Microsoft", "WindowsApps",
                "PythonSoftwareFoundation.PythonManager_*", "python.exe"
            )), reverse=True))
            candidates.extend(sorted(glob.glob(os.path.join(
                local, "Programs", "Python", "Python3*", "python.exe"
            )), reverse=True))

        program_files = os.environ.get("ProgramFiles", "")
        if program_files:
            candidates.extend(sorted(glob.glob(os.path.join(
                program_files, "Python3*", "python.exe"
            )), reverse=True))

    seen = set()
    for path in candidates:
        if not path or path in seen:
            continue
        seen.add(path)
        if os.path.isfile(path) and os.path.abspath(path) != os.path.abspath(sys.executable):
            return path
    return None


def _generate_via_python3(client, executable, instructions, prompt, model, effort,
                          cancel, trace, fast_mode):
    """Run only the long text SSE exchange in modern Python.

    Ren'Py and the rest of the runtime stay on bundled Python 2.7, so pygame_sdl2
    and generated-background handling remain unchanged.

    The result is exchanged through a temporary file rather than stdout. This
    avoids both Python 2 environment-type issues and Windows pipe deadlocks on
    large traces/responses.
    """
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gs_text_worker.py")
    if not os.path.isfile(worker):
        raise ClientError("Не найден gs_text_worker.py рядом с gs_backend.py.")

    if not os.path.isdir(client.data_dir):
        os.makedirs(client.data_dir)

    fd, result_path = tempfile.mkstemp(
        prefix=".gs-text-result-", suffix=".json", dir=client.data_dir
    )
    os.close(fd)

    request = {
        "data_dir": client.data_dir,
        "instructions": instructions,
        "prompt": prompt,
        "model": model,
        "effort": effort,
        "fast_mode": bool(fast_mode),
        "result_path": result_path,
    }

    options = {"creationflags": 0x08000000} if os.name == "nt" else {}

    # Do not pass env= here. Ren'Py's Python 2 subprocess rejects unicode
    # entries from its environment ("environment can only contain strings").
    process = subprocess.Popen(
        [executable, worker],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=os.name != "nt",
        **options
    )

    hard_deadline = time.time() + GENERATION_TIMEOUT + 60
    try:
        process.stdin.write((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
        process.stdin.flush()

        while process.poll() is None:
            if cancel is not None and cancel.is_set():
                try:
                    process.terminate()
                except OSError:
                    pass
                raise ClientError("Генерация отменена.")
            if time.time() > hard_deadline:
                try:
                    process.terminate()
                except OSError:
                    pass
                raise ClientError("Генерация заняла слишком много времени. Повторите запрос.")
            time.sleep(0.1)

        # Worker intentionally writes only tiny diagnostics to stdio; the
        # potentially large response/trace lives in result_path.
        output = process.stdout.read(4096)
        errors = process.stderr.read(64 * 1024)

        try:
            with open(result_path, "rb") as stream:
                raw = stream.read(MAX_RESPONSE_BYTES + 1)
        except IOError:
            raw = b""

        if len(raw) > MAX_RESPONSE_BYTES:
            raise ClientError("Процесс Python 3 вернул слишком большой ответ.")

        try:
            result = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError):
            detail = errors.decode("utf-8", "replace").strip()
            if not detail and output:
                detail = output.decode("utf-8", "replace").strip()
            if detail:
                detail = detail[-1500:]
            raise ClientError("Процесс Python 3 завершился без корректного результата." +
                              ((" " + detail) if detail else ""))

        worker_trace = result.get("trace")
        if trace is not None and isinstance(worker_trace, dict):
            trace.update(worker_trace)

        client.effective_model = result.get("effective_model")
        client.effective_effort = result.get("effective_effort")

        # The worker may refresh OAuth and rewrite auth.json.
        client._tokens = None
        client._load()

        if not result.get("ok"):
            raise ClientError(result.get("error") or
                              "Процесс Python 3 не завершил генерацию.")

        text = result.get("text")
        if not isinstance(text, text_type) or not text.strip():
            raise ClientError("Процесс Python 3 вернул пустую сцену.")
        return text
    finally:
        try:
            process.stdin.close()
        except Exception:
            pass
        try:
            process.stdout.close()
        except Exception:
            pass
        try:
            process.stderr.close()
        except Exception:
            pass
        if process.poll() is None:
            try:
                process.terminate()
            except OSError:
                pass
        try:
            process.wait()
        except Exception:
            pass
        try:
            os.unlink(result_path)
        except OSError:
            pass


class Client(object):
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.auth_path = os.path.join(data_dir, "auth.json")
        self.login_url = None
        self.effective_model = None
        self.effective_effort = None
        self._lock = threading.RLock()
        self._models = None
        self._tokens = None
        self._load()

    def _load(self):
        if self._tokens is None:
            try:
                with open(self.auth_path, "rb") as stream:
                    data = json.loads(stream.read(128 * 1024).decode("utf-8"))
                self._tokens = data if isinstance(data, dict) else {}
                if any(not _valid_token(self._tokens.get(key))
                       for key in ("access_token", "refresh_token")):
                    self._tokens = {}
                if not isinstance(self._tokens.get("refreshed_at"), (int, float)):
                    self._tokens["refreshed_at"] = 0
            except (IOError, ValueError, UnicodeError):
                self._tokens = {}
        return self._tokens

    def authenticated(self):
        # Screens (including prediction) must never wait for the network lock.
        # Credentials are loaded once and replaced atomically on save/logout.
        tokens = self._tokens or {}
        return bool(tokens.get("access_token") and tokens.get("refresh_token"))

    def _save(self, tokens):
        for field in ("access_token", "refresh_token"):
            value = tokens.get(field)
            if not _valid_token(value):
                raise ClientError("Сервис вернул некорректные данные входа.")
        if not os.path.isdir(self.data_dir):
            os.makedirs(self.data_dir, 0o700)
        if os.name != "nt":
            os.chmod(self.data_dir, 0o700)
        fd, path = tempfile.mkstemp(prefix=".auth-", dir=self.data_dir)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(json.dumps(tokens, ensure_ascii=False).encode("utf-8"))
                stream.flush()
                os.fsync(stream.fileno())
            if os.name == "nt" and not hasattr(os, "replace"):
                import ctypes
                if not ctypes.windll.kernel32.MoveFileExW(text_type(path), text_type(self.auth_path), 0x9):
                    raise ctypes.WinError()
            else:
                getattr(os, "replace", os.rename)(path, self.auth_path)
            self._tokens = tokens
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def logout(self):
        with self._lock:
            if os.path.exists(self.auth_path):
                os.unlink(self.auth_path)
            self._tokens = {}
            self._models = None

    def _open(self, url, body=None, headers=None):
        if url.startswith(BACKEND + "/images/"):
            return _image_process(url, body, headers)
        return _http_open(url, body, headers)

    def _token_request(self, fields, form=False):
        body = urlencode(fields).encode("ascii") if form else json.dumps(fields).encode("utf-8")
        content_type = "application/x-www-form-urlencoded" if form else "application/json"
        try:
            response = self._open(ISSUER + "/oauth/token", body, {"Content-Type": content_type})
            try:
                return _read_json(response)
            finally:
                response.close()
        except HTTPError as exc:
            exc.close()
            if exc.code in (400, 401):
                raise ClientError("Не удалось обновить вход ChatGPT. Подключите аккаунт ещё раз.")
            raise _http_error(exc.code)
        except (URLError, socket.error, ssl.SSLError):
            raise ClientError("Не удалось соединиться с сервером входа ChatGPT. Проверьте интернет и системные сертификаты.")

    def _refresh(self):
        old = self._load()
        if not old.get("refresh_token"):
            raise ClientError("Сначала подключите аккаунт ChatGPT.")
        tokens = self._token_request({"client_id": CLIENT_ID, "grant_type": "refresh_token",
                                      "refresh_token": old["refresh_token"]})
        merged = dict(old)
        merged.update({key: value for key, value in tokens.items() if value is not None})
        merged["refreshed_at"] = time.time()
        self._save(merged)

    def _authorized(self, path, body=None, stream=False):
        # Share refreshes, not the lifetime of text/image requests.
        with self._lock:
            if not self.authenticated():
                raise ClientError("Сначала подключите аккаунт ChatGPT.")
            tokens = self._load()
            expiry = _claims(tokens["access_token"]).get("exp")
            if (isinstance(expiry, (int, float)) and expiry < time.time() + 60) or time.time() - tokens.get("refreshed_at", 0) > 7 * 86400:
                self._refresh()
        for attempt in range(2):
            tokens = self._load()
            if not tokens.get("access_token"):
                raise ClientError("Сначала подключите аккаунт ChatGPT.")
            headers = {"Authorization": "Bearer " + tokens["access_token"],
                       "Content-Type": "application/json",
                       "Accept": "text/event-stream" if stream else "application/json"}
            claims = _claims(tokens.get("id_token", ""))
            auth = claims.get("https://api.openai.com/auth", {})
            account = auth.get("chatgpt_account_id") if isinstance(auth, dict) else None
            if not account:
                auth = _claims(tokens["access_token"]).get("https://api.openai.com/auth", {})
                account = auth.get("chatgpt_account_id") if isinstance(auth, dict) else None
            if isinstance(account, text_type) and re.match(r"^[A-Za-z0-9_-]+\Z", account):
                headers["ChatGPT-Account-Id"] = account
            try:
                return self._open(BACKEND + path, body, headers)
            except HTTPError as exc:
                exc.close()
                if exc.code == 401 and attempt == 0:
                    with self._lock:
                        if self._load().get("access_token") == tokens["access_token"]:
                            self._refresh()
                    continue
                raise _http_error(exc.code)
            except (URLError, socket.error, ssl.SSLError):
                raise ClientError("Нет соединения с ChatGPT. Проверьте интернет и системные сертификаты.")

    def login(self, on_status=None, cancel=None):
        """Run in a worker thread; cancel is an optional threading.Event."""
        verifier, state = _b64(os.urandom(48)), _b64(os.urandom(32))
        result = {}
        class Callback(BaseHTTPRequestHandler):
            timeout = 2

            def log_message(self, *args):
                pass  # Callback URLs contain authorization codes.

            def do_GET(self):
                try:
                    parsed = urlsplit(self.path)
                    query = parse_qs(parsed.query)
                    received = query.get("state", [""])[0].encode("utf-8")
                except (ValueError, UnicodeError):
                    self.send_error(400, "Invalid callback")
                    return
                expected_host = ("localhost:%s" % self.server.server_port, "127.0.0.1:%s" % self.server.server_port)
                valid = (parsed.path == "/auth/callback" and self.headers.get("Host") in expected_host
                         and hmac.compare_digest(received, state.encode("ascii")))
                if valid and "error" in query:
                    result["error"] = True
                elif valid and query.get("code", [""])[0]:
                    result["code"] = query["code"][0]
                else:
                    valid = False
                body = ("Login received. Return to Generative Summer." if valid else "Invalid callback.").encode("utf-8")
                self.send_response(200 if valid else 400)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(body)
        try:
            server = HTTPServer(("127.0.0.1", 1455), Callback)
        except socket.error:
            # Codex registers two callback ports; arbitrary ephemeral ports are not supported.
            try:
                server = HTTPServer(("127.0.0.1", 1457), Callback)
            except socket.error:
                raise ClientError("Порты входа 1455 и 1457 заняты. Завершите другой вход Codex и повторите.")
        server.timeout = 0.5
        redirect = "http://localhost:%s/auth/callback" % server.server_port
        self.login_url = ISSUER + "/oauth/authorize?" + urlencode({
            "response_type": "code", "client_id": CLIENT_ID, "redirect_uri": redirect,
            "scope": "openid profile email offline_access", "state": state,
            "code_challenge": _b64(hashlib.sha256(verifier.encode("ascii")).digest()),
            "code_challenge_method": "S256", "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true", "originator": "generative_summer"})
        try:
            if on_status:
                on_status("Завершите вход ChatGPT в открывшемся браузере.")
            webbrowser.open(self.login_url)
            deadline = time.time() + LOGIN_TIMEOUT
            while not result:
                if cancel is not None and cancel.is_set():
                    raise ClientError("Вход отменён.")
                if time.time() > deadline:
                    raise ClientError("Время входа истекло. Попробуйте подключить аккаунт снова.")
                server.handle_request()
            if result.get("error"):
                raise ClientError("Вход отменён или отклонён на стороне ChatGPT.")
            tokens = self._token_request({"grant_type": "authorization_code", "code": result["code"],
                "redirect_uri": redirect, "client_id": CLIENT_ID, "code_verifier": verifier}, form=True)
            if cancel is not None and cancel.is_set():
                raise ClientError("Вход отменён.")
            tokens["refreshed_at"] = time.time()
            with self._lock:
                self._save(tokens)
                self._models = None
            return True
        finally:
            server.server_close()
            self.login_url = None

    def list_models(self):
        with self._lock:
            response = self._authorized("/models?" + urlencode({"client_version": CLIENT_VERSION}))
            try:
                models = _read_json(response).get("models")
            except (socket.error, ssl.SSLError):
                raise ClientError("Соединение прервалось при загрузке моделей. Повторите запрос.")
            finally:
                response.close()
            if not isinstance(models, list):
                raise ClientError("Неожиданный формат списка моделей.")
            self._models = [m for m in models if isinstance(m, dict)
                and isinstance(m.get("slug"), text_type)
                and re.match(r"^[A-Za-z0-9._-]+\Z", m["slug"])
                and m.get("visibility", "list") == "list"]
            if not self._models:
                raise ClientError("Аккаунт не вернул доступных моделей Codex.")
            return self._models

    def generate_background(self, prompt, references=None, trace=None):
        """Same subscription/auth as Codex's standalone Images client, no API key."""
        body = {"model": IMAGE_MODEL, "prompt": prompt, "size": "2048x1152",
                "quality": "medium", "background": "opaque", "n": 1}
        path = "/images/edits" if references else "/images/generations"
        if references:
            body["images"] = [{"image_url": value} for value in references]
        if trace is not None:
            trace.update(request=dict(body), endpoint=BACKEND + path)
            if references:
                trace["request"]["images"] = [{"source": "original game style reference"} for value in references]
        response = self._authorized(path, json.dumps(body, ensure_ascii=False).encode("utf-8"))
        try:
            result = _read_json(response, MAX_IMAGE_RESPONSE_BYTES)
        except (socket.error, ssl.SSLError):
            raise ClientError("Соединение прервалось при генерации фона. Уже готовые фоны сохранены; повторите позже.")
        finally:
            response.close()
        if trace is not None:
            trace["response"] = dict((key, result[key]) for key in
                ("created", "size", "quality", "background", "usage") if key in result)
        images = result.get("data")
        if not isinstance(images, list) or len(images) != 1 or not isinstance(images[0], dict):
            raise ClientError("Сервис не вернул готовый фон. Повторите позже.")
        encoded = images[0].get("b64_json")
        if not isinstance(encoded, text_type) or not re.match(r"^[A-Za-z0-9+/]+={0,2}\Z", encoded):
            raise ClientError("Сервис вернул повреждённое изображение фона.")
        try:
            return base64.b64decode(encoded.encode("ascii"))
        except (binascii.Error, ValueError, TypeError):
            raise ClientError("Сервис вернул повреждённое изображение фона.")

    def generate(self, instructions, prompt, model=None, effort=DEFAULT_EFFORT, cancel=None, trace=None, fast_mode=True):
        # Ren'Py 7.4 / Python 2.7 is unreliable on the long Codex SSE stream.
        # If a modern Python is installed, isolate only this text request there.
        if sys.version_info[0] < 3 and not os.environ.get("GS_TEXT_WORKER"):
            executable = _external_python3()
            if executable:
                return _generate_via_python3(
                    self, executable, instructions, prompt, model, effort,
                    cancel, trace, fast_mode
                )

        models = self._models or self.list_models()
        selected = default_model(models, model)
        metadata = next(m for m in models if m["slug"] == selected)
        raw_levels = metadata.get("supported_reasoning_levels")
        if raw_levels is not None and not isinstance(raw_levels, list):
            raise ClientError("Неожиданный формат настроек модели.")
        levels = [m.get("effort") if isinstance(m, dict) else m for m in (raw_levels or [])]
        levels = [level for level in levels if isinstance(level, text_type)
                  and re.match(r"^[a-z]+\Z", level)]
        if levels and effort not in levels:
            default = metadata.get("default_reasoning_level")
            effort = default if default in levels else levels[0]
        body = {"model": selected, "instructions": instructions,
            "input": [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            "store": False, "stream": True, "tools": [], "tool_choice": "auto",
            "parallel_tool_calls": False, "include": []}
        # Codex backend controls retention and rejects the public API's TTL fields.
        # Only the stable prefix participates; chapters, repairs and restarts reuse it.
        body["prompt_cache_key"] = hashlib.sha256(instructions.encode("utf-8")).hexdigest()
        tiers = metadata.get("service_tiers") or []
        if not isinstance(tiers, list):
            raise ClientError("Неожиданный формат режимов скорости модели.")
        tier_ids = [tier.get("id") for tier in tiers if isinstance(tier, dict)]
        if fast_mode:
            if "priority" in tier_ids or (not tiers and "fast" in (metadata.get("additional_speed_tiers") or [])):
                body["service_tier"] = "priority"
            elif "fast" in tier_ids:
                body["service_tier"] = "fast"
        else:
            body["service_tier"] = "default"
        if levels or raw_levels is None:
            body["reasoning"] = {"effort": effort}
        self.effective_model = selected
        self.effective_effort = body.get("reasoning", {}).get("effort")
        if trace is not None:
            # Only the JSON body and selected SSE fields; never auth headers or reasoning items.
            trace["request"] = body
            trace["endpoint"] = BACKEND + "/responses"
            trace["response"] = {}
        response = self._authorized("/responses", json.dumps(body, ensure_ascii=False).encode("utf-8"), stream=True)
        try:
            return _response_text(response, cancel, trace["response"] if trace is not None else None)
        except (socket.error, ssl.SSLError):
            raise ClientError("Соединение прервалось до завершения сцены. Повторите запрос.")
        finally:
            response.close()


if __name__ == "__main__":
    _image_worker()
