#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
砚 Inkstone — 书稿层
零依赖。一本书是一个目录：

  data/books/<bid>/
    book.json          元信息 + 卷章树
    chapters/c001.md   正文，一章一文件
    bible.json         设定库（人物/势力/道具/时间线/伏笔/名词表/世界观）
    outline/book.md    整本大纲
    outline/vol-v1.md  分卷大纲
    outline/ch-c001.md 单章提纲
    snapshots/c001/    版本快照
    index.json         BM25 检索索引（可重建）
"""
import json
import os
import re
import shutil
import time
import uuid
import zipfile
import io

BOOKS = None          # 由 server.py 注入 DATA 后设置
_LOCK = None


def init(data_dir, lock):
    global BOOKS, _LOCK
    BOOKS = os.path.join(data_dir, "books")
    _LOCK = lock
    os.makedirs(BOOKS, exist_ok=True)


# ---------------------------------------------------------------- 基础 IO
def _safe(name):
    """只允许字母数字下划线，防目录穿越。"""
    return re.sub(r"[^0-9A-Za-z_\-]", "", name or "")


def bdir(bid):
    return os.path.join(BOOKS, _safe(bid))


def _read_json(path, default=None):
    if not os.path.exists(path):
        return json.loads(json.dumps(default)) if default is not None else None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return json.loads(json.dumps(default)) if default is not None else None


def _write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def _read_text(path, default=""):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return default


def _write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


# ---------------------------------------------------------------- 元信息
EMPTY_BIBLE = {
    "world": "",
    "characters": [],
    "factions": [],
    "items": [],
    "timeline": [],
    "foreshadow": [],
    "terms": [],
}


def count_words(text):
    """中文按字计，英文按词计——和网文平台的字数口径一致。"""
    if not text:
        return 0
    han = len(re.findall(r"[\u4e00-\u9fff]", text))
    en = len(re.findall(r"[A-Za-z]+", text))
    return han + en


def _new_cid(b):
    used = set()
    for v in b.get("volumes", []):
        for ch in v.get("chapters", []):
            used.add(ch["id"])
    n = 1
    while True:
        cid = "c%03d" % n
        if cid not in used:
            return cid
        n += 1


def _new_vid(b):
    used = {v["id"] for v in b.get("volumes", [])}
    n = 1
    while True:
        vid = "v%d" % n
        if vid not in used:
            return vid
        n += 1


def list_books():
    out = []
    if not os.path.isdir(BOOKS):
        return out
    for name in os.listdir(BOOKS):
        p = os.path.join(BOOKS, name, "book.json")
        if not os.path.isfile(p):
            continue
        b = _read_json(p)
        if not b:
            continue
        chs = [ch for v in b.get("volumes", []) for ch in v.get("chapters", [])]
        out.append({
            "id": b.get("id", name),
            "title": b.get("title") or "未命名书稿",
            "genre": b.get("genre") or "",
            "logline": b.get("logline") or "",
            "chapters": len(chs),
            "words": sum(int(ch.get("words") or 0) for ch in chs),
            "volumes": len(b.get("volumes", [])),
            "updatedAt": b.get("updatedAt") or 0,
        })
    out.sort(key=lambda x: x["updatedAt"], reverse=True)
    return out


def create_book(title, genre="", author=""):
    bid = "b" + uuid.uuid4().hex[:10]
    d = bdir(bid)
    os.makedirs(os.path.join(d, "chapters"), exist_ok=True)
    os.makedirs(os.path.join(d, "outline"), exist_ok=True)
    b = {
        "id": bid,
        "title": (title or "未命名书稿").strip(),
        "genre": genre or "",
        "author": author or "",
        "audience": "",
        "logline": "",
        "style": "",
        "notes": "",
        "createdAt": time.time(),
        "updatedAt": time.time(),
        "volumes": [{"id": "v1", "title": "第一卷", "chapters": []}],
    }
    _write_json(os.path.join(d, "book.json"), b)
    _write_json(os.path.join(d, "bible.json"), EMPTY_BIBLE)
    return b


def get_book(bid):
    return _read_json(os.path.join(bdir(bid), "book.json"))


def save_book(b):
    b["updatedAt"] = time.time()
    _write_json(os.path.join(bdir(b["id"]), "book.json"), b)
    return b


def delete_book(bid):
    d = bdir(bid)
    if not os.path.isdir(d):
        return True
    # 先删元信息：即使后面删目录被占用打断，列表里也不会再出现这本
    for name in ("book.json", "index.json"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            try:
                os.remove(p)
            except OSError:
                pass
    shutil.rmtree(d, ignore_errors=True)
    return True


def flat_chapters(b):
    """扁平章节列表，带全局序号与所属卷。"""
    out = []
    no = 0
    for vi, v in enumerate(b.get("volumes", [])):
        for ci, ch in enumerate(v.get("chapters", [])):
            no += 1
            out.append({
                "id": ch["id"], "title": ch.get("title") or "未命名",
                "volumeId": v["id"], "volumeTitle": v.get("title") or "",
                "no": no, "index": ci, "volumeIndex": vi,
                "words": int(ch.get("words") or 0),
                "summary": ch.get("summary") or "",
                "status": ch.get("status") or "draft",
                "updatedAt": ch.get("updatedAt") or 0,
            })
    return out


def find_chapter(b, cid):
    for v in b.get("volumes", []):
        for ch in v.get("chapters", []):
            if ch["id"] == cid:
                return v, ch
    return None, None


# ---------------------------------------------------------------- 章节
def chapter_path(bid, cid):
    return os.path.join(bdir(bid), "chapters", _safe(cid) + ".md")


def read_chapter(bid, cid):
    b = get_book(bid)
    if not b:
        return None
    v, ch = find_chapter(b, cid)
    if not ch:
        return None
    text = _read_text(chapter_path(bid, cid))
    return {
        "id": ch["id"], "title": ch.get("title") or "",
        "volumeId": v["id"], "text": text,
        "words": count_words(text),
        "summary": ch.get("summary") or "",
        "status": ch.get("status") or "draft",
        "updatedAt": ch.get("updatedAt") or 0,
        "outline": _read_text(os.path.join(bdir(bid), "outline", "ch-" + _safe(cid) + ".md")),
    }


SNAPSHOT_GAP = 45      # 秒：两次自动快照的最小间隔
SNAPSHOT_KEEP = 24     # 每章保留份数


def write_chapter(bid, cid, text, title=None, snapshot=True):
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    v, ch = find_chapter(b, cid)
    if not ch:
        raise ValueError("章节不存在")
    old = _read_text(chapter_path(bid, cid))
    if old == text and title is None:
        return {"ok": True, "unchanged": True}
    if snapshot and old.strip() and old != text:
        _snapshot(bid, cid, old)
    _write_text(chapter_path(bid, cid), text or "")
    if title is not None:
        ch["title"] = title
    ch["words"] = count_words(text)
    ch["updatedAt"] = time.time()
    ch["dirty"] = False
    save_book(b)
    return {"ok": True, "words": ch["words"], "updatedAt": ch["updatedAt"]}


def create_chapter(bid, volume_id=None, title=None, after=None, text=""):
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    if not b.get("volumes"):
        b["volumes"] = [{"id": "v1", "title": "第一卷", "chapters": []}]
    v = None
    if volume_id:
        v = next((x for x in b["volumes"] if x["id"] == volume_id), None)
    if not v:
        v = b["volumes"][-1]
    cid = _new_cid(b)
    total = len(flat_chapters(b)) + 1
    ch = {"id": cid, "title": title or ("第%d章" % total), "words": count_words(text),
          "summary": "", "status": "draft", "updatedAt": time.time()}
    idx = len(v["chapters"])
    if after:
        for i, x in enumerate(v["chapters"]):
            if x["id"] == after:
                idx = i + 1
                break
    v["chapters"].insert(idx, ch)
    if text:
        _write_text(chapter_path(bid, cid), text)
    save_book(b)
    return {"ok": True, "chapter": ch, "volumeId": v["id"], "id": cid}


def delete_chapter(bid, cid):
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    for v in b["volumes"]:
        for i, ch in enumerate(v["chapters"]):
            if ch["id"] == cid:
                v["chapters"].pop(i)
                p = chapter_path(bid, cid)
                if os.path.exists(p):
                    os.remove(p)
                save_book(b)
                return {"ok": True}
    raise ValueError("章节不存在")


def move_chapter(bid, cid, volume_id, index):
    """拖拽排序：把章节挪到指定卷的指定位置。"""
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    src_v, ch = find_chapter(b, cid)
    if not ch:
        raise ValueError("章节不存在")
    src_v["chapters"].remove(ch)
    dst = next((v for v in b["volumes"] if v["id"] == volume_id), None) or src_v
    index = max(0, min(int(index), len(dst["chapters"])))
    dst["chapters"].insert(index, ch)
    save_book(b)
    return {"ok": True}


def renumber_titles(bid, pattern="第{n}章"):
    """按当前顺序重排章节标题（只改纯编号标题，不碰自定义标题）。"""
    b = get_book(bid)
    n = 0
    changed = 0
    for v in b["volumes"]:
        for ch in v["chapters"]:
            n += 1
            t = ch.get("title") or ""
            if re.match(r"^第\s*[0-9零一二三四五六七八九十百千]+\s*章\s*$", t) or not t:
                ch["title"] = pattern.format(n=n)
                changed += 1
    save_book(b)
    return {"ok": True, "changed": changed}


# ---------------------------------------------------------------- 分章导入
CH_RE = re.compile(r"^[\s#*　]*第\s*[0-9零一二三四五六七八九十百千两]+\s*[章回节][\s　]*[^\n]{0,40}$")
VOL_RE = re.compile(r"^[\s#*　]*第\s*[0-9零一二三四五六七八九十百千两]+\s*[卷部篇][\s　]*[^\n]{0,40}$")


def _clean_heading(line):
    return re.sub(r"^[\s#*　]+|[\s*]+$", "", line).strip()


def split_chapters(text):
    """按「第X章」切分；没有标记就按字数硬切。返回 [(title, body)]。"""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")
    marks = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s or len(s) > 60:
            continue
        if CH_RE.match(s) or VOL_RE.match(s):
            marks.append((i, _clean_heading(s), bool(VOL_RE.match(s))))
    if len([m for m in marks if not m[2]]) >= 2:
        out = []
        cur_title, cur_vol = None, ""
        buf = []
        for i, ln in enumerate(lines):
            hit = next((m for m in marks if m[0] == i), None)
            if hit:
                if cur_title is not None:
                    body = "\n".join(buf).strip()
                    out.append((cur_title, body, cur_vol))
                if hit[2]:
                    cur_vol = hit[1]
                    cur_title = None
                else:
                    cur_title = hit[1]
                buf = []
            elif cur_title is not None:
                buf.append(ln)
        if cur_title is not None:
            out.append((cur_title, "\n".join(buf).strip(), cur_vol))
        out = [x for x in out if x[1]]
        if out:
            return out
    # 兜底：按 3000 字硬切
    body = text.strip()
    if not body:
        return []
    out = []
    size = 3000
    n = 0
    i = 0
    while i < len(body):
        n += 1
        chunk = body[i:i + size]
        # 尽量在句号处断开
        if i + size < len(body):
            cut = max(chunk.rfind("。"), chunk.rfind("\n"))
            if cut > size * 0.6:
                chunk = chunk[:cut + 1]
        out.append(("第%d章" % n, chunk.strip(), ""))
        i += len(chunk)
    return out


def import_book(title, text, genre="", filename="", bid=None):
    """整本导入：切章写入。bid 为空时新建一本书，否则追加到已有书。"""
    b = get_book(bid) if bid else None
    if not b:
        b = create_book(title or (filename or "导入书稿").rsplit(".", 1)[0], genre)
    parts = split_chapters(text)
    if not parts:
        raise ValueError("没有识别出正文内容")
    vol_map = {}
    for t, body, volname in parts:
        vname = volname or "第一卷"
        if vname not in vol_map:
            if not b["volumes"][0]["chapters"] and len(vol_map) == 0 and vname == "第一卷":
                b["volumes"][0]["title"] = vname
                vol_map[vname] = b["volumes"][0]
            else:
                vid = _new_vid(b)
                v = {"id": vid, "title": vname, "chapters": []}
                b["volumes"].append(v)
                vol_map[vname] = v
        cid = _new_cid(b)
        vol_map[vname]["chapters"].append({
            "id": cid, "title": t, "words": count_words(body),
            "summary": "", "status": "draft", "updatedAt": time.time(),
        })
        _write_text(chapter_path(b["id"], cid), body)
    b["volumes"] = [v for v in b["volumes"] if v["chapters"]]
    save_book(b)
    build_index(b["id"], force=True)
    return {"ok": True, "book": b, "chapters": len(parts)}


# ---------------------------------------------------------------- 设定库
def load_bible(bid):
    d = _read_json(os.path.join(bdir(bid), "bible.json"), EMPTY_BIBLE)
    for k, v in EMPTY_BIBLE.items():
        if k not in d:
            d[k] = json.loads(json.dumps(v))
    return d


def save_bible(bid, data):
    cur = load_bible(bid)
    for k in EMPTY_BIBLE:
        if k in data:
            cur[k] = data[k]
    _write_json(os.path.join(bdir(bid), "bible.json"), cur)
    return cur


def load_outline(bid):
    d = os.path.join(bdir(bid), "outline")
    return {
        "book": _read_text(os.path.join(d, "book.md")),
        "volumes": {v: _read_text(os.path.join(d, "vol-" + _safe(v) + ".md"))
                    for v in [x["id"] for x in (get_book(bid) or {}).get("volumes", [])]},
    }


def save_outline(bid, scope, key, text):
    d = os.path.join(bdir(bid), "outline")
    if scope == "book":
        fn = "book.md"
    elif scope == "volume":
        fn = "vol-" + _safe(key) + ".md"
    else:
        fn = "ch-" + _safe(key) + ".md"
    _write_text(os.path.join(d, fn), text or "")
    # 大纲改动时间戳，用于提醒正文未同步
    meta = _read_json(os.path.join(d, "_meta.json"), {})
    meta[key or "book"] = time.time()
    _write_json(os.path.join(d, "_meta.json"), meta)
    return {"ok": True}


def outline_drift(bid):
    """大纲比正文新 → 正文可能没跟上。"""
    b = get_book(bid)
    if not b:
        return []
    meta = _read_json(os.path.join(bdir(bid), "outline", "_meta.json"), {})
    out = []
    for ch in flat_chapters(b):
        t = meta.get(ch["id"])
        if t and t > (ch.get("updatedAt") or 0) + 5:
            out.append({"chapterId": ch["id"], "title": ch["title"], "no": ch["no"]})
    return out


# ---------------------------------------------------------------- 快照
def _snapdir(bid, cid):
    return os.path.join(bdir(bid), "snapshots", _safe(cid))


def _snapshot(bid, cid, text):
    d = _snapdir(bid, cid)
    os.makedirs(d, exist_ok=True)
    files = sorted(f for f in os.listdir(d) if f.endswith(".md"))
    if files:
        last = os.path.join(d, files[-1])
        try:
            if time.time() - os.path.getmtime(last) < SNAPSHOT_GAP:
                _write_text(last, text)      # 合并到上一份，避免碎片
                return
        except OSError:
            pass
    _write_text(os.path.join(d, "%d.md" % int(time.time() * 1000)), text)
    files = sorted(f for f in os.listdir(d) if f.endswith(".md"))
    for old in files[:-SNAPSHOT_KEEP]:
        try:
            os.remove(os.path.join(d, old))
        except OSError:
            pass


def list_snapshots(bid, cid):
    d = _snapdir(bid, cid)
    if not os.path.isdir(d):
        return []
    out = []
    for fn in sorted(os.listdir(d), reverse=True):
        if not fn.endswith(".md"):
            continue
        p = os.path.join(d, fn)
        txt = _read_text(p)
        out.append({"ts": int(fn[:-3]), "words": count_words(txt),
                    "preview": txt.strip()[:60].replace("\n", " ")})
    return out


def read_snapshot(bid, cid, ts):
    p = os.path.join(_snapdir(bid, cid), "%d.md" % int(ts))
    if not os.path.exists(p):
        raise ValueError("快照不存在")
    return _read_text(p)


def restore_snapshot(bid, cid, ts):
    text = read_snapshot(bid, cid, ts)
    return write_chapter(bid, cid, text)


def diff_lines(a, b):
    """行级 LCS diff，返回 [{op, text}]。"""
    la, lb = a.split("\n"), b.split("\n")
    n, m = len(la), len(lb)
    if n * m > 4000000:                      # 太长就退化成整段对比
        return [{"op": "del", "text": x} for x in la] + [{"op": "add", "text": x} for x in lb]
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            dp[i][j] = dp[i + 1][j + 1] + 1 if la[i] == lb[j] else max(dp[i + 1][j], dp[i][j + 1])
    out = []
    i = j = 0
    while i < n and j < m:
        if la[i] == lb[j]:
            out.append({"op": "same", "text": la[i]})
            i += 1
            j += 1
        elif dp[i + 1][j] >= dp[i][j + 1]:
            out.append({"op": "del", "text": la[i]})
            i += 1
        else:
            out.append({"op": "add", "text": lb[j]})
            j += 1
    while i < n:
        out.append({"op": "del", "text": la[i]})
        i += 1
    while j < m:
        out.append({"op": "add", "text": lb[j]})
        j += 1
    return out


# ---------------------------------------------------------------- 检索
CHUNK = 800
OVERLAP = 100


def _tokens(s):
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


def _stamp(bid):
    b = get_book(bid)
    if not b:
        return {}
    st = {}
    for ch in flat_chapters(b):
        p = chapter_path(bid, ch["id"])
        try:
            st[ch["id"]] = int(os.path.getmtime(p))
        except OSError:
            st[ch["id"]] = 0
    return st


def build_index(bid, force=False):
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    ip = os.path.join(bdir(bid), "index.json")
    st = _stamp(bid)
    if not force:
        idx = _read_json(ip)
        if idx and idx.get("stamp") == st:
            return idx
    chunks = []
    for ch in flat_chapters(b):
        text = _read_text(chapter_path(bid, ch["id"]))
        if not text.strip():
            continue
        i = 0
        while i < len(text):
            seg = text[i:i + CHUNK]
            chunks.append({
                "cid": ch["id"], "no": ch["no"], "title": ch["title"],
                "vol": ch["volumeTitle"], "i": i, "text": seg,
                "len": len(_tokens(seg)),
            })
            if i + CHUNK >= len(text):
                break
            i += CHUNK - OVERLAP
    df = {}
    for c in chunks:
        for t in set(_tokens(c["text"])):
            df[t] = df.get(t, 0) + 1
    idx = {"stamp": st, "builtAt": time.time(), "N": len(chunks),
           "avgdl": (sum(c["len"] for c in chunks) / len(chunks)) if chunks else 0,
           "df": df, "chunks": chunks}
    _write_json(ip, idx)
    return idx


def search(bid, query, k=8):
    """BM25 + 精确子串加权。返回带章节定位的片段。"""
    query = (query or "").strip()
    if not query:
        return []
    idx = build_index(bid)
    chunks = idx.get("chunks") or []
    if not chunks:
        return []
    q_tokens = _tokens(query)
    if not q_tokens:
        return []
    df, N = idx["df"], max(idx["N"], 1)
    avgdl = idx["avgdl"] or 1
    k1, b_ = 1.5, 0.75
    # 查询里的实词串（≥2 汉字），用于精确命中加权
    phrases = [p for p in re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}", query)]
    scored = []
    for c in chunks:
        toks = _tokens(c["text"])
        tf = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for qt in set(q_tokens):
            f = tf.get(qt)
            if not f:
                continue
            idf = __import__("math").log(1 + (N - df.get(qt, 0) + 0.5) / (df.get(qt, 0) + 0.5))
            s += idf * (f * (k1 + 1)) / (f + k1 * (1 - b_ + b_ * len(toks) / avgdl))
        for p in phrases:
            if p in c["text"]:
                s += 2.5 * min(c["text"].count(p), 3)
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    out = []
    per_chapter = {}
    for s, c in scored:
        # 同一章最多取 2 段，避免整屏都是同一处
        if per_chapter.get(c["cid"], 0) >= 2:
            continue
        per_chapter[c["cid"]] = per_chapter.get(c["cid"], 0) + 1
        txt = c["text"]
        pos = 0
        for p in phrases:
            q = txt.find(p)
            if q >= 0:
                pos = q
                break
        start = max(0, pos - 60)
        snippet = txt[start:start + 320].replace("\n", " ").strip()
        out.append({
            "chapterId": c["cid"], "no": c["no"], "title": c["title"],
            "volume": c["vol"], "offset": c["i"], "score": round(s, 3),
            "snippet": ("…" if start > 0 else "") + snippet + "…",
        })
        if len(out) >= k:
            break
    return out


def locate(bid, name):
    """实体定位：第一次出现在第几章、共出现几次。纯字符串扫描，比向量准。"""
    name = (name or "").strip()
    if not name:
        return {"name": name, "hits": [], "first": None, "total": 0}
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    hits = []
    total = 0
    for ch in flat_chapters(b):
        text = _read_text(chapter_path(bid, ch["id"]))
        cnt = text.count(name)
        if cnt:
            total += cnt
            i = text.find(name)
            hits.append({
                "chapterId": ch["id"], "no": ch["no"], "title": ch["title"],
                "count": cnt, "offset": i,
                "snippet": text[max(0, i - 50):i + 80].replace("\n", " ").strip(),
            })
    return {"name": name, "hits": hits, "total": total,
            "first": hits[0] if hits else None}


def context_for(bid, cid, query="", budget=6000):
    """给写作时拉上下文：当前章前后 + 检索片段 + 相关设定。"""
    b = get_book(bid)
    if not b:
        return ""
    chs = flat_chapters(b)
    cur = next((c for c in chs if c["id"] == cid), None)
    parts = []
    used = 0
    prev_tail = ""
    outline = ""

    def take(label, text, cap):
        nonlocal used
        text = (text or "").strip()
        if not text:
            return
        room = min(cap, budget - used)
        if room < 200:
            return
        if len(text) > room:
            text = text[:room] + "\n……（略）"
        parts.append(label + "\n" + text)
        used += len(text)

    if cur:
        # 上一章结尾：续写最需要的锚点
        prev = next((c for c in chs if c["no"] == cur["no"] - 1), None)
        if prev:
            prev_tail = _read_text(chapter_path(bid, prev["id"]))[-1200:]
            take("## 上一章结尾（%s · %s）" % (prev["title"], prev["volumeTitle"]),
                 "……" + prev_tail, 1300)
        if cur.get("summary"):
            take("## 本章已有摘要", cur["summary"], 600)
        outline = _read_text(os.path.join(bdir(bid), "outline", "ch-" + _safe(cid) + ".md"))
        take("## 本章提纲", outline, 800)
        # 全书大纲只取方向，别让续写跑飞
        book_outline = _read_text(os.path.join(bdir(bid), "outline", "book.md")).strip()
        if book_outline:
            take("## 全书大纲（只作方向，不要照抄）", book_outline[:700], 760)

    # 检索：优先用作者给的指令，其次本章提纲，最后上一章结尾
    q = (query or "").strip()
    if not q:
        q = (outline or "").strip()[:220]
    if not q:
        q = prev_tail[-220:]
    hits = [h for h in (search(bid, q, k=6) if q else [])
            if not cur or h["chapterId"] != cid]
    if hits:
        lines = ["## 全书相关片段（按相关度）"]
        for h in hits[:4]:
            lines.append("【第%d章 %s】%s" % (h["no"], h["title"], h["snippet"]))
        take(lines[0], "\n".join(lines[1:]), 1900)

    # 设定库：只挑上下文里真的提到的人物
    bible = load_bible(bid)
    blob = (query or "") + "\n" + outline + "\n" + prev_tail + "\n" + \
        " ".join(h["snippet"] for h in hits[:3])
    picked = []
    for c in bible.get("characters", []):
        nm = c.get("name") or ""
        if nm and (nm in blob or any(a and a in blob for a in c.get("aliases", []))):
            picked.append("### " + nm + "\n" + _char_card(c))
    if picked:
        take("## 出场人物档案（必须与之一致）", "\n\n".join(picked[:5]), 2200)

    if bible.get("world"):
        take("## 世界观", bible["world"], 700)
    fs = [f for f in bible.get("foreshadow", []) if f.get("status") != "done"]
    if fs:
        take("## 未回收伏笔", "\n".join("- " + (f.get("title") or "") + "：" + (f.get("note") or "")
                                      for f in fs[:10]), 700)
    return "\n\n".join(parts)


def _char_card(c):
    bits = []
    for k, label in (("age", "年龄"), ("gender", "性别"), ("identity", "身份"),
                     ("appearance", "外貌"), ("personality", "性格"), ("speech", "说话方式"),
                     ("faction", "阵营")):
        v = (c.get(k) or "").strip()
        if v:
            bits.append("- %s：%s" % (label, v))
    if c.get("aliases"):
        bits.append("- 别名：" + "、".join(c["aliases"]))
    rel = c.get("relations") or []
    if rel:
        bits.append("- 关系：" + "；".join("%s（%s）" % (r.get("to", ""), r.get("type", "")) for r in rel[:8]))
    if c.get("notes"):
        bits.append("- 备注：" + c["notes"])
    return "\n".join(bits)


# ---------------------------------------------------------------- 校验（纯程序部分）
def check_terms(bid):
    """名词统一：把名词表里每个正名+别名扫全书，报出叫法不一致。"""
    bible = load_bible(bid)
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    chs = flat_chapters(b)
    issues = []
    for t in bible.get("terms", []):
        main = (t.get("main") or "").strip()
        if not main:
            continue
        names = [main] + [a.strip() for a in (t.get("aliases") or []) if a and a.strip()]
        counts = {}
        where = {}
        for ch in chs:
            text = _read_text(chapter_path(bid, ch["id"]))
            for nm in names:
                c = text.count(nm)
                if c:
                    counts[nm] = counts.get(nm, 0) + c
                    where.setdefault(nm, []).append("第%d章" % ch["no"])
        if len([n for n in counts if counts[n] > 0]) > 1:
            issues.append({
                "term": main, "kind": "mixed",
                "detail": "、".join("%s（%d次）" % (n, counts[n]) for n in counts),
                "where": where,
            })
    # 顺带扫：正文里出现但名词表没有的高频人名（连续2-3字 + 常见姓氏）
    known = set()
    for t in bible.get("terms", []):
        known.add(t.get("main") or "")
        known.update(t.get("aliases") or [])
    for c in bible.get("characters", []):
        known.add(c.get("name") or "")
        known.update(c.get("aliases") or [])
    return {"issues": issues, "known": len([k for k in known if k])}


SURNAME = "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴鬱胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍卻璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公"


def scan_names(bid, limit=40):
    """从正文抽候选专名，按出现次数排序，供建名词表用。
    同时统计 2 字与 3 字组合，再判断该是「林昭」还是「欧阳锋」。"""
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    pat = re.compile("[" + SURNAME + "]")
    bad_tail = set("的了着过是在有和与就都也还很太上下里外中前后间处边们么呢吧啊呀吗嘛这那哪个些样时面")
    c2, c3, first2, span2 = {}, {}, {}, {}
    for ch in flat_chapters(b):
        text = _read_text(chapter_path(bid, ch["id"]))
        for m in pat.finditer(text):
            i = m.start()
            w2 = text[i:i + 2]
            if len(w2) == 2 and re.fullmatch(r"[\u4e00-\u9fff]{2}", w2):
                c2[w2] = c2.get(w2, 0) + 1
                first2.setdefault(w2, ch["no"])
                span2.setdefault(w2, set()).add(ch["no"])
            w3 = text[i:i + 3]
            if len(w3) == 3 and re.fullmatch(r"[\u4e00-\u9fff]{3}", w3):
                c3[w3] = c3.get(w3, 0) + 1
    names = {}
    # 三字名：尾字不能是虚词/方位（否则是「林昭在」这种截断），且前两字几乎都出自它
    for w3, n3 in c3.items():
        if n3 < 3 or w3[-1] in bad_tail:
            continue
        n2 = c2.get(w3[:2], 0)
        if n3 >= n2 * 0.55:
            names[w3] = n3
            c2.pop(w3[:2], None)
    for w2, n2 in c2.items():
        # 真名会跨章反复出现；只在个别章扎堆的多半是普通词
        if n2 >= 3 and len(span2.get(w2, ())) >= 2:
            names[w2] = n2
    out = []
    for nm, n in sorted(names.items(), key=lambda x: -x[1]):
        if nm[-1] in bad_tail:
            continue
        out.append({"name": nm, "count": n, "firstChapter": first2.get(nm)})
        if len(out) >= limit:
            break
    return out


def check_rhythm(bid):
    """情绪节奏：纯统计。对话占比、场景描写占比、段落长度分布。"""
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    out = []
    for ch in flat_chapters(b):
        text = _read_text(chapter_path(bid, ch["id"]))
        if not text.strip():
            continue
        paras = [p.strip() for p in re.split(r"\n\s*\n|\n", text) if p.strip()]
        total = count_words(text)
        # 对话：引号内的内容
        dlg = re.findall(r"[“\"「『]([^”\"」』]{1,400})[”\"」』]", text)
        dlg_words = sum(count_words(x) for x in dlg)
        # 场景描写：非对话、非纯动作短句的段落
        desc_words = 0
        for p in paras:
            if re.search(r"[“\"「『]", p):
                continue
            if count_words(p) > 40:
                desc_words += count_words(p)
        out.append({
            "chapterId": ch["id"], "no": ch["no"], "title": ch["title"],
            "words": total, "paras": len(paras),
            "dialogue": round(dlg_words / total, 3) if total else 0,
            "scene": round(desc_words / total, 3) if total else 0,
            "avgPara": round(total / len(paras), 1) if paras else 0,
        })
    return out


def check_foreshadow(bid):
    """伏笔回收状态：把伏笔的埋设/回收章与实际正文对一遍。"""
    bible = load_bible(bid)
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    chs = flat_chapters(b)
    by_no = {c["no"]: c for c in chs}
    out = []
    for f in bible.get("foreshadow", []):
        title = (f.get("title") or "").strip()
        if not title:
            continue
        plant = f.get("plantChapter")
        payoff = f.get("payoffChapter")
        hit = [c["no"] for c in chs
               if title[:6] and title[:6] in _read_text(chapter_path(bid, c["id"]))]
        out.append({
            "title": title, "status": f.get("status") or "open",
            "plant": plant, "payoff": payoff,
            "foundIn": hit,
            "warn": (f.get("status") != "done" and not payoff and len(chs) - (int(plant or 0)) > 30),
        })
    return out


def check_ooc_candidates(bid, cid):
    """给 OOC 校验准备材料：本章涉及的人物 + 他们在别处的原话片段。"""
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    text = _read_text(chapter_path(bid, cid))
    bible = load_bible(bid)
    present = []
    for c in bible.get("characters", []):
        nm = c.get("name") or ""
        if nm and (nm in text or any(a and a in text for a in c.get("aliases", []))):
            present.append(c)
    return {"text": text, "characters": present}


# ---------------------------------------------------------------- 导出
def export_book(bid, fmt="md", split=False):
    b = get_book(bid)
    if not b:
        raise ValueError("书稿不存在")
    safe_title = re.sub(r'[\\/:*?"<>|]', "_", b.get("title") or "书稿")
    chs = flat_chapters(b)
    if split:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for c in chs:
                t = _read_text(chapter_path(bid, c["id"]))
                name = "%03d_%s.%s" % (c["no"], re.sub(r'[\\/:*?"<>|]', "_", c["title"]), fmt)
                body = ("# " + c["title"] + "\n\n" + t) if fmt == "md" else (c["title"] + "\n\n" + t)
                z.writestr(name, body)
            if fmt == "md":
                z.writestr("00_目录.md", _toc(b, chs))
        return safe_title + "_分章.zip", buf.getvalue()

    if fmt == "md":
        lines = ["# " + (b.get("title") or "书稿"), ""]
        if b.get("logline"):
            lines += ["> " + b["logline"], ""]
        lines += [_toc(b, chs), ""]
        for vi, v in enumerate(b["volumes"]):
            lines += ["# " + (v.get("title") or "第%d卷" % (vi + 1)), ""]
            for ch in v.get("chapters", []):
                lines += ["## " + (ch.get("title") or ""), "",
                          _read_text(chapter_path(bid, ch["id"])), ""]
        text = "\n".join(lines)
    else:
        lines = [(b.get("title") or "书稿"), ""]
        for vi, v in enumerate(b["volumes"]):
            lines += [v.get("title") or "第%d卷" % (vi + 1), ""]
            for ch in v.get("chapters", []):
                lines += [ch.get("title") or "", "",
                          _read_text(chapter_path(bid, ch["id"])), ""]
        text = "\n".join(lines)
    return safe_title + "." + fmt, text.encode("utf-8")


def _toc(b, chs):
    lines = ["## 目录", ""]
    cur = None
    for c in chs:
        if c["volumeTitle"] != cur:
            cur = c["volumeTitle"]
            lines.append("**" + cur + "**")
        lines.append("- " + c["title"])
    return "\n".join(lines)


def book_overview(bid):
    b = get_book(bid)
    if not b:
        return None
    chs = flat_chapters(b)
    bible = load_bible(bid)
    return {
        "book": b,
        "chapters": chs,
        "bible": bible,
        "outline": load_outline(bid),
        "stats": {
            "words": sum(c["words"] for c in chs),
            "chapters": len(chs),
            "volumes": len(b.get("volumes", [])),
            "characters": len(bible.get("characters", [])),
            "openForeshadow": len([f for f in bible.get("foreshadow", []) if f.get("status") != "done"]),
        },
        "drift": outline_drift(bid),
    }
