# -*- coding: utf-8 -*-
"""Network/disk work lives outside Ren'Py's rollback and save stores."""
from __future__ import unicode_literals

import threading
import json
import logging
import os
import subprocess
import sys
import time
import uuid

# The generation child may be launched from a working directory outside the
# Workshop mod folder. Ensure sibling modules are importable by absolute file
# location rather than depending on cwd.
_module_dir = os.path.dirname(os.path.abspath(__file__))
if _module_dir not in sys.path:
    sys.path.insert(0, _module_dir)

import gs_backend
import gs_core

try:
    text_type = unicode
except NameError:
    text_type = str


class Runtime(object):
    def __init__(self, directory, catalog):
        self.client = gs_backend.Client(directory)
        self.library = gs_core.Store(directory, catalog)
        self.catalog = catalog
        self.models = []
        self.stories = []
        self.busy = False
        self.error = None
        self.status = ""
        self.result = None
        self.active_model = ""
        self.trace_error = None
        self.cancel = threading.Event()

    def start(self, task, *args):
        if self.busy:
            return
        self.busy = True
        self.error = None
        self.result = None
        self.status = "Подождите…"
        self.cancel = threading.Event()

        thread = threading.Thread(target=self._run, args=(task,) + args)
        thread.daemon = True
        thread.start()

    def _run(self, task, *args):
        try:
            self.result = task(*args)
        except gs_backend.ClientError as exc:
            self.error = text_type(exc)
        except gs_core.StoryError as exc:
            self.error = "Сценарий не прошёл проверку: " + text_type(exc)
        except (IOError, OSError):
            self.error = "Не удалось прочитать или сохранить данные мода. Проверьте доступ к папке сохранений и свободное место."
        except Exception as exc:
            logging.exception("Generative Summer operation failed")
            detail = ("%s: %s" % (exc.__class__.__name__, text_type(exc))).strip()
            self.error = "Не удалось выполнить операцию. Попробуйте ещё раз."
            if detail:
                self.error += " (" + detail[:600] + ")"
        finally:
            self.busy = False

    def login(self):
        self.status = "Завершите вход в ChatGPT в открывшемся браузере."
        self.client.login(on_status=self.set_status, cancel=self.cancel)

    def set_status(self, status):
        self.status = status

    def refresh_models(self):
        self.set_status("Получаем доступные вашему аккаунту модели…")
        self.models = self.client.list_models()

    def refresh_stories(self):
        self.stories = self.library.list_stories()

    def create(self, premise, source_profile_name="vanilla"):
        self.result = self.library.create(premise, source_profile_name)
        return self.result

    def _save_trace(self, trace):
        if trace is None:
            return
        trace["finished_at"] = time.time()
        try:
            directory = os.path.join(self.library.root, "traces")
            gs_core._mkdir(directory)
            if os.name != "nt":
                os.chmod(directory, 0o700)
            gs_core._write_json(os.path.join(directory, uuid.uuid4().hex + ".json"), trace)
        except (IOError, OSError, ValueError, TypeError):
            # Diagnostics must never discard a generated chapter or trigger another request.
            self.trace_error = "Не удалось записать трейс генерации. Проверьте папку сохранений и свободное место."
            logging.warning(self.trace_error)

    def generate(self, story_id, parent_id, choice_index, preferred, custom_choice=None, fast_mode=True):
        """Only IPC runs in the game's worker thread; generation owns another interpreter."""
        executable = gs_backend.python_executable()
        options = {"creationflags": 0x08000000} if os.name == "nt" else {}
        with open(os.devnull, "wb") as errors:
            process = subprocess.Popen([executable, os.path.splitext(os.path.abspath(__file__))[0] + ".py"],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                                       close_fds=os.name != "nt", **options)
            try:
                request = {"directory": self.library.root, "catalog": self.catalog, "models": self.models,
                           "args": [story_id, parent_id, choice_index, preferred, custom_choice, fast_mode]}
                process.stdin.write((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
                process.stdin.flush()
                while True:
                    line = process.stdout.readline(16 * 1024 * 1024)
                    if not line or not line.endswith(b"\n"):
                        raise gs_backend.ClientError("Процесс генерации завершился без главы. Попробуйте ещё раз.")
                    message = json.loads(line.decode("utf-8"))
                    if "status" in message:
                        self.status = message["status"]
                    if "result" in message:
                        self.models = self.client._models = message["models"]
                        self.active_model = message["active_model"]
                        self.trace_error = message["trace_error"]
                        if self.trace_error:
                            logging.warning(self.trace_error)
                        # The child may have refreshed the persisted ChatGPT session.
                        self.client._tokens = None
                        self.client._load()
                        if message["error"]:
                            raise gs_backend.ClientError(message["error"])
                        return message["result"]
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

    def _draw_background(self, job):
        try:
            job["data"] = self.client.generate_background(gs_core.BACKGROUND_STYLE + job["description"],
                references=self.catalog.get("background_references"), trace=job["trace"])
        except Exception as exc:
            job["error"] = exc

    def _finish_backgrounds(self, story_id, jobs):
        # HTTP runs in parallel; PNG decoding and immutable disk commits stay on this thread.
        failed, fatal = [], None
        while jobs:
            job = jobs.pop(0)
            job["thread"].join()
            trace = job["trace"]
            try:
                if "error" in job:
                    raise job["error"]
                self.library.save_background(story_id, job["description"], job.pop("data"))
                if trace is not None:
                    trace["outcome"] = "background_ready"
            except (gs_backend.ClientError, gs_core.StoryError) as exc:
                failed.append({"name": job["name"], "error": text_type(exc)})
                if trace is not None:
                    trace.update(outcome="background_failed", error=text_type(exc))
            except Exception as exc:
                # Disk/programming failures are fatal, but still drain every in-flight request.
                fatal = fatal or exc
                if trace is not None:
                    trace["outcome"] = "error"
            finally:
                self._save_trace(trace)
        if fatal is not None:
            raise fatal
        return failed

    def _generate(self, story_id, parent_id, choice_index, preferred, custom_choice=None, fast_mode=True):
        node_id, parent = self.library._branch(story_id, parent_id, choice_index, custom_choice)
        node = self.library.get_node(story_id, node_id)
        if node is not None:
            return node
        if not self.models:
            self.refresh_models()
        self.active_model = gs_backend.default_model(self.models, preferred)
        self.set_status("Пишем следующую главу · " + self.active_model + "…")
        prompt = self.library.generation_prompt(story_id, parent_id, choice_index, custom_choice)
        instructions = gs_core.instructions(self.catalog)
        request = prompt
        trace_enabled = os.path.isfile(os.path.join(self.library.root, "trace.enabled"))
        self.trace_error = None
        generation_id = uuid.uuid4().hex
        corrections, planned, jobs = 0, False, []
        try:
            # One image plan, chapter, one image-failure rewrite, and at most two format repairs.
            for attempt in range(5):
                trace = {"version": 1, "generation_id": generation_id, "story_id": story_id,
                         "node_id": node_id, "parent_id": parent_id, "choice_index": choice_index,
                         "custom_choice": gs_core.custom_choice_text(custom_choice) if custom_choice is not None else None,
                         "attempt": attempt + 1, "stage": "repair" if corrections else "generate",
                         "started_at": time.time(), "outcome": "interrupted"} if trace_enabled else None
                try:
                    raw = self.client.generate(instructions, request, model=self.active_model,
                                               effort=gs_backend.DEFAULT_EFFORT, trace=trace, fast_mode=fast_mode)
                    if trace is not None:
                        trace["raw_output"] = raw
                    if jobs:
                        self.set_status("Рисуем фон · ждём готовности изображений…")
                    failed = self._finish_backgrounds(story_id, jobs)
                    prompt = self.library.generation_prompt(story_id, parent_id, choice_index, custom_choice)
                    draft = raw if isinstance(raw, text_type) else json.dumps(raw, ensure_ascii=False)
                    if failed:
                        # Discard the entire speculative chapter, including its memory, before committing anything.
                        request = (prompt + "\n\nГенерация этих фонов не удалась: " + json.dumps(failed, ensure_ascii=False) +
                                   "\nПерепиши целиком черновик главы и memory без недоступных фонов. "
                                   "Сохрани события, место действия, реплики, длину и выбор либо финал. "
                                   "Используй только готовые фоны из каталога; если подходящего нет, используй bg black "
                                   "и передай окружение словами, не переноси действие в лагерь. "
                                   "Не повторяй запрос изображений. Верни полный JSON с title, memory, script.\n" + draft[:180000])
                        if trace is not None:
                            trace.update(outcome="background_rewrite", failed_backgrounds=failed)
                        self.set_status("Исправляем главу без недоступных фонов…")
                        continue
                    try:
                        descriptions = gs_core.background_request(raw)
                        if descriptions is not None and planned:
                            raise gs_core.StoryError("Backgrounds have already been planned. Return the chapter with title, memory, script, using only available backgrounds.")
                        if descriptions is None:
                            payload = gs_core.parse_payload(raw, self.library.story_catalog(story_id))
                    except gs_core.StoryError as exc:
                        if trace is not None:
                            trace.update(outcome="validation_error", validation_error=text_type(exc))
                        if corrections == 2:
                            raise gs_core.StoryError("Не удалось автоматически исправить главу после двух попыток. " + text_type(exc))
                        corrections += 1
                        self.set_status("Исправляем детали главы · попытка %s из 2…" % corrections)
                        request = (prompt + "\n\nИсправь этот черновик, не сочиняй новую главу. "
                                   "Сохрани сюжет, реплики, варианты выбора либо финал с return и память; исправь ошибки формата и ресурсов. "
                                   "Близкие варианты в сообщениях — подсказки, выбери подходящее точное имя из каталога. "
                                   "Если подходящего спрайта или звука нет, убери эту команду. "
                                   "Не сокращай главу. Верни целиком исправленный JSON с title, memory, script, без Markdown.\n" +
                                   json.dumps({"validation_errors": text_type(exc), "draft": draft[:180000]}, ensure_ascii=False))
                        continue
                    if descriptions is not None:
                        planned = True
                        backgrounds = [{"name": gs_core.background_name(value), "description": value} for value in descriptions]
                        existing = {item["name"] for item in self.library.backgrounds(story_id)}
                        for background in backgrounds:
                            if background["name"] in existing:
                                continue
                            image_trace = dict(trace, stage="background", started_at=time.time(),
                                               background=background) if trace is not None else None
                            # Each request owns its trace; never copy text request/response into image diagnostics.
                            if image_trace is not None:
                                for key in ("request", "response", "raw_output"):
                                    image_trace.pop(key, None)
                            job = dict(background, trace=image_trace)
                            job["thread"] = threading.Thread(target=self._draw_background, args=(job,))
                            job["thread"].daemon = True
                            job["thread"].start()
                            jobs.append(job)
                        request = (prompt + "\n\nЗапланированные фоны (генерируются параллельно с текстом): " +
                                   json.dumps(backgrounds, ensure_ascii=False) +
                                   "\nСразу пиши главу, используя эти точные name в scene. Мод дождётся изображений перед показом. "
                                   "Больше фоны не запрашивай; верни JSON с title, memory, script.")
                        if trace is not None:
                            trace.update(outcome="backgrounds_planned", backgrounds=backgrounds)
                        self.set_status("Пишем главу и рисуем фоны · %s…" % self.active_model)
                        continue
                    node = self.library.save_node(story_id, payload, parent_id, choice_index, custom_choice)
                    if trace is not None:
                        trace["outcome"] = "saved"
                    return node
                except gs_backend.ClientError as exc:
                    if trace is not None:
                        outcome = "refused" if "refusal" in trace.get("response", {}) else "client_error"
                        trace.update(outcome=outcome, error=text_type(exc))
                    raise
                except (IOError, OSError):
                    if trace is not None:
                        trace["outcome"] = "disk_error"
                    raise
                finally:
                    self._save_trace(trace)
            raise gs_core.StoryError("Не удалось подготовить главу. Готовые фоны сохранены; попробуйте ещё раз.")
        finally:
            # Text failure must not abandon image workers or lose backgrounds that already completed.
            self._finish_backgrounds(story_id, jobs)


app = None


def _worker():
    request = json.loads(sys.stdin.readline())
    # EOF means the game closed. Do not leave a generation process running behind it.
    def watch_game():
        sys.stdin.read()
        os._exit(0)
    watcher = threading.Thread(target=watch_game)
    watcher.daemon = True
    watcher.start()
    output = getattr(sys.stdout, "buffer", sys.stdout)
    def send(message):
        output.write((json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8"))
        output.flush()
    worker = Runtime(request["directory"], request["catalog"])
    worker.models = worker.client._models = request["models"]
    worker.set_status = lambda status: send({"status": status})
    worker._run(worker._generate, *request["args"])
    send({"result": worker.result, "error": worker.error, "models": worker.models,
          "active_model": worker.active_model, "trace_error": worker.trace_error})


if __name__ == "__main__":
    _worker()
