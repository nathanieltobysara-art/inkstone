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
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

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
    # 章级 beat 字段：老库平滑迁移，不用重建
    cols = {r[1] for r in con.execute("PRAGMA table_info(distill)")}
    if "beat" not in cols:
        con.execute("ALTER TABLE distill ADD COLUMN beat TEXT DEFAULT ''")
    # 文风指标：纯程序统计，不花 token
    con.execute("""CREATE TABLE IF NOT EXISTS style(
                     sid TEXT PRIMARY KEY, avgSent REAL, shortRatio REAL, dialogue REAL,
                     paraLen REAL, sentCount INTEGER, ts REAL)""")
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


def finish_job(sid, no, summary, events=None, hook="", tone="", beat=""):
    con = _conn()
    try:
        with _LOCK:
            con.execute("INSERT OR REPLACE INTO distill(sid,no,summary,events,hook,tone,beat,ts)"
                        " VALUES(?,?,?,?,?,?,?,?)",
                        (sid, no, summary, json.dumps(events or [], ensure_ascii=False),
                         hook, tone, beat, time.time()))
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


# ---------------------------------------------------------------- M2 蒸馏 worker
DISTILL_SYS = """你在拆解一部长篇小说的一章，供后续统计分析使用。只输出 JSON，不要解释、不要代码块围栏。

{"summary":"150字以内的本章剧情摘要，按事件顺序，写清谁做了什么、结果如何",
 "events":["本章发生的关键事件，最多5条，每条20字以内"],
 "hook":"章末留下的钩子，一句话；没有就填空字符串",
 "beat":"本章主类型，只能选一个：conflict_thrill / bond_deepening / faction_building / world_painting / tension_escalation / other"}

要求：summary 用陈述句，不加评论；只写正文里确实发生的事，不推测；不要复述原文句子。"""

BEAT_NAMES = {
    "conflict_thrill": "冲突爽点",
    "bond_deepening": "人物羁绊",
    "faction_building": "势力经营",
    "world_painting": "风土人情",
    "tension_escalation": "危机升级",
    "other": "其他",
}


def _post(url, payload, headers, timeout=120):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        if v:
            req.add_header(k, v)
    host = ""
    try:
        host = (url.split("//", 1)[-1].split("/", 1)[0].split(":")[0]).lower()
    except Exception:
        pass
    # 本地回环必须绕过系统代理，否则 Ollama / LM Studio 会被拦成 502
    opener = (urllib.request.build_opener(urllib.request.ProxyHandler({}))
              if host in ("localhost", "127.0.0.1", "::1") else urllib.request.build_opener())
    try:
        with opener.open(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8", "ignore"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:300]
        except Exception:
            pass
        raise RuntimeError("HTTP %d %s" % (e.code, body))
    except urllib.error.URLError as e:
        raise RuntimeError("无法连接：%s" % e.reason)


def complete(cfg, messages, max_tokens=600, temperature=0.3, timeout=120):
    """非流式补全。批量蒸馏不建 SSE 连接——1.3 万次调用，流式纯属浪费。"""
    kind = (cfg.get("kind") or "openai").lower()
    base = (cfg.get("baseUrl") or "").strip().rstrip("/")
    key = cfg.get("apiKey") or ""
    model = cfg.get("model") or ""

    if kind == "anthropic":
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        conv = [m for m in messages if m["role"] in ("user", "assistant")]
        obj = _post(base + "/v1/messages",
                    {"model": model, "system": system, "messages": conv,
                     "max_tokens": max_tokens, "temperature": temperature},
                    {"x-api-key": key, "anthropic-version": "2023-06-01"}, timeout)
        return "".join(b.get("text", "") for b in (obj.get("content") or []))

    if kind == "ollama":
        obj = _post(base + "/api/chat",
                    {"model": model, "messages": messages, "stream": False,
                     "options": {"temperature": temperature, "num_predict": max_tokens}},
                    {}, timeout)
        return (obj.get("message") or {}).get("content", "")

    if base.endswith("/chat/completions"):
        url = base
    elif re.search(r"/v\d+$", base):
        url = base + "/chat/completions"
    else:
        url = base + "/v1/chat/completions"
    obj = _post(url, {"model": model, "messages": messages, "stream": False,
                      "max_tokens": max_tokens, "temperature": temperature},
                {"Authorization": "Bearer " + (key or "sk-local")}, timeout)
    ch = (obj.get("choices") or [{}])[0]
    return (ch.get("message") or {}).get("content", "") or ""


def _json_of(text):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S)
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        return json.loads(t[i:j + 1])
    except Exception:
        return None


