#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""书稿 API 端到端测试。需要先启动 server.py（端口从 argv 取）。"""
import base64
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:%s" % (sys.argv[1] if len(sys.argv) > 1 else "8791")
ok = fail = 0


def call(method, path, body=None):
    data = json.dumps(body, ensure_ascii=False).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return json.loads(e.read().decode() or "{}")


def check(name, cond, extra=""):
    global ok, fail
    if cond:
        ok += 1
        print("  ✓ %s %s" % (name, extra))
    else:
        fail += 1
        print("  ✗ %s %s" % (name, extra))


print("== 新建 / 章节 ==")
b = call("POST", "/api/books", {"title": "端到端测试", "genre": "武侠"})
bid = b.get("id")
check("建书", bool(bid), bid)

r = call("POST", "/api/books/%s/chapters" % bid, {"title": "第一章 试笔"})
cid = r.get("id")
check("建章", bool(cid), cid)

text = "林昭推开门，雨声涌进来。\n\n“你来晚了。”沈砚说。\n\n他没答话，把刀放在桌上。"
r = call("PUT", "/api/books/%s/chapters/%s" % (bid, cid), {"text": text})
check("保存正文", r.get("ok") and r.get("words", 0) > 0, "words=%s" % r.get("words"))

r = call("GET", "/api/books/%s/chapters/%s" % (bid, cid))
check("读回正文", r.get("text") == text)

r = call("PUT", "/api/books/%s/chapters/%s" % (bid, cid), {"text": text + "\n\n他抬起头。"})
check("二次保存触发快照", r.get("ok"))
r = call("GET", "/api/books/%s/snapshots/%s" % (bid, cid))
snaps = r.get("snapshots") or []
check("快照列表", len(snaps) >= 1, "%d 份" % len(snaps))
if snaps:
    r = call("GET", "/api/books/%s/snapshots/%s/%s" % (bid, cid, snaps[0]["ts"]))
    check("读快照", "林昭推开门" in (r.get("text") or ""))
    r = call("POST", "/api/books/%s/restore" % bid, {"chapterId": cid, "ts": snaps[0]["ts"]})
    check("回退快照", r.get("ok"))

print("== 检索 ==")
for i in range(2, 6):
    r = call("POST", "/api/books/%s/chapters" % bid, {"title": "第%d章" % i})
    call("PUT", "/api/books/%s/chapters/%s" % (bid, r["id"]),
         {"text": "第%d章正文。沈砚在落雁关等林昭。刀锋擦过石阶。" % i})
r = call("POST", "/api/books/%s/search" % bid, {"query": "沈砚 落雁关", "k": 5})
hits = r.get("hits") or []
check("BM25 检索", len(hits) > 0, "%d 条，首条第%s章" % (len(hits), hits[0]["no"] if hits else "-"))
r = call("POST", "/api/books/%s/locate" % bid, {"name": "沈砚"})
check("实体定位", r.get("total", 0) > 0, "共 %s 次，首见第 %s 章" % (
    r.get("total"), (r.get("first") or {}).get("no")))

print("== 设定库 ==")
bible = {"characters": [{"name": "林昭", "identity": "捕快", "personality": "寡言",
                         "aliases": ["昭儿"], "relations": [{"to": "沈砚", "type": "旧识", "note": ""}]}],
         "terms": [{"main": "林昭", "aliases": ["昭儿", "小林"], "type": "person"}],
         "foreshadow": [{"title": "刀上的刻痕", "plantChapter": "1", "status": "open"}],
         "world": "青崖城，雨水多。"}
r = call("PUT", "/api/books/%s/bible" % bid, bible)
check("保存设定库", len((r.get("bible") or {}).get("characters", [])) == 1)
r = call("GET", "/api/books/%s" % bid)
ov = r
check("概览统计", ov.get("stats", {}).get("characters") == 1,
      "%s 章 / %s 字" % (ov["stats"]["chapters"], ov["stats"]["words"]))

print("== 纯程序校验 ==")
r = call("POST", "/api/books/%s/check" % bid, {"kind": "terms"})
check("名词统一", "result" in r, "%d 处混用" % len((r.get("result") or {}).get("issues", [])))
r = call("POST", "/api/books/%s/check" % bid, {"kind": "rhythm"})
check("节奏统计", len(r.get("chapters") or []) > 0)
r = call("POST", "/api/books/%s/check" % bid, {"kind": "foreshadow"})
check("伏笔检查", len(r.get("items") or []) == 1)
r = call("POST", "/api/books/%s/names" % bid, {"limit": 10})
check("抽人名", "names" in r, str([x["name"] for x in (r.get("names") or [])[:3]]))

print("== 大纲 / 排序 ==")
r = call("PUT", "/api/books/%s/outline" % bid, {"scope": "chapter", "key": cid, "text": "开篇要冷"})
check("存章节提纲", r.get("ok"))
r = call("GET", "/api/books/%s/chapters/%s" % (bid, cid))
check("提纲读回", r.get("outline") == "开篇要冷")

ov = call("GET", "/api/books/%s" % bid)
vols = ov["book"]["volumes"]
first = vols[0]["chapters"].pop(0)
vols[0]["chapters"].append(first)
r = call("PATCH", "/api/books/%s" % bid, {"volumes": vols})
check("拖拽排序持久化", r.get("ok") and r["book"]["volumes"][0]["chapters"][-1]["id"] == first["id"])

print("== 导出 ==")
r = call("POST", "/api/books/%s/export" % bid, {"format": "md"})
check("导出 md", bool(r.get("data")), "%s 字节" % len(base64.b64decode(r.get("data") or "")))
r = call("POST", "/api/books/%s/export" % bid, {"format": "txt", "split": True})
check("导出分章 zip", (r.get("filename") or "").endswith(".zip"), r.get("filename"))

print("== 整本导入 ==")
book_text = "\n\n".join("第%d章　标题%d\n\n%s" % (i, i, "林昭走在长街上。" * 60) for i in range(1, 9))
r = call("POST", "/api/books", {
    "title": "导入测试", "filename": "novel.txt",
    "data": base64.b64encode(book_text.encode()).decode(),
})
check("导入整本", r.get("chapters") == 8, "%s 章" % r.get("chapters"))
bid2 = (r.get("book") or {}).get("id")
r = call("GET", "/api/books/%s" % bid2)
check("导入后可读", r["stats"]["chapters"] == 8)

print("== 清理 ==")
call("DELETE", "/api/books/%s" % bid)
call("DELETE", "/api/books/%s" % bid2)
r = call("GET", "/api/books")
check("删除生效", all(x["id"] not in (bid, bid2) for x in r.get("books") or []))

print("\n结果：%d 通过，%d 失败" % (ok, fail))
sys.exit(1 if fail else 0)
