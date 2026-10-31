#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开发用假模型：按 system 提示词返回对应形状的回答，用来验证书稿 AI 链路。

启动：python tools/mock_llm.py [port]
接口：POST /v1/chat/completions （OpenAI 兼容，流式）
"""
import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LAST = {"system": "", "user": ""}


def reply(system, user):
    if "人物一致性审校" in system:
        return json.dumps({
            "issues": [
                {"level": "high", "character": "林昭", "type": "台词",
                 "quote": "“那就别在这儿站着。”",
                 "why": "档案写他「话极少，能用一个字答的不用两个」，“那就别在这儿站着”是七个字的长句，且带指令语气，更像沈砚。",
                 "fix": "改成“走。”或者删掉，让他只是转身。"},
                {"level": "mid", "character": "林昭", "type": "能力",
                 "quote": "刀锋擦过石阶，溅起一串火星",
                 "why": "档案写他右手食指有旧伤、握刀会抖，此处描写像毫不用力。",
                 "fix": "加一句手抖的细节，或者改成左手。"},
            ]
        }, ensure_ascii=False)

    if "章节摘要" in system:
        return json.dumps({
            "summary": "林昭在雨夜回到青崖城，进听雪阁见沈砚。沈砚问他东西还在不在，并告知陆无咎也在场。陆无咎提起七年前旧事，林昭说出一个名字，屋里所有人变色。",
            "events": ["林昭雨夜回城", "沈砚试探东西是否还在", "陆无咎出场", "林昭说出关键人名"],
            "characters": ["林昭", "沈砚", "陆无咎", "苏晚棠"],
            "hooks": ["刀鞘上的裂痕", "沈砚七年没换的灯芯"],
            "payoff": [],
        }, ensure_ascii=False)

    if "人物关系图" in system:
        return json.dumps({
            "nodes": [
                {"id": "林昭", "group": "无", "note": "前捕快"},
                {"id": "沈砚", "group": "听雪阁", "note": "掌灯人"},
                {"id": "陆无咎", "group": "北境军", "note": "落雁关守将"},
                {"id": "苏晚棠", "group": "听雪阁", "note": "说书人"},
            ],
            "edges": [
                {"from": "林昭", "to": "沈砚", "type": "旧识", "note": "七年前替他顶罪", "weight": 5},
                {"from": "林昭", "to": "陆无咎", "type": "敌对", "note": "杀父之仇", "weight": 5},
                {"from": "林昭", "to": "苏晚棠", "type": "旧识", "note": "答应带她走", "weight": 4},
                {"from": "沈砚", "to": "苏晚棠", "type": "上下级", "note": "", "weight": 2},
                {"from": "陆无咎", "to": "沈砚", "type": "敌对", "note": "互相提防", "weight": 3},
            ],
        }, ensure_ascii=False)

    if "剧情分支推演" in system:
        return json.dumps({
            "branches": [
                {"title": "林昭当场拔刀", "logic": "他七年来第一次被人当面提起父亲，压不住。",
                 "scene": "刀出鞘三寸，沈砚的灯横在中间。灯灭了，屋里只剩雨声。陆无咎没动，只说了一句“你果然还是这样”。",
                 "cost": "暴露实力，北境军当晚封城。",
                 "foreshadow": {"recover": ["刀鞘上的裂痕"], "new": ["沈砚为什么拦他"]},
                 "score": 3},
                {"title": "林昭认下这个名字", "logic": "他回来就是为了让人知道他在。",
                 "scene": "他把刀推回鞘里，说了第二遍那个名字。这一次，苏晚棠手里的碗掉了。",
                 "cost": "听雪阁被迫选边，沈砚七年中立经营毁于一旦。",
                 "foreshadow": {"recover": ["沈砚的铜灯"], "new": ["苏晚棠为什么失手"]},
                 "score": 5},
                {"title": "什么都不说，转身走", "logic": "他还没准备好，先退。",
                 "scene": "林昭拿起刀，走到门口停了一下，没有回头。雨里有人撑伞等他。",
                 "cost": "读者会觉得憋屈，必须下一章立刻给补偿。",
                 "foreshadow": {"recover": [], "new": ["撑伞的人是谁"]},
                 "score": 2},
            ]
        }, ensure_ascii=False)

    if "卷梗概" in system:
        return ("第一卷写林昭回城。他带着一把裂了鞘的刀进听雪阁，与沈砚重逢，"
                "撞上陆无咎。七年前的旧案被重新提起，三方势力在雨夜里各自试探。"
                "卷末林昭说出那个名字，把自己从暗处推到了明处。")

    if "整本书写梗概" in system:
        return ("一个七年前被除名的捕快回到边城，只为取回一件不该存在的东西。"
                "他先遇上旧友沈砚，再撞上杀父仇人陆无咎。刀鞘上的裂痕牵出当年那晚的真相，"
                "而真相的代价是让所有护过他的人都站到刀口上。")

    # 默认：当成续写正文
    return ("雨还没停。\n\n"
            "林昭把刀鞘横在膝上，拇指反复摩挲那道裂痕。裂口很浅，指腹划过去几乎感觉不到，"
            "可他知道它在。\n\n"
            "“你手在抖。”沈砚说。\n\n"
            "“冷。”\n\n"
            "沈砚没再问，把铜灯往他那边推了半寸。灯芯烧得很稳，七年没换过，"
            "火苗低得像是随时会灭，却一直没灭。\n\n"
            "街对面传来脚步声，两个人，一轻一重。轻的那个在跳着走。")


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        try:
            body = json.loads(raw.decode("utf-8"))
        except Exception:
            body = {}
        msgs = body.get("messages") or []
        system = "\n".join(m.get("content", "") for m in msgs if m.get("role") == "system")
        user = "\n".join(m.get("content", "") for m in msgs if m.get("role") == "user")
        LAST["system"] = system
        LAST["user"] = user
        with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_mock_last.json"), "w", encoding="utf-8") as f:
            json.dump({"system_len": len(system), "user_len": len(user),
                       "system_head": system[:600]}, f, ensure_ascii=False, indent=1)

        text = reply(system, user)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            step = 24
            for i in range(0, len(text), step):
                obj = {"choices": [{"delta": {"content": text[i:i + step]},
                                    "finish_reason": None}]}
                self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
                self.wfile.flush()
                time.sleep(0.005)
            self.wfile.write(("data: " + json.dumps(
                {"choices": [{"delta": {}, "finish_reason": "stop"}]}) + "\n\n").encode("utf-8"))
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception:
            pass
        self.close_connection = True

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    print("mock llm on", port)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
