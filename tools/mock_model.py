#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开发用：本地模拟 OpenAI 兼容流式接口。

支持三种行为（按最后一条用户消息里的标记触发）：
  __trunc__  正常输出后以 finish_reason=length 结束（模拟达到 max_tokens）
  __drop__   输出几段后直接断开连接（模拟本地服务中途挂掉）
  其他        正常以 finish_reason=stop 结束
"""
import json
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BODY = """## 第一章控制卡

**必须改变的事**：沈砚从「旁观者」变成「局中人」。

| 项目 | 内容 |
| --- | --- |
| 推进主线 | 密卷失窃案第一次浮出水面 |
| 回收债务 | 第三章埋下的铜钥匙 |

### 场景清单

1. **雨夜验尸房**：目标——确认死者身份；阻碍——仵作不肯开口。
2. **长廊对质**：目标——套出值班记录；阻碍——对方是他旧友。

> 写作提示：不要写他「心中一惊」，写他手上的灯晃了一下。
"""


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n)
        try:
            req = json.loads(raw.decode("utf-8"))
        except Exception:
            req = {}
        msgs = req.get("messages") or []
        last = ""
        for m in reversed(msgs):
            if m.get("role") == "user":
                last = m.get("content") or ""
                break
        mode = "trunc" if "__trunc__" in last else ("drop" if "__drop__" in last else "ok")

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()

        def send(obj):
            self.wfile.write(("data: " + json.dumps(obj, ensure_ascii=False) + "\n\n").encode("utf-8"))
            self.wfile.flush()

        try:
            step = 8
            limit = len(BODY) if mode != "drop" else 60
            for i in range(0, limit, step):
                send({"id": "demo", "object": "chat.completion.chunk",
                      "choices": [{"index": 0, "delta": {"content": BODY[i:i + step]},
                                   "finish_reason": None}]})
                time.sleep(0.012)
            if mode == "drop":
                self.close_connection = True
                try:
                    self.wfile.flush()
                    self.connection.close()
                except Exception:
                    pass
                return
            send({"id": "demo", "object": "chat.completion.chunk",
                  "choices": [{"index": 0, "delta": {},
                               "finish_reason": "length" if mode == "trunc" else "stop"}]})
            self.wfile.write(b"data: [DONE]\n\n")
            self.wfile.flush()
        except Exception:
            pass
        self.close_connection = True


if __name__ == "__main__":
    print("mock model on http://127.0.0.1:8899/v1  (__trunc__ / __drop__)")
    ThreadingHTTPServer(("127.0.0.1", 8899), H).serve_forever()
