#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""造一本用于界面预览的样书，直接写进 data/books。"""
import os
import random
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import books  # noqa: E402

books.init(os.path.join(ROOT, "data"), threading.Lock())

NAMES = ["林昭", "沈砚", "陆无咎", "苏晚棠"]
PLACES = ["青崖城", "落雁关", "听雪阁", "不夜楼"]

PARAS = [
    "雨下了三天。{p}的青石板被泡得发亮，檐角的水连成一条线，砸在阶前，溅起细碎的白。",
    "{a}站在廊下，看着街对面那扇关着的门。门上的铜环生了绿锈，没人碰过。",
    "“你来晚了。”{b}的声音从身后传来，很轻，像怕惊动什么。",
    "{a}没有回头。“路上有人跟着。”",
    "“几个人？”",
    "“三个。两个在城门口就散了，剩下一个，一直跟到{p}。”",
    "{b}沉默了一会儿，把手里那盏灯往前递了递。灯光照到{a}的半边脸，另外半边还在暗里。",
    "远处传来三声更鼓。风从北边来，带着铁锈和雪的味道。",
    "刀锋擦过石阶，溅起一串火星。",
    "{a}低头看了一眼自己的手。指节上有一道旧疤，是七年前留下的，到现在还没褪干净。",
    "“东西还在你身上？”{b}问。",
    "“在。”",
    "“那就别在这儿站着。”{b}转身往里走，走了两步又停下，“{c}也在。”",
    "{a}终于抬起了头。",
    "屋里的灯芯爆了一下，忽然安静下来。{c}坐在最里面的位置，面前放着一只空碗，碗底朝天。",
    "“七年了。”{c}说，“你还敢回来。”",
    "这句话说出来的时候，没有人接。雨声忽然大了，把剩下的都盖住了。",
    "{a}把刀解下来，放在桌上。刀鞘上有一道裂痕，从中间一直裂到尾端。",
    "“我不是回来叙旧的。”",
    "“那你回来做什么？”",
    "“{d}。”",
    "这个名字一出口，{c}的手停在了半空。",
    "灯又爆了一下。这一次，屋里所有人都听见了。",
]


def make_chapter(n):
    rnd = random.Random(n * 37)
    parts = ["第%d章　%s" % (n, rnd.choice(["雨夜", "断刀", "旧信", "长街", "灯下", "雪落", "归人"]))]
    size = 0
    while size < 2800:
        p = rnd.choice(PARAS).format(
            a=rnd.choice(NAMES), b=rnd.choice([x for x in NAMES if True]),
            c=rnd.choice(NAMES), d=rnd.choice(NAMES), p=rnd.choice(PLACES))
        parts.append(p)
        size += len(p)
    return "\n\n".join(parts)


