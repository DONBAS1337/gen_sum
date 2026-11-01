# -*- coding: utf-8 -*-
"""Local-only ComfyUI /prompt -> /history -> /view image bridge.

No Python package dependencies, no credentials, no arbitrary URLs and no
assumptions that Anima is SD1.5: exports of actual Anima workflows in API format
are required. Works in Ren'Py's bundled Python 2.7 or Python 3.
"""
from __future__ import unicode_literals
import copy
import json
import os
import time
import uuid
import sys

try:
    from urllib.request import Request, urlopen
    from urllib.parse import urlencode, urlsplit
except ImportError:
    from urllib2 import Request, urlopen
    from urllib import urlencode
    from urlparse import urlsplit

class ComfyError(Exception):
    pass

def _base(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in ("localhost","127.0.0.1")
            or parsed.username is not None or parsed.password is not None
            or parsed.port != 8188 or parsed.path not in ("","/")
            or parsed.query or parsed.fragment):
        raise ComfyError("ComfyUI address is restricted to http://127.0.0.1:8188")
    return "http://127.0.0.1:8188"

def _read(url, data=None, maxbytes=33554432, timeout=20):
    if data is not None:
        if not isinstance(data, bytes):
            data=json.dumps(data,ensure_ascii=True).encode("utf-8")
        request=Request(url,data,{"Content-Type":"application/json"})
    else:
        request=Request(url)
    response=urlopen(request,timeout=timeout)
    try:
        body=response.read(maxbytes+1)
    finally:
        response.close()
    if len(body)>maxbytes:
        raise ComfyError("ComfyUI returned an oversized response")
    return body

def _json(url, data=None):
    raw=_read(url,data,maxbytes=2*1024*1024,timeout=30)
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError,UnicodeDecodeError):
        raise ComfyError("Unexpected JSON response from ComfyUI")

def prepare_workflow(document, prompt, negative_prompt="", seed=None):
    """Replace explicit tokens, or ONE unambiguous CLIPTextEncode positive node."""
    if not isinstance(document,dict):
        raise ComfyError("Workflow must be an API JSON object")
    payload=copy.deepcopy(document.get("prompt",document))
    if "nodes" in payload and isinstance(payload["nodes"],list):
        raise ComfyError("Export workflow using 'Save (API Format)', not the UI format")
    if not payload or not all(isinstance(v,dict) and "class_type" in v and
                              isinstance(v.get("inputs"),dict) for v in payload.values()):
        raise ComfyError("Invalid ComfyUI API workflow")
    if seed is None:
        seed=uuid.uuid4().int % (2**32)
    count=[0]
    def replace(value):
        if isinstance(value,dict):
            return dict((key,replace(v)) for key,v in value.items())
        if isinstance(value,list):
            return [replace(v) for v in value]
        if isinstance(value,str if str is not bytes else bytes):
            if "__DG_PROMPT__" in value:
                count[0]+=1
                value=value.replace("__DG_PROMPT__",prompt)
            value=value.replace("__DG_NEGATIVE__",negative_prompt)
            value=value.replace("__DG_SEED__",str(seed))
            return value
        try:
            if isinstance(value,unicode):
                if u"__DG_PROMPT__" in value:
                    count[0]+=1
                    value=value.replace(u"__DG_PROMPT__",prompt)
                return value.replace(u"__DG_NEGATIVE__",negative_prompt).replace(u"__DG_SEED__",str(seed))
        except NameError:
            pass
        return value
    payload=replace(payload)
    # Anima KSampler uses a NUMBER seed. No text placeholder is required.
    # Patch numeric fields only, preserving other model/graph inputs.
    for node in payload.values():
        if node.get("class_type") in ("KSampler", "KSamplerAdvanced"):
            previous = node["inputs"].get("seed")
            if isinstance(previous, (int, long)) if sys.version_info[0] < 3 else isinstance(previous, int):
                node["inputs"]["seed"] = int(seed)
    if count[0] == 0:
        # Avoid corrupting multi-encoder/subgraph workflows.
        candidates=[node for node in payload.values()
                    if node.get("class_type")=="CLIPTextEncode" and
                       isinstance(node["inputs"].get("text"),type(prompt))]
        if len(candidates)!=1:
            raise ComfyError("Place __DG_PROMPT__ in exactly one text field of the exported workflow")
        candidates[0]["inputs"]["text"]=prompt
    return payload

def probe(base_url="http://127.0.0.1:8188"):
    base=_base(base_url)
    info=_json(base+"/system_stats")
    return isinstance(info,dict) and ("system" in info or "devices" in info)

def generate(workflow_path,prompt,kind,base_url="http://127.0.0.1:8188",
             negative_prompt="",timeout_seconds=300,poll_seconds=1):
    if kind not in ("background","cg","cg18"):
        raise ComfyError("Unsupported asset kind")
    if not isinstance(timeout_seconds,int) or not 10<=timeout_seconds<=900:
        raise ComfyError("Timeout must be 10..900 seconds")
    base=_base(base_url)
    if not os.path.isfile(workflow_path):
        raise ComfyError("Save an API-format Anima workflow at: "+workflow_path)
    if os.path.getsize(workflow_path)>1024*1024:
        raise ComfyError("Workflow JSON is too large")
    try:
        with open(workflow_path,"rb") as fh:
            source=json.loads(fh.read().decode("utf-8"))
    except (IOError,ValueError,UnicodeDecodeError):
        raise ComfyError("Cannot parse the exported workflow JSON")
    api=prepare_workflow(source,prompt,negative_prompt)
    queued=_json(base+"/prompt",{"prompt":api,"client_id":uuid.uuid4().hex})
    if not isinstance(queued,dict) or not queued.get("prompt_id"):
        raise ComfyError("ComfyUI rejected workflow: "+repr(queued.get("node_errors") or queued.get("error"))[:700])
    request_id=queued["prompt_id"]
    if not isinstance(request_id,str if str is not bytes else bytes):
        try:
            if not isinstance(request_id,unicode):
                raise ComfyError("Invalid prompt ID")
        except NameError:
            raise ComfyError("Invalid prompt ID")
    import re
    if not re.match(r"^[0-9a-fA-F-]{20,80}$",request_id):
        raise ComfyError("Invalid ComfyUI prompt ID")
    deadline=time.time()+timeout_seconds
    while time.time()<deadline:
        reply=_json(base+"/history/"+request_id)
        if request_id in reply:
            entry=reply[request_id]
            status=entry.get("status",{})
            if status.get("status_str")=="error":
                raise ComfyError("ComfyUI workflow failed: "+repr(status.get("messages",[]))[-600:])
            for node_output in entry.get("outputs",{}).values():
                for item in node_output.get("images",[]):
                    if item.get("type","output")!="output":
                        continue
                    name=item.get("filename","")
                    folder=item.get("subfolder","")
                    if not isinstance(name,str) or not name.endswith(".png"):
                        continue
                    if "/" in name or "\\" in name or ".." in name:
                        continue
                    if not isinstance(folder,str) or ".." in folder or "\\" in folder:
                        continue
                    query=urlencode({"filename":name,"subfolder":folder,"type":"output"})
                    data=_read(base+"/view?"+query,maxbytes=32*1024*1024,timeout=45)
                    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                        raise ComfyError("Use SaveImage with PNG output, not JPEG/WebP")
                    return data
            raise ComfyError("No PNG SaveImage output found. Export a workflow ending in SaveImage.")
        time.sleep(poll_seconds)
    raise ComfyError("ComfyUI timeout; inspect its queue and history at http://127.0.0.1:8188")