def estimate(price=None):
    """跑之前先算账：多少任务、多少 token、多少钱。"""
    con = _conn()
    try:
        rows = con.execute("SELECT sid, no FROM jobs WHERE state IN ('todo','doing','dead')").fetchall()
        chars = 0
        for sid, no in rows:
            r = con.execute("SELECT words FROM chapters WHERE sid=? AND no=?", (sid, no)).fetchone()
            chars += min(int((r[0] if r else 0) or 0), 9000)
    finally:
        con.close()
    tin = int(chars * 0.75)
    tout = len(rows) * 220
    out = {"jobs": len(rows), "chars": chars, "tokensIn": tin, "tokensOut": tout,
           "minutes": round(len(rows) / 4.0 * 4 / 60.0, 1)}
    if price:
        out["cost"] = round(tin / 1e6 * price.get("in", 0) + tout / 1e6 * price.get("out", 0), 2)
    return out


def _distill_one(cfg, job):
    ch = chapter_text(job["sid"], job["no"])
    if not ch or not (ch["text"] or "").strip():
        raise ValueError("章节正文为空")
    body = ch["text"][:9000]
    txt = complete(cfg, [
        {"role": "system", "content": DISTILL_SYS},
        {"role": "user", "content": "章节标题：%s\n\n正文：\n%s" % (ch["title"], body)},
    ], max_tokens=600, temperature=0.3)
    d = _json_of(txt)
    if not d or not (d.get("summary") or "").strip():
        raise ValueError("返回无法解析为 JSON：" + (txt or "")[:80])
    beat = (d.get("beat") or "").strip()
    if beat not in BEAT_NAMES:
        beat = "other"
    finish_job(job["sid"], job["no"], d["summary"].strip(),
               d.get("events") or [], (d.get("hook") or "").strip(), "", beat)
    return {"summary": d["summary"].strip()[:40], "beat": beat}


def run_jobs(cfg, concurrency=4, max_jobs=None, on_event=None, should_stop=None):
    """并发跑蒸馏队列。断点续跑靠 jobs 表的 doing 状态，进程被杀也不会丢任务。"""
    done = failed = 0
    if on_event:
        on_event("start", {"concurrency": concurrency})

    def handle(job, fn):
        nonlocal done, failed
        try:
            r = fn()
            done += 1
            if on_event:
                on_event("done", dict(job, done=done, failed=failed, **r))
        except Exception as e:
            msg = str(e)
            res = fail_job(job["sid"], job["no"], msg)
            failed += 1
            if on_event:
                on_event("fail", dict(job, error=msg[:160], state=res["state"],
                                      done=done, failed=failed))
            if "429" in msg or "rate" in msg.lower():
                time.sleep(2)

    with ThreadPoolExecutor(max_workers=max(1, int(concurrency))) as ex:
        while True:
            if should_stop and should_stop():
                break
            if max_jobs and (done + failed) >= max_jobs:
                break
            n = min(concurrency, max_jobs - (done + failed)) if max_jobs else concurrency
            batch = take_jobs(max(1, n))
            if not batch:
                break
            futs = {ex.submit(_distill_one, cfg, j): j for j in batch}
            for f in as_completed(futs):
                handle(futs[f], f.result)

    if on_event:
        on_event("end", {"done": done, "failed": failed})
    return {"done": done, "failed": failed}