def main():
    text = "\n\n".join(make_chapter(i) for i in range(1, 13))
    res = books.import_book("长夜将尽", text, "武侠")
    bid = res["book"]["id"]
    ov = books.book_overview(bid)
    chs = ov["chapters"]

    # 分三卷
    b = books.get_book(bid)
    v1 = b["volumes"][0]
    v1["title"] = "第一卷　雨夜"
    v2 = {"id": "v2", "title": "第二卷　断刀", "chapters": v1["chapters"][4:8]}
    v3 = {"id": "v3", "title": "第三卷　归人", "chapters": v1["chapters"][8:]}
    v1["chapters"] = v1["chapters"][:4]
    b["volumes"] = [v1, v2, v3]
    b["logline"] = "一个七年前该死的人回到青崖城，只为取回一件不该存在的东西。"
    b["genre"] = "武侠 / 悬疑"
    books.save_book(b)

    bible = books.load_bible(bid)
    bible["world"] = (
        "青崖城，北地边城，常年多雨。\n"
        "城里只有一条主街，从城门直通听雪阁。\n"
        "江湖上有一条不成文的规矩：进了听雪阁的门，刀要留在外面。"
    )
    bible["characters"] = [
        {"name": "林昭", "aliases": ["昭儿"], "age": "二十七", "gender": "男",
         "identity": "前青崖城捕快，七年前被除名",
         "appearance": "左眉有一道浅疤，常年穿一件洗得发白的旧袍，右手食指有道旧伤，握刀时会抖。",
         "personality": "话极少，能用一个字答的不用两个。怕欠人情，宁可自己吃亏。底线是不杀女人和孩子。",
         "speech": "短句。从不用敬称，对谁都直呼其名。被逼急了会说反话。",
         "faction": "无",
         "relations": [{"to": "沈砚", "type": "旧识", "note": "七年前替他顶了罪"},
                       {"to": "陆无咎", "type": "敌对", "note": "杀父之仇未报"},
                       {"to": "苏晚棠", "type": "亏欠", "note": "答应过带她走，没做到"}],
         "notes": "刀鞘上的裂痕是七年前那晚留下的。"},
        {"name": "沈砚", "aliases": [], "age": "三十一", "gender": "男",
         "identity": "听雪阁掌灯人",
         "appearance": "瘦高，右手常年提一盏铜灯。指甲修得很干净。",
         "personality": "面上温和，心里记账。从不撒谎，但只说一半。",
         "speech": "语速慢，爱用「你」不用「您」，说完常停半拍。",
         "faction": "听雪阁",
         "relations": [{"to": "林昭", "type": "旧识", "note": ""},
                       {"to": "苏晚棠", "type": "上下级", "note": ""}],
         "notes": "知道七年前的真相，但一直没说。"},
        {"name": "陆无咎", "aliases": ["陆爷"], "age": "四十五", "gender": "男",
         "identity": "落雁关守将，掌北境三城兵权",
         "appearance": "鬓角全白，左手缺一根小指。",
         "personality": "极有耐心，能等十年。不信任何人，包括自己人。",
         "speech": "说话像下命令，句末从不上扬。偶尔引用兵书。",
         "faction": "北境军",
         "relations": [{"to": "林昭", "type": "敌对", "note": "杀其父"}],
         "notes": ""},
        {"name": "苏晚棠", "aliases": ["阿棠"], "age": "二十三", "gender": "女",
         "identity": "听雪阁说书人",
         "appearance": "总穿一身青，头上只插一支木簪。",
         "personality": "记性极好，听过一遍的事不会忘。嘴上不饶人。",
         "speech": "爱用反问句。说书时换一副嗓子。",
         "faction": "听雪阁",
         "relations": [{"to": "林昭", "type": "旧识", "note": "等了他七年"}],
         "notes": ""},
    ]
    bible["factions"] = [
        {"name": "听雪阁", "type": "情报行当", "goal": "买卖消息，不站队", "members": "沈砚、苏晚棠"},
        {"name": "北境军", "type": "军镇", "goal": "守住落雁关", "members": "陆无咎"},
    ]
    bible["items"] = [
        {"name": "断刀", "owner": "林昭", "desc": "刀鞘有裂，刀身有七处缺口。缺的第八处，是七年前那一刀。"},
        {"name": "铜灯", "owner": "沈砚", "desc": "灯芯烧了七年没换过。"},
    ]
    bible["foreshadow"] = [
        {"title": "刀鞘上的裂痕", "plantChapter": "1", "payoffChapter": "12", "status": "open",
         "note": "裂痕是七年前那晚留下的，最后一章要交代是谁砍的"},
        {"title": "沈砚的铜灯", "plantChapter": "2", "payoffChapter": "", "status": "open",
         "note": "灯芯七年没换，暗示他在等一个人"},
        {"title": "陆无咎缺的那根小指", "plantChapter": "5", "payoffChapter": "", "status": "open",
         "note": "还没想好怎么收"},
    ]
    bible["terms"] = [
        {"main": "林昭", "aliases": ["昭儿", "小林"], "type": "person"},
        {"main": "沈砚", "aliases": [], "type": "person"},
        {"main": "青崖城", "aliases": ["青崖"], "type": "place"},
    ]
    bible["timeline"] = [
        {"when": "七年前·冬", "chapterId": chs[0]["id"], "event": "林昭被除名，离开青崖城"},
        {"when": "现在·春", "chapterId": chs[0]["id"], "event": "林昭回到青崖城"},
    ]
    books.save_bible(bid, bible)

    for c in chs[:3]:
        books.write_chapter(bid, c["id"], books.read_chapter(bid, c["id"])["text"],
                            title=None, snapshot=False)

    books.save_outline(bid, "chapter", chs[0]["id"],
                       "1. 林昭雨夜回城，沈砚在听雪阁等他\n2. 提到「东西还在你身上」\n3. 章末：陆无咎的名字第一次被说出来")
    books.save_outline(bid, "book", "",
                       "# 全书结构\n\n"
                       "## 第一卷 雨夜（1-4）\n林昭回城，与沈砚重逢，暴露行踪。\n\n"
                       "## 第二卷 断刀（5-8）\n陆无咎出手，七年前的真相露出一角。\n\n"
                       "## 第三卷 归人（9-12）\n刀鞘裂痕的来历揭开，林昭做出选择。")

    ov = books.book_overview(bid)
    print("bookId =", bid)
    print("章数 =", ov["stats"]["chapters"], "字数 =", ov["stats"]["words"])
    print("卷 =", [v["title"] for v in ov["book"]["volumes"]])


if __name__ == "__main__":
    main()
