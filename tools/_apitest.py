#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开发用：验证截断 / 续写 / 断流三条路径。"""
import json
import os
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import server as engine  # noqa: E402

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
mock = subprocess.Popen([sys.executable, os.path.join(HERE, "mock_model.py")])
srv, port = engine.serve_in_thread(0)
base = "http://127.0.0.1:%d" % port
time.sleep(1.2)


def get(path):
    return json.load(op.open(base + path, timeout=30))


def post(path, obj):
    req = urllib.request.Request(base + path, data=json.dumps(obj).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    return op.open(req, timeout=90)


def events(raw):
    out = []
    for block in raw.split("\n\n"):
        ev, data = None, None
        for line in block.split("\n"):
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                data = line[5:].strip()
        if ev and data:
            out.append((ev, json.loads(data)))
    return out


try:
    cfg = get("/api/bootstrap")["config"]
    if not any(p["id"] == "demo" for p in cfg["providers"]):
        cfg["providers"].append({"id": "demo", "name": "演示模型", "kind": "openai",
                                 "baseUrl": "http://127.0.0.1:8899/v1", "apiKey": "demo",
                                 "model": "demo", "models": ["demo"]})
    cfg["activeProviderId"] = "demo"
    post("/api/config", cfg)

    # ---- A 截断
    conv = json.load(post("/api/conversations", {"skillId": "novel-engine"}))
    cid = conv["id"]
    raw = post("/api/chat", {"conversationId": cid, "skillId": "novel-engine",
                             "content": "帮我写一章 __trunc__"}).read().decode()
    evs = events(raw)
    done = [d for e, d in evs if e == "done"][0]
    print("A 截断:", "finish=%s truncated=%s chars=%s" % (done["finish"], done["truncated"], done["chars"]))

    # ---- B 续写
    raw = post("/api/chat", {"conversationId": cid, "skillId": "novel-engine",
                             "continue": True}).read().decode()
    done2 = [d for e, d in events(raw) if e == "done"][0]
    saved = get("/api/conversations/" + cid)
    last = saved["messages"][-1]
    print("B 续写:", "continue=%s finish=%s 总字数=%d 消息数=%d" % (
        done2.get("continue"), done2["finish"], len(last["content"]), len(saved["messages"])))

    # ---- C 断流
    conv2 = json.load(post("/api/conversations", {"skillId": "novel-engine"}))
    cid2 = conv2["id"]
    raw = post("/api/chat", {"conversationId": cid2, "skillId": "novel-engine",
                             "content": "写一段 __drop__"}).read().decode()
    kinds = [e for e, _ in events(raw)]
    saved2 = get("/api/conversations/" + cid2)
    last2 = saved2["messages"][-1] if saved2["messages"] else {}
    print("C 断流:", "事件=%s 保留=%d字 incomplete=%s" % (
        kinds, len(last2.get("content") or ""), last2.get("incomplete")))
finally:
    mock.terminate()
    srv.shutdown()