# ---------------------------------------------------------------- M3 横向聚合
def style_metrics(sid):
    """从原文算文风指标，纯程序统计，不花一个 token。"""
    con = _conn()
    try:
        rows = con.execute("SELECT text FROM chapters WHERE sid=? ORDER BY no", (sid,)).fetchall()
    finally:
        con.close()
    text = "\n".join((r[0] or "") for r in rows)
    if not text.strip():
        return None
    sents = [s for s in re.split(r"[。！？!?…]+", text) if s.strip()]
    lens = [len(s) for s in sents]
    paras = [p for p in text.split("\n") if p.strip()]
    quoted = sum(len(m) for m in re.findall(r"[“\"]([^”\"]{1,200})[”\"]", text))
    m = {"avgSent": round(sum(lens) / max(len(lens), 1), 1),
         "shortRatio": round(sum(1 for x in lens if x <= 15) / max(len(lens), 1), 3),
         "dialogue": round(quoted / max(len(text), 1), 3),
         "paraLen": round(sum(len(p) for p in paras) / max(len(paras), 1), 1),
         "sentCount": len(sents)}
    con = _conn()
    try:
        with _LOCK:
            con.execute("INSERT OR REPLACE INTO style(sid,avgSent,shortRatio,dialogue,paraLen,sentCount,ts)"
                        " VALUES(?,?,?,?,?,?,?)",
                        (sid, m["avgSent"], m["shortRatio"], m["dialogue"], m["paraLen"],
                         m["sentCount"], time.time()))
            con.commit()
    finally:
        con.close()
    return m


def genre_baseline():
    """按题材聚合：章长、文风坐标、爽点类型分布。这才是「几百本书」的价值。"""
    con = _conn()
    try:
        books = con.execute("SELECT sid, COALESCE(NULLIF(genre,''),'未分类') g, words, nchap FROM books").fetchall()
        st = {r[0]: r[1:] for r in con.execute("SELECT sid,avgSent,shortRatio,dialogue,paraLen FROM style")}
        beats = {}
        for sid, beat, c in con.execute(
                "SELECT sid, COALESCE(NULLIF(beat,''),'other'), COUNT(*) FROM distill GROUP BY sid, beat"):
            beats.setdefault(sid, {})[beat] = c
    finally:
        con.close()

    agg = {}
    for sid, g, words, nchap in books:
        a = agg.setdefault(g, {"genre": g, "books": 0, "words": 0, "chapters": 0,
                               "style": [], "beats": {}})
        a["books"] += 1
        a["words"] += words or 0
        a["chapters"] += nchap or 0
        if sid in st:
            a["style"].append(st[sid])
        for b, c in (beats.get(sid) or {}).items():
            a["beats"][b] = a["beats"].get(b, 0) + c

    out = []
    for a in agg.values():
        s = a.pop("style")
        if s:
            a["avgSent"] = round(sum(x[0] for x in s) / len(s), 1)
            a["shortRatio"] = round(sum(x[1] for x in s) / len(s), 3)
            a["dialogue"] = round(sum(x[2] for x in s) / len(s), 3)
        a["avgWords"] = round(a["words"] / max(a["books"], 1))
        a["avgChap"] = round(a["chapters"] / max(a["books"], 1), 1)
        tot = sum(a["beats"].values()) or 1
        a["beats"] = {k: round(v / tot, 3) for k, v in
                      sorted(a["beats"].items(), key=lambda x: -x[1])}
        out.append(a)
    out.sort(key=lambda x: -x["words"])
    return out


def report_markdown():
    """生成一份可落盘的聚合报告。"""
    ov = overview()
    lines = ["# 语料库蒸馏报告", "",
             "- 书目 %d 本 / %d 章 / %.1f 万字" % (ov["books"], ov["chapters"], ov["words"] / 10000.0),
             "- 已蒸馏 %d 章 / 任务 %s" % (ov["distilled"], ov["jobs"] or "无"), ""]

    base = genre_baseline()
    if not base:
        lines.append("_还没有数据。先 import 再 plan，然后 run。_")
        return "\n".join(lines)

    lines += ["## 题材基准线", "",
              "| 题材 | 本数 | 总字数 | 平均章长 | 平均句长 | 短句占比 | 对话占比 |",
              "|---|---|---|---|---|---|---|"]
    for g in base:
        lines.append("| %s | %d | %.1f 万 | %s | %s | %s | %s |" % (
            g["genre"], g["books"], g["words"] / 10000.0, g.get("avgChap", "-"),
            g.get("avgSent", "-"), g.get("shortRatio", "-"), g.get("dialogue", "-")))

    has_beat = any(g["beats"] for g in base)
    if has_beat:
        lines += ["", "## 爽点类型分布", "",
                  "| 题材 | " + " | ".join(BEAT_NAMES.values()) + " |",
                  "|---|" + "---|" * len(BEAT_NAMES)]
        for g in base:
            cells = ["%.0f%%" % (g["beats"].get(k, 0) * 100) for k in BEAT_NAMES]
            lines.append("| %s | %s |" % (g["genre"], " | ".join(cells)))
    else:
        lines += ["", "## 爽点类型分布", "",
                  "_还没有章级蒸馏数据。先跑 `plan` + `run`，这里才有东西可统计。_"]

    con = _conn()
    try:
        top = con.execute("SELECT sid,no,summary,beat FROM distill ORDER BY RANDOM() LIMIT 8").fetchall()
    finally:
        con.close()
    if top:
        lines += ["", "## 随机抽样（校对用）", ""]
        for sid, no, sm, beat in top:
            b = book_meta(sid) or {}
            lines.append("- 《%s》第 %d 章（%s）：%s" % (
                b.get("title", "?"), no, BEAT_NAMES.get(beat, beat or "-"), sm))

    return "\n".join(lines)


