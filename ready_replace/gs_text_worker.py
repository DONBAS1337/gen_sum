# -*- coding: utf-8 -*-
"""Modern-Python worker for the long Codex text SSE request."""
from __future__ import print_function, unicode_literals

import json
import os
import sys
import threading

# Mark the helper before importing gs_backend. Python 3 would not bridge again
# anyway, but this also makes the execution mode explicit.
os.environ["GS_TEXT_WORKER"] = "1"

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

import gs_backend


def _watch_parent():
    # Parent keeps stdin open while we work. EOF means the Ren'Py worker died.
    try:
        sys.stdin.buffer.read()
    except AttributeError:
        sys.stdin.read()
    os._exit(0)


def _write_result(path, value):
    data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    with open(path, "wb") as stream:
        stream.write(data)
        stream.flush()
        try:
            os.fsync(stream.fileno())
        except OSError:
            pass


def main():
    input_stream = getattr(sys.stdin, "buffer", sys.stdin)
    line = input_stream.readline()

    request = None
    result_path = None
    try:
        if not line:
            raise ValueError("empty request")
        if not isinstance(line, str):
            line = line.decode("utf-8")
        request = json.loads(line)
        result_path = request.get("result_path")
        if not result_path:
            raise ValueError("missing result_path")
    except Exception as exc:
        # At this point we may not have a usable result path, so stderr is the
        # only reliable diagnostic channel.
        sys.stderr.write("Invalid Python 3 worker request: %s\n" % exc)
        sys.stderr.flush()
        return 2

    watcher = threading.Thread(target=_watch_parent)
    watcher.daemon = True
    watcher.start()

    trace = {}
    client = None
    try:
        client = gs_backend.Client(request["data_dir"])
        text = client.generate(
            request["instructions"],
            request["prompt"],
            model=request.get("model"),
            effort=request.get("effort", gs_backend.DEFAULT_EFFORT),
            trace=trace,
            fast_mode=bool(request.get("fast_mode", True)),
        )
        _write_result(result_path, {
            "ok": True,
            "text": text,
            "trace": trace,
            "effective_model": client.effective_model,
            "effective_effort": client.effective_effort,
        })
        return 0
    except Exception as exc:
        try:
            _write_result(result_path, {
                "ok": False,
                "error": "%s: %s" % (type(exc).__name__, str(exc)),
                "trace": trace,
                "effective_model": getattr(client, "effective_model", None),
                "effective_effort": getattr(client, "effective_effort", None),
            })
        except Exception:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
