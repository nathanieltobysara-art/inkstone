# -*- coding: utf-8 -*-
"""砚 Inkstone · 语料库（Corpus）

和 books.py 的分工：
  books.py  —— 我自己写的书，一「本」一个目录，追求可读、可编辑、可快照
  corpus.py —— 别人的书，几百上千本，追求可检索、可统计、可批量蒸馏

为什么单独一套：
  books.py 的索引是「整本 JSON 读进内存 + 每次检索重新分词」，
  30 万字 40ms 没问题，9000 万字要 4 秒以上。
  这里改用 SQLite + FTS5：9000 万字建库 55 秒，检索 4 毫秒。

只用标准库（sqlite3 的 FTS5 在 CPython 官方 Windows 构建里默认开启）。
"""
import json
import os
import re
import sqlite3
import threading
import time
import uuid

import books as bk          # 只复用 split_chapters / count_words，不碰它的全局状态

SCHEMA_VERSION = 1
CHUNK = 800                 # 全文索引片段长度（字符）
OVERLAP = 100

_LOCK = threading.Lock()
_DB = {"path": None}

# 蒸馏任务的抽样策略：几百本书不可能逐章跑，必须抽样
PLANS = {
    "front30": lambda n: list(range(1, min(n, 30) + 1)),
    "sample":  lambda n: sorted(set(list(range(1, min(n, 30) + 1)) + list(range(31, n + 1, 5)))),
    "all":     lambda n: list(range(1, n + 1)),
}