# ---------------------------------------------------------------- 命令行
def _cli(argv):
    """不依赖界面，直接命令行跑：
        python corpus.py init   data/corpus.db
        python corpus.py import data/corpus.db D:/novels/ --no-fulltext
        python corpus.py search data/corpus.db 林昭
        python corpus.py stats  data/corpus.db
        python corpus.py plan   data/corpus.db sample
        python corpus.py style  data/corpus.db
        python corpus.py run    data/corpus.db --config data/config.json --concurrency 4
        python corpus.py report data/corpus.db out.md
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
        est = estimate()
        print("预计：%d 次调用 / 输入 %.0f 万 token / 输出 %.0f 万 token / 并发 4 约 %.1f 小时"
              % (est["jobs"], est["tokensIn"] / 1e4, est["tokensOut"] / 1e4, est["minutes"] / 60))
        return 0

    if cmd == "style":
        n = 0
        for b in list_books(1000):
            if style_metrics(b["sid"]):
                n += 1
        print("已统计 %d 本文风指标（纯程序，未调用模型）" % n)
        return 0

    if cmd == "run":
        args = argv[3:]
        opt = {}
        i = 0
        while i < len(args):
            if args[i].startswith("--"):
                opt[args[i][2:]] = args[i + 1] if i + 1 < len(args) else ""
                i += 2
            else:
                i += 1
        cfg = {}
        if opt.get("config") and os.path.exists(opt["config"]):
            raw = json.load(open(opt["config"], encoding="utf-8"))
            aid = raw.get("activeProviderId")
            cfg = next((p for p in raw.get("providers", []) if p.get("id") == aid), None) or {}
            print("用配置里的供应商：%s / %s" % (cfg.get("name", "?"), cfg.get("model", "?")))
        if opt.get("base"):
            cfg["baseUrl"] = opt["base"]
        if opt.get("key"):
            cfg["apiKey"] = opt["key"]
        if opt.get("model"):
            cfg["model"] = opt["model"]
        if not cfg.get("baseUrl") or not cfg.get("model"):
            print("缺少模型配置。用 --config data/config.json，或 --base/--key/--model 指定。")
            return 1
        est = estimate()
        if not est["jobs"]:
            print("没有待办任务。先跑 plan。")
            return 0
        print("待跑 %d 个任务 / 输入约 %.0f 万 token / 输出约 %.0f 万 token"
              % (est["jobs"], est["tokensIn"] / 1e4, est["tokensOut"] / 1e4))

        def on_event(kind, d):
            if kind == "done":
                print("  [%d/%d] %s 第%d章 → %s" % (d.get("done", 0), est["jobs"],
                                                  d["sid"][:8], d["no"], d.get("beat", "")))
            elif kind == "fail":
                print("  [失败] %s 第%d章 %s" % (d["sid"][:8], d["no"], d.get("error", "")))

        r = run_jobs(cfg, concurrency=int(opt.get("concurrency") or 4),
                     max_jobs=int(opt["max"]) if opt.get("max") else None,
                     on_event=on_event)
        print("完成：成功 %d / 失败 %d" % (r["done"], r["failed"]))
        return 0

    if cmd == "report":
        md = report_markdown()
        out = argv[3] if len(argv) > 3 else ""
        if out:
            with open(out, "w", encoding="utf-8") as f:
                f.write(md)
            print("已写入", out)
        else:
            print(md)
        return 0

    print("未知命令:", cmd)
    return 1


if __name__ == "__main__":
    import sys
    raise SystemExit(_cli(sys.argv))
