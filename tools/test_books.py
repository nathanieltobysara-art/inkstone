#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""书稿层压测：造一本 30 万字 60 章的书，验证导入/检索/定位/导出。"""
import os
import random
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import books  # noqa: E402

TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_bench_data")
books.init(TMP, threading.Lock())

NAMES = ["林昭", "沈砚", "陆无咎", "苏晚棠", "裴聿", "谢云峥", "顾清和", "白露"]
PLACES = ["青崖城", "落雁关", "寒山寺", "不夜楼", "听雪阁"]
SENT = [
    "他抬眼看向檐下的雨，没有说话。",
    "刀锋擦过石阶，溅起一串火星。",
    "那封信在她袖中，压得人喘不过气。",
    "风从北边来，带着铁锈和雪的味道。",
    "“你早就知道了。”她说。",
    "灯芯爆了一下，屋里忽然安静。",
    "他把酒盏推过去，指节泛白。",
    "远处传来三声更鼓。",
]


def make_chapter(n):
    rnd = random.Random(n)
    parts = ["第%d章　%s" % (n, rnd.choice(["雨夜", "断刀", "旧信", "长街", "灯下", "雪落"]))]
    size = 0
    while size < 5000:
        s = rnd.choice(SENT)
        if rnd.random() < 0.25:
            s = "%s在%s的%s。" % (rnd.choice(NAMES), rnd.choice(PLACES), rnd.choice(["巷口", "楼上", "阶前", "渡口"]))
        parts.append(s)
        size += len(s)
    return "\n".join(parts)


def build_text():
    out = ["林昭传", ""]
    for i in range(1, 61):
        out.append(make_chapter(i))
        out.append("")
    return "\n".join(out)


def main():
    t0 = time.time()
    text = build_text()
    print("造稿：%d 字，%.2fs" % (len(text), time.time() - t0))

    t0 = time.time()
    res = books.import_book("林昭传", text, "武侠")
    bid = res["book"]["id"]
    print("导入：%d 章，%.2fs" % (res["chapters"], time.time() - t0))

    t0 = time.time()
    books.build_index(bid, force=True)
    print("建索引：%.2fs" % (time.time() - t0))

    t0 = time.time()
    hits = books.search(bid, "林昭 断刀", 5)
    print("检索：%d 条，%.3fs" % (len(hits), time.time() - t0))
    for h in hits[:3]:
        print("   第%d章 %s | %.2f | %s" % (h["no"], h["title"], h["score"], h["snippet"][:50]))

    t0 = time.time()
    loc = books.locate(bid, "陆无咎")
    print("定位：首次=第%d章，共%d次，%.3fs" % (
        loc["first"]["no"] if loc["first"] else -1, loc["total"], time.time() - t0))

    ov = books.book_overview(bid)
    print("概览：%d 章 / %d 字 / %d 卷" % (
        ov["stats"]["chapters"], ov["stats"]["words"], ov["stats"]["volumes"]))

    t0 = time.time()
    ctx = books.context_for(bid, ov["chapters"][30]["id"], "林昭 旧信", 6000)
    print("上下文：%d 字，%.3fs" % (len(ctx), time.time() - t0))

    t0 = time.time()
    fn, data = books.export_book(bid, "md", False)
    print("导出 md：%s，%d 字节，%.3fs" % (fn, len(data), time.time() - t0))
    fn, data = books.export_book(bid, "txt", True)
    print("导出分章 zip：%s，%d 字节" % (fn, len(data)))

    t0 = time.time()
    rh = books.check_rhythm(bid)
    print("节奏分析：%d 章，%.2fs，首章对话占比 %.1f%%" % (
        len(rh), time.time() - t0, rh[0]["dialogue"] * 100))

    t0 = time.time()
    names = books.scan_names(bid, 10)
    print("抽名：%d 个，%.2fs，前三个 %s" % (
        len(names), time.time() - t0, [x["name"] for x in names[:3]]))

    # 快照
    cid = ov["chapters"][0]["id"]
    books.write_chapter(bid, cid, "改过的正文", snapshot=True)
    print("快照：%d 份" % len(books.list_snapshots(bid, cid)))

    print("\n目录占用：")
    total = 0
    for root, _d, files in os.walk(books.bdir(bid)):
        for f in files:
            total += os.path.getsize(os.path.join(root, f))
    print("  %.1f MB" % (total / 1024 / 1024))
    print("\nbookId =", bid)


if __name__ == "__main__":
    main()