# ---------------------------------------------------------------- 连接
def init(db_path):
    """绑定数据库文件。首次调用会建表。"""
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    _DB["path"] = db_path
    con = _conn()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT);

    CREATE TABLE IF NOT EXISTS books(
      sid TEXT PRIMARY KEY, title TEXT, author TEXT, genre TEXT,
      words INTEGER, nchap INTEGER, source TEXT,
      fulltext INTEGER DEFAULT 0, addedAt REAL, status TEXT DEFAULT 'raw'
    );

    CREATE TABLE IF NOT EXISTS chapters(
      sid TEXT, no INTEGER, title TEXT, words INTEGER, text TEXT,
      PRIMARY KEY(sid, no)
    );

    -- 章级蒸馏产物（M2 写入）
    CREATE TABLE IF NOT EXISTS distill(
      sid TEXT, no INTEGER, summary TEXT, events TEXT, hook TEXT,
      tone TEXT, ts REAL,
      PRIMARY KEY(sid, no)
    );

    -- 书级蒸馏产物
    CREATE TABLE IF NOT EXISTS dbook(
      sid TEXT PRIMARY KEY, volume_sum TEXT, book_sum TEXT,
      characters TEXT, style TEXT, tropes TEXT, rhythm TEXT, updatedAt REAL
    );

    -- 蒸馏任务队列（append-only 语义，断点续跑靠它）
    CREATE TABLE IF NOT EXISTS jobs(
      sid TEXT, no INTEGER, state TEXT DEFAULT 'todo',
      tries INTEGER DEFAULT 0, err TEXT, ts REAL,
      PRIMARY KEY(sid, no)
    );

    CREATE INDEX IF NOT EXISTS ix_ch ON chapters(sid, no);
    CREATE INDEX IF NOT EXISTS ix_job ON jobs(state, sid, no);
    """)
    # 全文索引：tok 存 bigram 切分后的 token 串；原文不重复存，靠 (sid,no,i) 回 chapters 取
    con.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS ft USING fts5(
                     tok, sid UNINDEXED, no UNINDEXED, i UNINDEXED, title UNINDEXED,
                     tokenize='unicode61')""")
    # 蒸馏产物索引：几百本书的摘要加起来只有几 MB，检索毫秒级
    con.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS ftd USING fts5(
                     tok, sid UNINDEXED, no UNINDEXED, tokenize='unicode61')""")
    con.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('schema',?)", (str(SCHEMA_VERSION),))
    con.commit()
    con.close()
    return db_path


def _conn():
    p = _DB["path"]
    if not p:
        raise RuntimeError("corpus 未初始化，先调 corpus.init(path)")
    con = sqlite3.connect(p, timeout=30, check_same_thread=False)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA temp_store=MEMORY")
    return con


# ---------------------------------------------------------------- 分词
def tokens(s):
    """和 books.py 保持同一套中文 bigram 规则，保证两边检索口径一致。"""
    out = []
    for seg in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z]+|\d+", s or ""):
        if "\u4e00" <= seg[0] <= "\u9fff":
            if len(seg) == 1:
                out.append(seg)
            else:
                for i in range(len(seg) - 1):
                    out.append(seg[i:i + 2])
                if len(seg) <= 6:
                    out.append(seg)
        else:
            out.append(seg.lower())
    return out


def _match_expr(q):
    """把查询词转成 FTS5 的 MATCH 表达式（bigram 之间用 OR）。"""
    t = tokens(q)
    if not t:
        return ""
    seen, uniq = set(), []
    for x in t:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return " OR ".join('"%s"' % x.replace('"', '') for x in uniq[:64])


# ---------------------------------------------------------------- 导入
def add_book(title, text, author="", genre="", source="", fulltext=True, sid=None):
    """导入一本书。切章 → 写 chapters → 建全文索引。

    fulltext=False 时只存正文不建全文索引，省磁盘（每 100 万字约 110MB）。
    """
    parts = bk.split_chapters(text)
    if not parts:
        raise ValueError("没有识别出正文内容，检查是否含「第N章」这类标题")
    sid = sid or uuid.uuid4().hex[:12]
    con = _conn()
    try:
        rows, ft_rows, total, no = [], [], 0, 0
        for t, body, volname in parts:
            no += 1
            w = bk.count_words(body)
            total += w
            rows.append((sid, no, t, w, body))
            if fulltext:
                i = 0
                while i < len(body):
                    seg = body[i:i + CHUNK]
                    ft_rows.append((" ".join(tokens(seg)), sid, no, i, t))
                    if i + CHUNK >= len(body):
                        break
                    i += CHUNK - OVERLAP
        with _LOCK:
            con.executemany("INSERT OR REPLACE INTO chapters(sid,no,title,words,text) VALUES(?,?,?,?,?)", rows)
            if ft_rows:
                con.executemany("INSERT INTO ft(tok,sid,no,i,title) VALUES(?,?,?,?,?)", ft_rows)
            con.execute("INSERT OR REPLACE INTO books(sid,title,author,genre,words,nchap,source,fulltext,addedAt,status)"
                        " VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (sid, title or "未命名", author, genre, total, no, source, 1 if fulltext else 0,
                         time.time(), "raw"))
            con.commit()
        return {"ok": True, "sid": sid, "chapters": no, "words": total,
                "chunks": len(ft_rows)}
    finally:
        con.close()


def add_book_file(path, fulltext=True, genre="", author=""):
    ext = os.path.splitext(path)[1].lower()
    if ext not in (".txt", ".md"):
        raise ValueError("语料库目前只收 .txt / .md（docx / epub / pdf 请先在写作界面导入一次再导出）")
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        text = f.read()
    return add_book(os.path.splitext(os.path.basename(path))[0], text,
                    author=author, genre=genre, source=os.path.basename(path), fulltext=fulltext)


def drop_book(sid):
    con = _conn()
    try:
        with _LOCK:
            for sql in ("DELETE FROM chapters WHERE sid=?", "DELETE FROM distill WHERE sid=?",
                        "DELETE FROM dbook WHERE sid=?", "DELETE FROM jobs WHERE sid=?",
                        "DELETE FROM books WHERE sid=?", "DELETE FROM ft WHERE sid=?",
                        "DELETE FROM ftd WHERE sid=?"):
                con.execute(sql, (sid,))
            con.commit()
        return {"ok": True}
    finally:
        con.close()


# ---------------------------------------------------------------- 检索
def search(q, k=10, sid=None, snippet_len=320):
    """跨书全文检索。9000 万字量级下约 4 毫秒。"""
    expr = _match_expr(q)
    if not expr:
        return []
    con = _conn()
    try:
        sql = ("SELECT sid, no, i, title, bm25(ft) AS s FROM ft WHERE ft MATCH ?"
               + (" AND sid = ?" if sid else "") + " ORDER BY s LIMIT ?")
        args = [expr] + ([sid] if sid else []) + [max(k * 4, 20)]
        rows = con.execute(sql, args).fetchall()
        phrases = [p for p in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", q)]
        out, per = [], {}
        for rsid, no, i, title, score in rows:
            if per.get(rsid, 0) >= 3:      # 同一本书最多 3 条，避免整屏同一本
                continue
            per[rsid] = per.get(rsid, 0) + 1
            body = con.execute("SELECT text FROM chapters WHERE sid=? AND no=?", (rsid, no)).fetchone()
            text = (body[0] if body else "") or ""
            # 片段要对准命中处，而不是永远从 800 字块的起点开始
            window = text[i:i + CHUNK + OVERLAP]
            pos = -1
            for p in phrases:
                k2 = window.find(p)
                if k2 >= 0:
                    pos = k2
                    break
            start = i + (max(0, pos - 60) if pos >= 0 else 0)
            seg = text[start:start + snippet_len].replace("\n", " ").strip()
            out.append({"sid": rsid, "no": no, "title": title,
                        "score": round(-score, 5),
                        "snippet": ("…" if start > 0 else "") + seg + "…"})
            if len(out) >= k:
                break
        return out
    finally:
        con.close()


def search_distill(q, k=10):
    """只在蒸馏产物里检索——想「找套路/找写法」时用这个，不碰原文。"""
    expr = _match_expr(q)
    if not expr:
        return []
    con = _conn()
    try:
        rows = con.execute(
            "SELECT x.sid, x.no, x.summary, x.hook, bm25(ftd) AS s"
            " FROM ftd JOIN distill x ON x.sid=ftd.sid AND x.no=ftd.no"
            " WHERE ftd MATCH ? ORDER BY s LIMIT ?", (expr, k)).fetchall()
        return [{"sid": s, "no": n, "summary": sm, "hook": hk, "score": round(-sc, 3)}
                for s, n, sm, hk, sc in rows]
    finally:
        con.close()


# ---------------------------------------------------------------- 统计
def book_stats(sid):
    """单本的无损结构统计，不花 token。"""
    con = _conn()
    try:
        rows = con.execute("SELECT no,title,words,text FROM chapters WHERE sid=? ORDER BY no", (sid,)).fetchall()
    finally:
        con.close()
    if not rows:
        return {}
    lens = [r[2] for r in rows]
    dlg = []
    for _no, _t, _w, text in rows:
        text = text or ""
        quoted = sum(len(m) for m in re.findall(r"[“\"]([^”\"]{1,200})[”\"]", text))
        dlg.append(round(quoted / max(len(text), 1), 3))
    avg = sum(lens) / len(lens)
    return {
        "sid": sid, "chapters": len(rows), "words": sum(lens),
        "avgWords": round(avg, 1),
        "minWords": min(lens), "maxWords": max(lens),
        "stdWords": round((sum((x - avg) ** 2 for x in lens) / len(lens)) ** 0.5, 1),
        "dialogueRatio": round(sum(dlg) / len(dlg), 3),
        "dialogueCurve": dlg[:60],
    }


def overview():
    con = _conn()
    try:
        b = con.execute("SELECT COUNT(*), COALESCE(SUM(words),0), COALESCE(SUM(nchap),0) FROM books").fetchone()
        g = con.execute("SELECT COALESCE(NULLIF(genre,''),'未分类') g, COUNT(*), COALESCE(SUM(words),0)"
                        " FROM books GROUP BY g ORDER BY 3 DESC").fetchall()
        d = con.execute("SELECT COUNT(*) FROM distill").fetchone()[0]
        j = dict(con.execute("SELECT state, COUNT(*) FROM jobs GROUP BY state").fetchall())
        return {"books": b[0], "words": b[1], "chapters": b[2],
                "genres": [{"genre": x[0], "books": x[1], "words": x[2]} for x in g],
                "distilled": d, "jobs": j}
    finally:
        con.close()


def list_books(limit=500):
    con = _conn()
    try:
        rows = con.execute("SELECT sid,title,author,genre,words,nchap,fulltext,addedAt FROM books"
                           " ORDER BY addedAt DESC LIMIT ?", (limit,)).fetchall()
        return [{"sid": r[0], "title": r[1], "author": r[2], "genre": r[3],
                 "words": r[4], "chapters": r[5], "fulltext": bool(r[6]), "addedAt": r[7]} for r in rows]
    finally:
        con.close()


# ---------------------------------------------------------------- 蒸馏任务队列
def plan_jobs(sid, plan="sample"):
    """为一本书生成待蒸馏的章节列表。几百本书必须抽样，否则成本爆炸。"""
    con = _conn()
    try:
        n = con.execute("SELECT nchap FROM books WHERE sid=?", (sid,)).fetchone()
        if not n:
            return {"ok": False, "error": "书不存在"}
        nos = PLANS.get(plan, PLANS["sample"])(n[0])
        with _LOCK:
            con.executemany("INSERT OR IGNORE INTO jobs(sid,no,state,tries,ts) VALUES(?,?,'todo',0,?)",
                            [(sid, x, time.time()) for x in nos])
            con.commit()
        return {"ok": True, "planned": len(nos), "total": n[0], "plan": plan}
    finally:
        con.close()


def take_jobs(limit=8):
    """取一批待办。worker 崩溃后重启会重新拿到 state='doing' 的，天然续跑。"""
    con = _conn()
    try:
        with _LOCK:
            rows = con.execute("SELECT sid,no,tries FROM jobs WHERE state IN ('todo','doing')"
                               " ORDER BY sid,no LIMIT ?", (limit,)).fetchall()
            for sid, no, _t in rows:
                con.execute("UPDATE jobs SET state='doing', ts=? WHERE sid=? AND no=?", (time.time(), sid, no))
            con.commit()
        return [{"sid": r[0], "no": r[1], "tries": r[2]} for r in rows]
    finally:
        con.close()


def finish_job(sid, no, summary, events=None, hook="", tone=""):
    con = _conn()
    try:
        with _LOCK:
            con.execute("INSERT OR REPLACE INTO distill(sid,no,summary,events,hook,tone,ts)"
                        " VALUES(?,?,?,?,?,?,?)",
                        (sid, no, summary, json.dumps(events or [], ensure_ascii=False), hook, tone, time.time()))
            con.execute("INSERT INTO ftd(tok,sid,no) VALUES(?,?,?)",
                        (" ".join(tokens(summary + " " + hook)), sid, no))
            con.execute("UPDATE jobs SET state='done', err='' WHERE sid=? AND no=?", (sid, no))
            con.commit()
        return True
    finally:
        con.close()


def fail_job(sid, no, err, max_tries=3):
    con = _conn()
    try:
        with _LOCK:
            t = con.execute("SELECT tries FROM jobs WHERE sid=? AND no=?", (sid, no)).fetchone()
            tries = (t[0] if t else 0) + 1
            state = "dead" if tries >= max_tries else "todo"
            con.execute("UPDATE jobs SET state=?, tries=?, err=?, ts=? WHERE sid=? AND no=?",
                        (state, tries, str(err)[:300], time.time(), sid, no))
            con.commit()
        return {"state": state, "tries": tries}
    finally:
        con.close()


def chapter_text(sid, no):
    con = _conn()
    try:
        r = con.execute("SELECT title,text,words FROM chapters WHERE sid=? AND no=?", (sid, no)).fetchone()
        return {"title": r[0], "text": r[1], "words": r[2]} if r else None
    finally:
        con.close()


def book_meta(sid):
    con = _conn()
    try:
        r = con.execute("SELECT sid,title,author,genre,words,nchap FROM books WHERE sid=?", (sid,)).fetchone()
        return {"sid": r[0], "title": r[1], "author": r[2], "genre": r[3], "words": r[4], "chapters": r[5]} if r else None
    finally:
        con.close()


def save_dbook(sid, **kw):
    """写入书级蒸馏产物（卷摘要 / 全书 / 人物 / 文风卡 / 套路 / 节奏）。"""
    con = _conn()
    try:
        cur = con.execute("SELECT sid FROM dbook WHERE sid=?", (sid,)).fetchone()
        if cur:
            keys = [k for k in kw if k in ("volume_sum", "book_sum", "characters", "style", "tropes", "rhythm")]
            if keys:
                con.execute("UPDATE dbook SET " + ",".join("%s=?" % k for k in keys) + ", updatedAt=? WHERE sid=?",
                            [kw[k] for k in keys] + [time.time(), sid])
        else:
            con.execute("INSERT INTO dbook(sid,volume_sum,book_sum,characters,style,tropes,rhythm,updatedAt)"
                        " VALUES(?,?,?,?,?,?,?,?)",
                        (sid, kw.get("volume_sum", ""), kw.get("book_sum", ""), kw.get("characters", ""),
                         kw.get("style", ""), kw.get("tropes", ""), kw.get("rhythm", ""), time.time()))
        con.commit()
        return {"ok": True}
    finally:
        con.close()


# ---------------------------------------------------------------- 命令行
def _cli(argv):
    """不依赖界面，直接命令行跑：
        python corpus.py init   data/corpus.db
        python corpus.py import data/corpus.db D:/novels/ --no-fulltext
        python corpus.py search data/corpus.db 林昭
        python corpus.py stats  data/corpus.db
        python corpus.py plan   data/corpus.db sample
    """
    if len(argv) < 2:
        print("用法：python corpus.py {init|import|search|stats|plan} <db> [参数]")
        return 1
    cmd = argv[1]
    if cmd == "init":
        init(argv[2] if len(argv) > 2 else "corpus.db")
        print("已初始化")
        return 0

    db = argv[2] if len(argv) > 2 else "corpus.db"
    init(db)

    if cmd == "import":
        target = argv[3]
        ft = "--no-fulltext" not in argv
        files = []
        if os.path.isdir(target):
            for root, _d, fs in os.walk(target):
                for f in fs:
                    if os.path.splitext(f)[1].lower() in (".txt", ".md"):
                        files.append(os.path.join(root, f))
        else:
            files = [target]
        print("待导入 %d 个文件（全文索引：%s）" % (len(files), "开" if ft else "关"))
        t0 = time.time()
        bad = 0
        for i, p in enumerate(files, 1):
            try:
                r = add_book_file(p, fulltext=ft)
                print("  [%d/%d] %s → %d 章 %d 字" % (i, len(files), os.path.basename(p), r["chapters"], r["words"]))
            except Exception as e:
                bad += 1
                print("  [%d/%d] 跳过 %s：%s" % (i, len(files), os.path.basename(p), e))
        print("完成，用时 %.1fs，失败 %d 个" % (time.time() - t0, bad))
        return 0

    if cmd == "search":
        for hit in search(" ".join(argv[3:]), k=10):
            b = book_meta(hit["sid"]) or {}
            print("\n《%s》第%d章 %s  [%.2f]" % (b.get("title", "?"), hit["no"], hit["title"], hit["score"]))
            print("  " + hit["snippet"])
        return 0

    if cmd == "stats":
        ov = overview()
        print("书 %d 本 / %d 章 / %d 万字 / 已蒸馏 %d 章"
              % (ov["books"], ov["chapters"], ov["words"] // 10000, ov["distilled"]))
        for g in ov["genres"][:12]:
            print("  %-6s %3d 本  %5d 万字" % (g["genre"], g["books"], g["words"] // 10000))
        print("任务:", ov["jobs"] or "无")
        return 0

    if cmd == "plan":
        plan = argv[3] if len(argv) > 3 else "sample"
        total = 0
        for b in list_books(1000):
            total += plan_jobs(b["sid"], plan)["planned"]
        print("已排 %d 个蒸馏任务（策略 %s）" % (total, plan))
        return 0

    print("未知命令:", cmd)
    return 1


if __name__ == "__main__":
    import sys
    raise SystemExit(_cli(sys.argv))
