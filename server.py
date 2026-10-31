#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
砚 Inkstone — 本地写作智能体
零依赖（仅 Python 标准库）：HTTP 服务 + 多协议模型接入 + 技能库 + 本地存储
"""
import base64
import io
import json
import mimetypes
import os
import re
import shutil
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
import zipfile
import zlib
from html import unescape as html_unescape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlparse

import books
import corpus

FROZEN = getattr(sys, "frozen", False)

# 程序所在目录：打包后是 exe 所在目录，开发时是源码目录
APP_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.abspath(__file__))
# 资源目录：打包后是 PyInstaller 解压出的临时目录
RES_DIR = getattr(sys, "_MEIPASS", APP_DIR)

STATIC = os.path.join(RES_DIR, "static")
SKILLS_DIR = os.path.join(RES_DIR, "skills")

# 引导配置：记录用户自定义的数据目录。放在程序目录而不是 data 里，
# 否则一旦换了目录就再也读不到这条记录了。
BOOTSTRAP_PATH = os.path.join(APP_DIR, "inkstone.data.json")

DATA_SOURCE = "appdir"
DATA_WARNING = ""


def _load_bootstrap():
    try:
        with open(BOOTSTRAP_PATH, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save_bootstrap(obj):
    with open(BOOTSTRAP_PATH, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def _writable(d):
    try:
        os.makedirs(d, exist_ok=True)
        probe = os.path.join(d, ".writable")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("1")
        os.remove(probe)
        return True
    except Exception:
        return False


def _pick_data_dir():
    """优先级：用户自定义目录 → exe 旁边的 data（便携） → LOCALAPPDATA。"""
    global DATA_SOURCE, DATA_WARNING
    custom = (_load_bootstrap().get("dataDir") or "").strip()
    if custom:
        if _writable(custom):
            DATA_SOURCE = "custom"
            return custom
        DATA_WARNING = "自定义工作区不可用，已临时回退：" + custom
        print("[data]", DATA_WARNING)
    preferred = os.path.join(APP_DIR, "data")
    if _writable(preferred):
        if not DATA_WARNING:
            DATA_SOURCE = "appdir"
        return preferred
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    fallback = os.path.join(base, "Inkstone", "data")
    _writable(fallback)
    if not DATA_WARNING:
        DATA_SOURCE = "fallback"
    return fallback


DATA = _pick_data_dir()
CHATS = os.path.join(DATA, "chats")
BGS = os.path.join(DATA, "backgrounds")
USER_SKILLS = os.path.join(DATA, "skills")
CONFIG_PATH = os.path.join(DATA, "config.json")

for d in (DATA, CHATS, BGS, USER_SKILLS):
    os.makedirs(d, exist_ok=True)

MATERIAL_BUDGET = 24000   # 参考资料注入上限（字符）

_lock = threading.Lock()
books.init(DATA, _lock)
corpus.init(os.path.join(DATA, "corpus.db"))


# ---------------------------------------------------------------- 语料库
_CORPUS_RUN = {"running": False, "done": 0, "failed": 0, "log": [], "stop": False}


def corpus_overview():
    return {"overview": corpus.overview(), "books": corpus.list_books()}


def corpus_import(name, text):
    title = os.path.splitext(os.path.basename(name or "未命名"))[0]
    r = corpus.add_book(title, text, source=name)
    return r


def corpus_plan(plan="sample"):
    total = 0
    for b in corpus.list_books(1000):
        total += corpus.plan_jobs(b["sid"], plan).get("planned", 0)
    return {"ok": True, "planned": total, "plan": plan, "estimate": corpus.estimate()}


def corpus_style_all():
    n = 0
    for b in corpus.list_books(1000):
        if corpus.style_metrics(b["sid"]):
            n += 1
    return {"ok": True, "count": n}


def corpus_start(body):
    if _CORPUS_RUN.get("running"):
        return {"ok": False, "error": "已有蒸馏任务在跑"}
    cfg = load_config()
    p = find_provider(cfg, body.get("providerId"))
    if not p or not p.get("baseUrl"):
        return {"ok": False, "error": "没有可用的模型配置"}
    est = corpus.estimate()
    if not est["jobs"]:
        return {"ok": False, "error": "没有待办任务，先排任务"}
    conc = max(1, min(16, int(body.get("concurrency") or 4)))
    mx = int(body.get("max") or 0) or None
    _CORPUS_RUN.update({"running": True, "done": 0, "failed": 0, "log": [], "stop": False})

    def emit(kind, d):
        if kind == "done":
            _CORPUS_RUN["done"] = d.get("done", 0)
            _CORPUS_RUN["failed"] = d.get("failed", 0)
            _CORPUS_RUN["log"].append("第 %s 章 → %s" % (d.get("no", "?"), d.get("beat", "")))
        elif kind == "fail":
            _CORPUS_RUN["failed"] = d.get("failed", 0)
            _CORPUS_RUN["log"].append("失败 第 %s 章：%s" % (d.get("no", "?"), d.get("error", "")))
        _CORPUS_RUN["log"] = _CORPUS_RUN["log"][-80:]

    def work():
        try:
            corpus.run_jobs(
                {"kind": p.get("kind"), "baseUrl": p.get("baseUrl"),
                 "apiKey": p.get("apiKey"), "model": p.get("model")},
                concurrency=conc, max_jobs=mx, on_event=emit,
                should_stop=lambda: _CORPUS_RUN.get("stop"))
        except Exception as e:
            _CORPUS_RUN["log"].append("中断：" + str(e)[:120])
        finally:
            _CORPUS_RUN["running"] = False

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True, "estimate": est, "concurrency": conc}


# ---------------------------------------------------------------- 配置
DEFAULT_CONFIG = {
    "providers": [
        {"id": "deepseek", "name": "DeepSeek", "kind": "openai",
         "baseUrl": "https://api.deepseek.com/v1", "apiKey": "",
         "model": "deepseek-chat", "models": ["deepseek-chat", "deepseek-reasoner"]},
        {"id": "openai", "name": "OpenAI", "kind": "openai",
         "baseUrl": "https://api.openai.com/v1", "apiKey": "",
         "model": "gpt-4o-mini", "models": ["gpt-4o", "gpt-4o-mini", "gpt-4.1", "o4-mini"]},
        {"id": "anthropic", "name": "Anthropic Claude", "kind": "anthropic",
         "baseUrl": "https://api.anthropic.com", "apiKey": "",
         "model": "claude-sonnet-4-20250514",
         "models": ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-haiku-20241022"]},
        {"id": "moonshot", "name": "Moonshot Kimi", "kind": "openai",
         "baseUrl": "https://api.moonshot.cn/v1", "apiKey": "",
         "model": "kimi-k2-0905-preview", "models": ["kimi-k2-0905-preview", "moonshot-v1-32k", "moonshot-v1-128k"]},
        {"id": "zhipu", "name": "智谱 GLM", "kind": "openai",
         "baseUrl": "https://open.bigmodel.cn/api/paas/v4", "apiKey": "",
         "model": "glm-4-plus", "models": ["glm-4-plus", "glm-4-air", "glm-4-flash"]},
        {"id": "dashscope", "name": "通义千问", "kind": "openai",
         "baseUrl": "https://dashscope.aliyuncs.com/compatible-mode/v1", "apiKey": "",
         "model": "qwen-plus", "models": ["qwen-plus", "qwen-max", "qwen-turbo"]},
        {"id": "siliconflow", "name": "硅基流动", "kind": "openai",
         "baseUrl": "https://api.siliconflow.cn/v1", "apiKey": "",
         "model": "Qwen/Qwen2.5-72B-Instruct", "models": ["Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3"]},
        {"id": "openrouter", "name": "OpenRouter", "kind": "openai",
         "baseUrl": "https://openrouter.ai/api/v1", "apiKey": "",
         "model": "anthropic/claude-3.5-sonnet", "models": []},
        {"id": "ollama", "name": "Ollama（本地）", "kind": "ollama",
         "baseUrl": "http://localhost:11434", "apiKey": "",
         "model": "qwen2.5:7b", "models": ["qwen2.5:7b", "qwen2.5:14b", "llama3.1:8b", "deepseek-r1:7b"]},
        {"id": "lmstudio", "name": "LM Studio（本地）", "kind": "openai",
         "baseUrl": "http://localhost:1234/v1", "apiKey": "lm-studio",
         "model": "local-model", "models": []},
        {"id": "vllm", "name": "vLLM / 自定义", "kind": "openai",
         "baseUrl": "http://localhost:8000/v1", "apiKey": "", "model": "", "models": []},
    ],
    "activeProviderId": "deepseek",
    "params": {"temperature": 0.85, "maxTokens": 8192, "topP": 0.95, "ctx": 8192},
    "prefs": {"language": "中文", "tone": "", "length": "", "rules": ""},
    "appearance": {"theme": "paper", "accent": None, "radius": None, "fontSize": 17,
                   "panelOpacity": None, "backgroundId": None, "intensity": 0.5,
                   "blur": 0, "dim": 0.12},
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k == "providers" and isinstance(v, list) and v:
                    cfg["providers"] = v
                elif isinstance(v, dict) and isinstance(cfg.get(k), dict):
                    cfg[k].update(v)
                else:
                    cfg[k] = v
        except Exception as e:
            print("[config] 读取失败，使用默认配置:", e)
    # 老版本的默认输出上限是 4096，长回答会被截断，统一抬到 8192
    if cfg.get("params", {}).get("maxTokens") == 4096:
        cfg["params"]["maxTokens"] = 8192
    return cfg


def save_config(cfg):
    with _lock:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- 技能库
def derive_stages(body):
    """没有 stages 的导入技能：用 ## 标题生成阶段按钮。"""
    out = []
    for m in re.finditer(r"^##\s+(.+)$", body, re.M):
        title = m.group(1).strip().strip("*# ")
        if not title or len(title) > 20:
            continue
        out.append({"name": title[:12], "hint": "按「" + title + "」这一节的要求处理下面的内容。"})
        if len(out) >= 6:
            break
    if not out:
        out = [{"name": "按此技能处理", "hint": "按这个技能的规则处理下面的内容。"}]
    return out


def slugify(name):
    s = re.sub(r"[^\w\u4e00-\u9fa5-]+", "-", (name or "").strip().lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:40] or ("skill-" + uuid.uuid4().hex[:6])


def parse_skill(text, filename, source="builtin"):
    meta = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            head, body = parts[1], parts[2]
            for line in head.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                k, v = k.strip(), v.strip()
                if k == "stages":
                    try:
                        meta["stages"] = json.loads(v)
                    except Exception:
                        meta["stages"] = []
                else:
                    meta[k] = v
    stem = os.path.splitext(filename)[0]
    if not meta.get("id"):
        meta["id"] = slugify(meta.get("name") or stem)
    if not meta.get("name"):
        meta["name"] = meta["id"]
    meta.setdefault("category", "其他")
    if not meta.get("tag"):
        desc = meta.get("description") or ""
        meta["tag"] = re.sub(r"[，。,.!！].*$", "", desc)[:10]
    meta.setdefault("accent", "#B23A2F")
    meta.setdefault("stages", [])
    if not meta["stages"]:
        meta["stages"] = derive_stages(body)
    meta["source"] = source
    meta["editable"] = source == "user"
    meta["prompt"] = body.strip()
    return meta


def load_skills():
    out = []
    seen = set()
    for d, source in ((SKILLS_DIR, "builtin"), (USER_SKILLS, "user")):
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.endswith(".md"):
                continue
            try:
                with open(os.path.join(d, fn), "r", encoding="utf-8") as f:
                    sk = parse_skill(f.read(), fn, source)
            except Exception as e:
                print("[skills] 跳过", fn, e)
                continue
            if sk["id"] in seen:
                print("[skills] id 重复，跳过", fn)
                continue
            seen.add(sk["id"])
            out.append(sk)
    order = ["book-analysis", "novel-engine", "chapter-craft", "scene-craft",
             "character-world", "interactive", "short-drama", "deai", "review",
             "seven-step", "wechat-article", "official-doc", "brand-voice",
             "longform", "doc-coauthor", "research-deep", "work-comms",
             "academic", "academic-polish"]
    out.sort(key=lambda s: order.index(s["id"]) if s["id"] in order else 99)
    return out


def write_user_skill(sk):
    fm = ["---",
          "id: " + sk["id"],
          "name: " + sk["name"],
          "category: " + sk["category"],
          "tag: " + sk["tag"],
          "accent: " + sk["accent"],
          "stages: " + json.dumps(sk["stages"], ensure_ascii=False),
          "---", ""]
    path = os.path.join(USER_SKILLS, sk["id"] + ".md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(fm) + "\n" + sk["prompt"] + "\n")
    return path


def import_skills(filename, raw):
    """接受单个 .md 或一个 .zip（可含 Claude 插件结构），返回导入结果。"""
    name = (filename or "").lower()
    items = []
    if name.endswith(".zip"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for info in z.infolist():
                    if info.is_dir() or "__MACOSX" in info.filename:
                        continue
                    if not info.filename.lower().endswith((".md", ".markdown")):
                        continue
                    if info.file_size > 3 * 1024 * 1024:
                        continue
                    try:
                        items.append((os.path.basename(info.filename),
                                      z.read(info).decode("utf-8", "ignore")))
                    except Exception:
                        continue
        except Exception as e:
            raise ValueError("zip 解析失败：" + str(e))
    elif name.endswith((".md", ".markdown", ".txt")):
        items.append((filename, raw.decode("utf-8", "ignore")))
    else:
        raise ValueError("只支持 .md 或 .zip")

    imported, skipped = [], []
    existing = {s["id"] for s in SKILLS}
    for fn, text in items:
        if len(text.strip()) < 120:
            skipped.append({"file": fn, "reason": "内容太短"})
            continue
        try:
            sk = parse_skill(text, fn, "user")
        except Exception as e:
            skipped.append({"file": fn, "reason": str(e)[:60]})
            continue
        if len(sk["prompt"]) < 120:
            skipped.append({"file": fn, "reason": "正文太短"})
            continue
        base = sk["id"] if sk["id"] not in existing else sk["id"] + "-" + uuid.uuid4().hex[:4]
        sk["id"] = base
        if sk["category"] in ("其他", ""):
            sk["category"] = "导入"
        existing.add(sk["id"])
        write_user_skill(sk)
        imported.append({"id": sk["id"], "name": sk["name"],
                         "stages": len(sk["stages"]), "chars": len(sk["prompt"])})
    return imported, skipped


TEXT_EXTS = (".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log",
             ".srt", ".yaml", ".yml", ".ini", ".rst")


def _decode_text(raw):
    for enc in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "ignore")


def _strip_tags(t):
    t = re.sub(r"(?is)<(script|style|head)[^>]*>.*?</\1>", " ", t)
    t = re.sub(r"(?is)<br\s*/?>", "\n", t)
    t = re.sub(r"(?is)</(p|div|h[1-6]|li|tr|section)>", "\n", t)
    t = re.sub(r"(?s)<[^>]+>", "", t)
    t = html_unescape(t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _zip_read(raw, want):
    out = []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        for info in z.infolist():
            if info.is_dir() or "__MACOSX" in info.filename:
                continue
            if want(info.filename.lower()) and info.file_size < 8 * 1024 * 1024:
                out.append(z.read(info))
    return out


def extract_text(filename, raw):
    """把导入的文件转成纯文本。支持 txt/md/csv/json/html/docx/epub，pdf 尽力而为。"""
    name = (filename or "").lower()
    ext = os.path.splitext(name)[1]
    if ext in TEXT_EXTS:
        return _decode_text(raw)
    if ext in (".html", ".htm", ".xhtml"):
        return _strip_tags(_decode_text(raw))
    if ext == ".docx":
        parts = []
        for data in _zip_read(raw, lambda f: f.endswith("word/document.xml")):
            xml = data.decode("utf-8", "ignore")
            xml = xml.replace("</w:p>", "\n").replace("<w:br/>", "\n").replace("<w:tab/>", "\t")
            parts.append(_strip_tags(xml))
        return "\n".join(parts).strip()
    if ext == ".epub":
        parts = [_strip_tags(d.decode("utf-8", "ignore"))
                 for d in _zip_read(raw, lambda f: f.endswith((".xhtml", ".html", ".htm")))]
        return "\n\n".join(p for p in parts if p).strip()
    if ext == ".pdf":
        chunks = []
        for m in re.finditer(rb"stream\r?\n(.*?)endstream", raw, re.S):
            try:
                data = zlib.decompress(m.group(1))
            except Exception:
                continue
            for tm in re.finditer(rb"\((?:\\.|[^\\)])*\)", data):
                t = tm.group(0)[1:-1]
                t = t.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
                chunks.append(t.decode("latin-1", "ignore"))
        text = " ".join(chunks)
        good = sum(1 for ch in text if ch.isprintable() and ch not in "\ufffd")
        if len(text) < 120 or good < len(text) * 0.85:
            raise ValueError("这个 PDF 提取不出文字（可能是扫描件或用了特殊字体），"
                             "请另存为 docx 或 txt 再导入")
        return text
    raise ValueError("暂不支持 %s 格式，可用 txt / md / docx / epub / html" % (ext or "这个"))


SKILLS = load_skills()
SKILL_MAP = {s["id"]: s for s in SKILLS}


def reload_skills():
    global SKILLS, SKILL_MAP
    SKILLS = load_skills()
    SKILL_MAP = {s["id"]: s for s in SKILLS}


# ---------------------------------------------------------------- 会话存储
def conv_path(cid):
    return os.path.join(CHATS, cid + ".json")


def list_conversations():
    items = []
    for fn in os.listdir(CHATS):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(CHATS, fn), "r", encoding="utf-8") as f:
                c = json.load(f)
            msgs = c.get("messages", [])
            preview = ""
            for m in reversed(msgs):
                if m.get("role") == "assistant" and m.get("content"):
                    preview = m["content"][:80].replace("\n", " ")
                    break
            items.append({
                "id": c["id"], "title": c.get("title") or "未命名创作",
                "skillId": c.get("skillId"), "updatedAt": c.get("updatedAt", 0),
                "messageCount": len(msgs), "preview": preview,
                "workflowId": c.get("workflowId") or "",
                "hasProject": bool([v for v in (c.get("project") or {}).values() if v]),
                "projectTitle": ((c.get("project") or {}).get("title") or "").strip(),
            })
        except Exception:
            continue
    items.sort(key=lambda x: x["updatedAt"], reverse=True)
    return items


def get_conversation(cid):
    p = conv_path(cid)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_conversation(c):
    c["updatedAt"] = time.time()
    with _lock:
        with open(conv_path(c["id"]), "w", encoding="utf-8") as f:
            json.dump(c, f, ensure_ascii=False, indent=1)


def save_partial(conv, text, cont, reason):
    """流式中途断掉时，把已经生成的部分落盘，别让用户白等。"""
    if not text:
        return
    if cont and conv["messages"] and conv["messages"][-1]["role"] == "assistant":
        m = conv["messages"][-1]
        m["content"] = (m.get("content") or "") + text
        m["incomplete"] = True
        m["finish"] = reason
    else:
        conv["messages"].append({"role": "assistant", "content": text,
                                 "skillId": conv.get("skillId"), "ts": time.time(),
                                 "incomplete": True, "finish": reason})
    save_conversation(conv)


def new_conversation(skill_id="novel-engine", title=None):
    c = {"id": uuid.uuid4().hex[:12], "title": title or "未命名创作",
         "skillId": skill_id, "createdAt": time.time(), "updatedAt": time.time(),
         "messages": [], "project": {}}
    save_conversation(c)
    return c


# ---------------------------------------------------------------- 提示词
BASE_IDENTITY = """你是「砚 Inkstone」——一个中文写作智能体。你只做一件事：帮用户把想法写成作品。

工作方式：
- 直接产出内容，不寒暄、不自我介绍、不复述用户的指令、不解释你正在做什么。
- 需要澄清时，一次最多问 3 个最关键的问题，并同时给出你的默认假设，让用户可以直接说「按你的来」。
- 用 Markdown 组织输出；长文分段交付，一段写完可以停下来等反馈。
- 不编造事实、数据、文献、引文。不确定的标【待考】或「待核实」。
- 中文输出（除非用户要求其他语言）。"""

OUTPUT_RULES = """# 输出纪律
1. 正文里不出现 [说明]、TODO、括号旁白等元信息。
2. 不用「首先/其次/最后」「综上所述」「总而言之」这类结构性套话。
3. 少用条目式罗列，能用连贯段落说清的就用段落。
4. 具体优于抽象：写动作、写细节、写数字，不写「意义深远」「令人震撼」。
5. 一次只做用户要求的那件事，不顺手扩写别的部分。"""


BASE_WRITER = """你是「砚 Inkstone」的写作引擎，正在参与一部长篇小说的创作。

铁律：
- 直接写正文。不写「好的」「以下是」这类开场，不写解释、不写批注、不写"（未完待续）"。
- 只写中文正文，段落之间空一行，不用小标题拆分。
- 严格遵守上文给出的人物设定、世界规则、时间地点。有冲突时以上文为准。
- 不复述、不总结已有情节。该往下写就往下写。
- 不替作者下判断，不写"这一段很精彩"之类的元评论。"""

WRITE_MODES = {
    "continue": "接着上文往下写。不要重复上文已有句子，不要总结前情，直接从下一个动作或下一句对白开始。写 600-1200 字，停在一个有张力的位置。",
    "polish": "润色下面这段文字：保留原意、情节和人物口吻，改掉重复句式、口水词、翻译腔、形容词堆砌。只输出改后的正文。",
    "expand": "扩写下面这段：加入具体的动作、感官细节、环境反应和人物微表情，篇幅约为原文 1.8 倍。不要新增情节支线。只输出正文。",
    "condense": "压缩下面这段：删掉冗余修饰和重复信息，保留全部关键情节与对白，篇幅约为原文 0.6 倍。只输出正文。",
    "pov": "把下面这段改用 {persona} 的第一人称内心视角重写：事件不变，换成这个人物会注意到的细节、会有的判断、会压下去的情绪。只输出正文。",
    "dialog": "重写下面这段对话：让每个人的说话方式明显区分（用词、句长、称谓、口头习惯），删掉寒暄和重复信息，能靠潜台词说的不要直说。只输出正文。",
}

SUMMARY_SYS = """你在为一部长篇小说做章节摘要。只输出 JSON，不要任何解释、不要代码块围栏。

{"summary":"150字以内的本章剧情摘要，按事件顺序，写清谁做了什么、结果如何",
 "events":["关键事件"],
 "characters":["出场人物"],
 "hooks":["本章埋下或推进的伏笔"],
 "payoff":["本章回收的伏笔"]}

要求：summary 用陈述句，不加评论；events 最多 5 条、每条 20 字内；只写正文里确实发生的事，不推测。"""

VOLUME_SUM_SYS = """你在为一卷小说写卷梗概。输出 400 字以内的连贯段落，按时间顺序讲清这一卷的主线推进、主要矛盾的变化、卷末留下的悬念。不加评论，不写"本卷讲述了"。"""

BOOK_SUM_SYS = """你在为整本书写梗概。输出 600 字以内的连贯段落：核心冲突是什么、主角的目标如何变化、几条主要线索如何交织、结局落在哪里。不加评论。"""

OOC_SYS = """你在做长篇小说的人物一致性审校。只输出 JSON，不要解释。

{"issues":[{"level":"high|mid|low","character":"人物名","type":"性格|外貌|年龄|身份|台词|能力|关系",
 "quote":"原文片段，不超过40字","why":"和设定的哪一条冲突","fix":"具体怎么改"}]}

判定标准：
- 只有和「人物档案」明确写着的设定冲突，才算问题。档案没写的，不算冲突。
- 台词风格突变：用词习惯、句子长短、对长辈/下属的称谓与该人物一贯风格明显不符。
- 没有问题时输出 {"issues":[]}。不要为了凑数编问题。"""

REL_SYS = """你在整理长篇小说的人物关系图。只输出 JSON，不要解释。

{"nodes":[{"id":"人物名","group":"阵营或身份","note":"一句话定位"}],
 "edges":[{"from":"A","to":"B","type":"师徒|父子|敌对|盟友|上下级|暗恋|旧识","note":"恩怨由来","weight":1}]}

要求：只输出档案和摘要里能确认的关系，不要编。weight 取 1-5，表示关系强度。"""

BRANCH_SYS = """你在做剧情分支推演。只输出 JSON，不要解释。

{"branches":[{"title":"走向名","logic":"这一走向如何从当前节点自然长出来，50字内",
 "scene":"接下来会发生什么，150字内，要能直接当正文的场景梗概",
 "cost":"这条走向的代价或风险",
 "foreshadow":{"recover":["能回收的伏笔"],"new":["会新埋的伏笔"]},
 "score":1}]}

要求：给 3 条，必须真的不同（不是同一件事的三种说法）。score 取 1-5，衡量的是"对全书结构的贡献"，不是"爽不爽"。"""


def _json_of(text):
    """从模型输出里抠出 JSON，容忍代码围栏和尾逗号。"""
    if not text:
        return None
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s, flags=re.S)
    m = re.search(r"\{[\s\S]*\}", s)
    if not m:
        return None
    raw = m.group(0)
    for attempt in (raw, re.sub(r",\s*([}\]])", r"\1", raw)):
        try:
            return json.loads(attempt)
        except Exception:
            continue
    return None


def _write_json_soft(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print("[books] 写文件失败:", e)


def _save_chapter_meta(bid, cid, data):
    b = books.get_book(bid)
    if not b:
        return
    v, ch = books.find_chapter(b, cid)
    if not ch:
        return
    ch["summary"] = (data.get("summary") or "").strip()
    ch["events"] = data.get("events") or []
    ch["hooks"] = data.get("hooks") or []
    ch["payoff"] = data.get("payoff") or []
    books.save_book(b)


def build_system(skill, conv, prefs):
    parts = [BASE_IDENTITY]
    if skill:
        parts.append("# 当前技能：" + skill["name"] + "\n\n" + skill["prompt"])
    proj = (conv or {}).get("project") or {}
    fields = [
        ("作品名", "title"), ("类型 / 题材", "genre"), ("目标读者", "audience"),
        ("一句话故事", "logline"), ("人物设定", "characters"), ("世界观与规则", "world"),
        ("大纲", "outline"), ("文风要求", "style"), ("其他备注", "notes"),
    ]
    filled = [(label, proj.get(k, "").strip()) for label, k in fields if (proj.get(k) or "").strip()]
    if filled:
        block = ["# 创作档案（真值层）",
                 "以下设定是本书唯一事实来源。与你的记忆冲突时，一律以此为准；如需改动，先说明影响范围。", ""]
        for label, val in filled:
            block.append("## " + label + "\n" + val)
        parts.append("\n".join(block))
    p = prefs or {}
    if any((p.get(k) or "").strip() for k in ("language", "tone", "length")):
        block = ["# 写作偏好"]
        if p.get("language"):
            block.append("- 语言：" + p["language"])
        if p.get("tone"):
            block.append("- 语气：" + p["tone"])
        if p.get("length"):
            block.append("- 篇幅：" + p["length"])
        parts.append("\n".join(block))

    # 参考资料（导入的文件）
    mats = (conv or {}).get("materials") or []
    if mats:
        block = ["# 参考资料（作者导入）",
                 "以下材料是作者提供的原文，写作时以它为准；引用其中的事实、名称、数字时不要改动。", ""]
        used = 0
        for m in mats:
            txt = (m.get("text") or "").strip()
            if not txt:
                continue
            room = MATERIAL_BUDGET - used
            if room <= 0:
                block.append("（其余材料因长度限制未载入）")
                break
            if len(txt) > room:
                txt = txt[:room] + "\n……（后文略）"
            used += len(txt)
            block.append("## " + (m.get("name") or "材料") + "\n" + txt)
        parts.append("\n".join(block))

    parts.append(OUTPUT_RULES)

    rules = [r.strip(" -·\t") for r in (p.get("rules") or "").splitlines()]
    rules = [r for r in rules if r]
    if rules:
        block = ["# 规则词（最高优先级）",
                 "以下规则由作者亲自设定。它们优先于上面所有写作习惯、技能要求和默认风格；"
                 "与技能冲突时，以本节为准。违反其中任何一条都算失败。", ""]
        for i, r in enumerate(rules, 1):
            block.append("%d. %s" % (i, r))
        parts.append("\n".join(block))

    return "\n\n".join(parts)


# ---------------------------------------------------------------- 模型接入
class ProviderError(Exception):
    pass


def normalize_openai_base(base):
    b = (base or "").strip().rstrip("/")
    if not b:
        raise ProviderError("未填写 API 地址")
    if b.endswith("/chat/completions"):
        return b
    if re.search(r"/v\d+$", b) or b.endswith("/compatible-mode/v1") or b.endswith("/api/paas/v4"):
        return b + "/chat/completions"
    return b + "/v1/chat/completions"


def _opener(url):
    """本地回环地址强制绕过系统代理，否则 Ollama / LM Studio 会被代理拦成 502。"""
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or host.endswith(".local"):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def http_post(url, payload, headers, timeout=300):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        if v:
            req.add_header(k, v)
    try:
        return _opener(url).open(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "ignore")[:600]
        except Exception:
            pass
        hint = {
            401: "API Key 无效或未授权",
            403: "访问被拒绝（检查 Key 权限或模型权限）",
            404: "接口或模型不存在（检查 Base URL 与模型名）",
            429: "请求过于频繁或额度不足",
        }.get(e.code, "")
        raise ProviderError(f"HTTP {e.code} {hint}\n{body}")
    except urllib.error.URLError as e:
        raise ProviderError(f"无法连接模型服务：{e.reason}\n（本地模型请确认 Ollama / LM Studio 已启动）")
    except Exception as e:
        raise ProviderError(f"请求失败：{e}")


def stream_openai(p, messages, params, emit):
    url = normalize_openai_base(p.get("baseUrl"))
    mt = int(params.get("maxTokens", 8192) or 0)
    payload = {
        "model": p.get("model") or "",
        "messages": messages,
        "stream": True,
        "temperature": params.get("temperature", 0.85),
        "top_p": params.get("topP", 0.95),
    }
    if mt > 0:
        payload["max_tokens"] = mt
    headers = {"Authorization": "Bearer " + (p.get("apiKey") or "sk-local"),
               "Accept": "text/event-stream"}
    if "openrouter" in url:
        headers["HTTP-Referer"] = "http://localhost"
        headers["X-Title"] = "Inkstone"
    resp = http_post(url, payload, headers)
    full = []
    finish = None
    for raw in resp:
        line = raw.decode("utf-8", "ignore").strip()
        if not line or not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if chunk in ("[DONE]", ""):
            break
        try:
            obj = json.loads(chunk)
        except Exception:
            continue
        if obj.get("error"):
            raise ProviderError(str(obj["error"])[:400])
        choices = obj.get("choices") or []
        if not choices:
            continue
        fr = choices[0].get("finish_reason")
        if fr:
            finish = fr
        delta = choices[0].get("delta") or {}
        piece = delta.get("content") or ""
        if not piece and delta.get("reasoning_content"):
            piece = ""  # 思考过程不写入正文
        if piece:
            full.append(piece)
            emit(piece)
    return "".join(full), finish


def stream_anthropic(p, messages, params, emit):
    base = (p.get("baseUrl") or "https://api.anthropic.com").rstrip("/")
    url = base + "/v1/messages"
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    conv = [m for m in messages if m["role"] in ("user", "assistant")]
    if conv and conv[0]["role"] == "assistant":
        conv.insert(0, {"role": "user", "content": "继续。"})
    mt = int(params.get("maxTokens", 8192) or 0)
    payload = {
        "model": p.get("model") or "",
        "system": system,
        "messages": conv,
        "max_tokens": mt if mt > 0 else 8192,
        "temperature": params.get("temperature", 0.85),
        "stream": True,
    }
    headers = {"x-api-key": p.get("apiKey") or "",
               "anthropic-version": "2023-06-01",
               "Accept": "text/event-stream"}
    resp = http_post(url, payload, headers)
    full = []
    finish = None
    for raw in resp:
        line = raw.decode("utf-8", "ignore").strip()
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        try:
            obj = json.loads(chunk)
        except Exception:
            continue
        t = obj.get("type")
        if t == "error":
            raise ProviderError(str(obj.get("error"))[:400])
        if t == "content_block_delta":
            piece = (obj.get("delta") or {}).get("text") or ""
            if piece:
                full.append(piece)
                emit(piece)
        elif t == "message_delta":
            finish = (obj.get("delta") or {}).get("stop_reason") or finish
    return "".join(full), finish


def stream_ollama(p, messages, params, emit):
    base = (p.get("baseUrl") or "http://localhost:11434").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    url = base + "/api/chat"
    mt = int(params.get("maxTokens", 8192) or 0)
    opts = {
        "temperature": params.get("temperature", 0.85),
        "top_p": params.get("topP", 0.95),
    }
    if mt > 0:
        opts["num_predict"] = mt
    # Ollama 默认上下文只有 4k，长篇的设定 + 历史会被截掉，导致答到一半就停
    ctx = int(params.get("ctx") or 8192)
    if ctx > 0:
        opts["num_ctx"] = ctx
    payload = {
        "model": p.get("model") or "",
        "messages": messages,
        "stream": True,
        "options": opts,
        "keep_alive": params.get("keepAlive") or "30m",
    }
    headers = {}
    if p.get("apiKey"):
        headers["Authorization"] = "Bearer " + p["apiKey"]
    resp = http_post(url, payload, headers)
    full = []
    finish = None
    for raw in resp:
        line = raw.decode("utf-8", "ignore").strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("error"):
            raise ProviderError(str(obj["error"])[:400])
        piece = (obj.get("message") or {}).get("content") or ""
        if piece:
            full.append(piece)
            emit(piece)
        if obj.get("done"):
            finish = obj.get("done_reason") or "stop"
            break
    return "".join(full), finish


SUMMARY_PROMPT = """把下面这段创作对话压缩成一份「前情提要」，供后续继续写作时参考。

必须保留：
- 人物：姓名、身份、彼此关系
- 设定：已确定的世界观、地名、规则、时间线
- 情节：已发生的关键事件，按顺序
- 伏笔：埋下但还没回收的线索
- 作者偏好：明确说过要什么、不要什么
- 进度：现在写到哪

必须删掉：寒暄、重复解释、被否掉的方案、过程性讨论、AI 的自述。

写法：条目式，不要写成文章，总长控制在 800 字以内。
只写对话里真实出现过的信息，不要补充，不要推测，不要评价。

已有提要（如果有，合并进去，不要重复）：
{prev}

对话原文：
{body}
"""


def conv_chars(msgs):
    return sum(len(m.get("content") or "") for m in msgs)


def compress_conversation(conv, provider, params, keep=6):
    """把较早的消息合并成前情提要。返回统计信息；不需要压缩时返回 None。"""
    msgs = conv.get("messages") or []
    start = int(conv.get("summaryCount") or 0)   # 已经压过的部分不再重复压
    pending = msgs[start:]
    if len(pending) <= keep + 2:
        return None
    cut = len(msgs) - keep
    old = msgs[start:cut]
    lines = []
    for m in old:
        who = "作者" if m.get("role") == "user" else "助手"
        txt = (m.get("content") or "").strip()
        if txt:
            lines.append(who + "：" + txt[:3000])
    body = "\n\n".join(lines)
    if not body.strip():
        return None

    prompt = SUMMARY_PROMPT.format(prev=conv.get("summary") or "（无）", body=body[:80000])
    sp = {"temperature": 0.3, "maxTokens": 2400}
    out = run_model(provider, [{"role": "user", "content": prompt}], sp, lambda _p: None)
    text = out[0] if isinstance(out, tuple) else out
    text = (text or "").strip()
    if not text:
        return None

    before = conv_chars(msgs)
    conv["summary"] = text
    conv["summaryCount"] = cut
    conv["summaryAt"] = time.time()
    save_conversation(conv)
    after = conv_chars(msgs[cut:]) + len(text)
    return {"merged": cut, "before": before, "after": after,
            "summary": text, "kept": len(msgs) - cut}


def run_model(provider, messages, params, emit):
    kind = provider.get("kind", "openai")
    if kind == "anthropic":
        return stream_anthropic(provider, messages, params, emit)
    if kind == "ollama":
        return stream_ollama(provider, messages, params, emit)
    return stream_openai(provider, messages, params, emit)


def dir_size(path):
    total = 0
    try:
        for root, _dirs, files in os.walk(path):
            for fn in files:
                try:
                    total += os.path.getsize(os.path.join(root, fn))
                except OSError:
                    pass
    except Exception:
        pass
    return total


def storage_info():
    sizes = {
        "books": dir_size(os.path.join(DATA, "books")),
        "chats": dir_size(CHATS),
        "backgrounds": dir_size(BGS),
        "skills": dir_size(USER_SKILLS),
    }
    custom = (_load_bootstrap().get("dataDir") or "").strip()
    return {
        "dataDir": DATA,
        "appDir": APP_DIR,
        "bootstrap": BOOTSTRAP_PATH,
        "custom": custom,
        "source": DATA_SOURCE,
        "warning": DATA_WARNING,
        "sizes": sizes,
        "total": dir_size(DATA),
        "isDefault": not custom,
        "defaultDir": os.path.join(APP_DIR, "data"),
    }


def move_data(new_dir):
    """把当前工作区复制到新位置，并记进引导配置。原目录保留不动。"""
    new_dir = os.path.abspath((new_dir or "").strip().strip('"').strip("'"))
    if not new_dir:
        raise ValueError("请填写新的文件夹路径")
    if os.path.normcase(new_dir) == os.path.normcase(DATA):
        raise ValueError("这就是当前的工作区")
    parent = os.path.dirname(new_dir)
    if parent and not os.path.isdir(parent):
        raise ValueError("上级目录不存在：" + parent)
    if not _writable(new_dir):
        raise ValueError("这个文件夹不可写，换一个试试")
    if os.listdir(new_dir):
        raise ValueError("目标文件夹不是空的，请选一个空文件夹")
    # 先确认能把设置写进程序目录，免得复制完才发现存不下
    probe = os.path.join(APP_DIR, ".ws_probe")
    try:
        with open(probe, "w", encoding="utf-8") as f:
            f.write("1")
        os.remove(probe)
    except Exception:
        raise ValueError("软件所在目录不可写，无法保存位置设置。把软件放到可写目录再试。")
    for name in os.listdir(DATA):
        src = os.path.join(DATA, name)
        dst = os.path.join(new_dir, name)
        try:
            if os.path.isdir(src):
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        except Exception as e:
            raise ValueError("复制 %s 失败：%s" % (name, e))
    _save_bootstrap({"dataDir": new_dir})
    return new_dir


def reset_data_dir():
    if os.path.exists(BOOTSTRAP_PATH):
        try:
            os.remove(BOOTSTRAP_PATH)
        except OSError as e:
            raise ValueError("无法清除设置：%s" % e)
    return os.path.join(APP_DIR, "data")


def ask_model(provider, params, system, user, max_tokens=1600, temperature=0.3):
    """一次性拿完整回答（摘要、校验、图谱这类不需要流式的活儿）。"""
    p = dict(params or {})
    p["maxTokens"] = max_tokens
    p["temperature"] = temperature
    buf = []
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    text, _finish = run_model(provider, msgs, p, lambda x: buf.append(x))
    return "".join(buf) or (text or "")


def find_provider(cfg, pid=None):
    pid = pid or cfg.get("activeProviderId")
    for p in cfg["providers"]:
        if p["id"] == pid:
            return p
    return cfg["providers"][0]


# ---------------------------------------------------------------- 背景图
def list_backgrounds():
    items = []
    for fn in sorted(os.listdir(BGS), reverse=True):
        if fn.startswith("."):
            continue
        p = os.path.join(BGS, fn)
        items.append({"id": fn, "url": "/backgrounds/" + fn,
                      "name": os.path.splitext(fn)[1].lstrip(".").upper() + " 图片",
                      "size": os.path.getsize(p),
                      "createdAt": os.path.getctime(p)})
    return items


# ---------------------------------------------------------------- HTTP
class Handler(BaseHTTPRequestHandler):
    server_version = "Inkstone/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        if "/api/chat" in (self.path or ""):
            return
        print("  %s %s" % (self.command, self.path))

    # -- helpers
    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text, code=200, ctype="text/plain; charset=utf-8", extra=None):
        body = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def read_json(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0:
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def serve_file(self, path, cache="no-store"):
        if not os.path.isfile(path):
            self.send_text("Not Found", 404)
            return
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype in ("application/javascript",):
            ctype += "; charset=utf-8"
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.end_headers()
        self.wfile.write(body)

    # -- routing
    def do_GET(self):
        u = urlparse(self.path)
        path = unquote(u.path)
        try:
            if path in ("/", "/index.html"):
                return self.serve_file(os.path.join(STATIC, "index.html"))
            if path.startswith("/static/"):
                rel = path[len("/static/"):].replace("\\", "/")
                full = os.path.normpath(os.path.join(STATIC, rel))
                if not full.startswith(os.path.normpath(STATIC)):
                    return self.send_text("Forbidden", 403)
                return self.serve_file(full)
            if path.startswith("/backgrounds/"):
                return self.serve_file(os.path.join(BGS, os.path.basename(path)), "max-age=86400")
            if path == "/api/bootstrap":
                return self.send_json({
                    "skills": SKILLS,
                    "config": load_config(),
                    "conversations": list_conversations(),
                    "backgrounds": list_backgrounds(),
                })
            if path == "/api/skills":
                return self.send_json({"skills": SKILLS})
            if path.startswith("/api/conversations/"):
                cid = path.split("/")[3]
                c = get_conversation(cid)
                if not c:
                    return self.send_json({"error": "会话不存在"}, 404)
                return self.send_json(c)
            if path == "/api/conversations":
                return self.send_json({"conversations": list_conversations()})
            if path == "/api/books":
                return self.send_json({"books": books.list_books()})
            if path.startswith("/api/books/"):
                return self.handle_book_get(path)
            if path == "/api/storage":
                return self.send_json(storage_info())
            if path == "/api/corpus/overview":
                return self.send_json(corpus_overview())
            if path == "/api/corpus/search":
                q = (parse_qs(u.query).get("q") or [""])[0]
                return self.send_json({"hits": corpus.search(q, k=12) if q.strip() else []})
            if path == "/api/corpus/report":
                return self.send_json({"markdown": corpus.report_markdown(),
                                       "baseline": corpus.genre_baseline()})
            if path == "/api/corpus/progress":
                return self.send_json(dict(_CORPUS_RUN))
            if path == "/api/health":
                return self.send_json({"ok": True, "skills": len(SKILLS)})
            return self.send_text("Not Found", 404)
        except BrokenPipeError:
            pass
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def do_POST(self):
        path = unquote(urlparse(self.path).path)
        try:
            if path == "/api/chat":
                return self.handle_chat()
            if path == "/api/config":
                body = self.read_json()
                cfg = load_config()
                for k, v in body.items():
                    if k in ("providers", "activeProviderId", "params", "prefs", "appearance"):
                        cfg[k] = v
                save_config(cfg)
                return self.send_json({"ok": True, "config": cfg})
            if path == "/api/test":
                return self.handle_test()
            if path == "/api/corpus/import":
                body = self.read_json()
                return self.send_json(corpus_import(body.get("name"), body.get("text") or ""))
            if path == "/api/corpus/plan":
                body = self.read_json()
                return self.send_json(corpus_plan(body.get("plan") or "sample"))
            if path == "/api/corpus/estimate":
                return self.send_json(corpus.estimate())
            if path == "/api/corpus/style":
                return self.send_json(corpus_style_all())
            if path == "/api/corpus/run":
                return self.send_json(corpus_start(self.read_json()))
            if path == "/api/corpus/stop":
                _CORPUS_RUN["stop"] = True
                return self.send_json({"ok": True})
            if path == "/api/conversations":
                body = self.read_json()
                c = new_conversation(body.get("skillId", "novel-engine"), body.get("title"))
                return self.send_json(c)
            if path == "/api/backgrounds":
                return self.handle_upload()
            if path == "/api/files/extract":
                return self.handle_extract()
            if path == "/api/skills/import":
                return self.handle_skill_import()
            if path.startswith("/api/conversations/") and path.endswith("/compress"):
                return self.handle_compress(path)
            if path == "/api/export":
                return self.handle_export()
            if path == "/api/books":
                body = self.read_json()
                if body.get("data"):
                    data = body["data"]
                    if data.strip().startswith("data:") and "," in data:
                        data = data.split(",", 1)[1]
                    try:
                        raw = base64.b64decode(data)
                    except Exception:
                        return self.send_json({"error": "文件解码失败"}, 400)
                    name = body.get("filename") or "book.txt"
                    try:
                        text = extract_text(name, raw)
                        res = books.import_book(
                            body.get("title") or name.rsplit(".", 1)[0],
                            text, body.get("genre") or "", name)
                    except ValueError as e:
                        return self.send_json({"error": str(e)}, 400)
                    return self.send_json({"ok": True, "book": res["book"],
                                           "chapters": res["chapters"]})
                b = books.create_book(body.get("title") or "未命名书稿", body.get("genre") or "")
                return self.send_json(b)
            if path.startswith("/api/books/"):
                return self.handle_book_post(path)
            if path.startswith("/api/storage/"):
                return self.handle_storage(path)
            return self.send_text("Not Found", 404)
        except BrokenPipeError:
            pass
        except Exception as e:
            try:
                self.send_json({"error": str(e)}, 500)
            except Exception:
                pass

    def do_PATCH(self):
        path = unquote(urlparse(self.path).path)
        try:
            if path.startswith("/api/conversations/"):
                cid = path.split("/")[3]
                c = get_conversation(cid)
                if not c:
                    return self.send_json({"error": "会话不存在"}, 404)
                body = self.read_json()
                for k in ("title", "skillId", "project", "messages", "materials",
                          "summary", "summaryCount", "workflowId", "workflowStep"):
                    if k in body:
                        c[k] = body[k]
                save_conversation(c)
                return self.send_json({"ok": True, "conversation": c})
            if path.startswith("/api/books/"):
                return self.handle_book_patch(path)
            return self.send_text("Not Found", 404)
        except BrokenPipeError:
            pass
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    def do_PUT(self):
        path = unquote(urlparse(self.path).path)
        try:
            if path.startswith("/api/books/"):
                return self.handle_book_put(path)
            return self.send_text("Not Found", 404)
        except BrokenPipeError:
            pass
        except Exception as e:
            try:
                self.send_json({"error": str(e)}, 500)
            except Exception:
                pass

    def do_DELETE(self):
        path = unquote(urlparse(self.path).path)
        try:
            if path.startswith("/api/conversations/"):
                cid = path.split("/")[3]
                p = conv_path(cid)
                if os.path.exists(p):
                    os.remove(p)
                return self.send_json({"ok": True})
            if path.startswith("/api/skills/"):
                sid = os.path.basename(path.split("/")[3])
                fp = os.path.join(USER_SKILLS, sid + ".md")
                if os.path.exists(fp):
                    os.remove(fp)
                    reload_skills()
                    return self.send_json({"ok": True, "skills": SKILLS})
                return self.send_json({"error": "只能删除自己导入的技能"}, 403)
            if path.startswith("/api/backgrounds/"):
                fn = os.path.basename(path.split("/")[3])
                p = os.path.join(BGS, fn)
                if os.path.exists(p):
                    os.remove(p)
                return self.send_json({"ok": True})
            if path.startswith("/api/books/"):
                return self.handle_book_delete(path)
            return self.send_text("Not Found", 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 500)

    # -- 业务
    def handle_upload(self):
        body = self.read_json()
        data_url = body.get("dataUrl") or ""
        m = re.match(r"data:image/(png|jpe?g|webp|gif);base64,(.+)", data_url, re.S)
        if not m:
            return self.send_json({"error": "只支持 PNG / JPG / WEBP / GIF 图片"}, 400)
        ext = "jpg" if m.group(1).startswith("jpeg") else m.group(1)
        try:
            raw = base64.b64decode(m.group(2))
        except Exception:
            return self.send_json({"error": "图片解析失败"}, 400)
        if len(raw) > 16 * 1024 * 1024:
            return self.send_json({"error": "图片请小于 16MB"}, 400)
        fn = "bg_%d_%s.%s" % (int(time.time() * 1000), uuid.uuid4().hex[:4], ext)
        with open(os.path.join(BGS, fn), "wb") as f:
            f.write(raw)
        return self.send_json({"ok": True, "background": {
            "id": fn, "url": "/backgrounds/" + fn,
            "name": (body.get("name") or "自定义背景"),
            "size": len(raw), "createdAt": time.time()}})

    def handle_extract(self):
        body = self.read_json()
        data = body.get("data") or ""
        if data.strip().startswith("data:") and "," in data:
            data = data.split(",", 1)[1]
        try:
            raw = base64.b64decode(data)
        except Exception:
            return self.send_json({"error": "文件解码失败"}, 400)
        if len(raw) > 40 * 1024 * 1024:
            return self.send_json({"error": "文件请小于 40MB"}, 400)
        name = body.get("filename") or "material.txt"
        try:
            text = extract_text(name, raw)
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)
        except Exception as e:
            return self.send_json({"error": "解析失败：" + str(e)[:120]}, 400)
        text = (text or "").strip()
        if len(text) < 20:
            return self.send_json({"error": "没识别出文字内容"}, 400)
        cut = len(text) > 200000
        return self.send_json({"ok": True, "name": name, "chars": len(text),
                               "truncated": cut, "text": text[:200000]})

    def handle_skill_import(self):
        body = self.read_json()
        data = body.get("data") or ""
        if "," in data and data.strip().startswith("data:"):
            data = data.split(",", 1)[1]
        try:
            raw = base64.b64decode(data)
        except Exception:
            return self.send_json({"error": "文件解码失败"}, 400)
        if len(raw) > 20 * 1024 * 1024:
            return self.send_json({"error": "文件请小于 20MB"}, 400)
        try:
            imported, skipped = import_skills(body.get("filename") or "skill.md", raw)
        except ValueError as e:
            return self.send_json({"error": str(e)}, 400)
        if imported:
            reload_skills()
        return self.send_json({"ok": True, "imported": imported,
                               "skipped": skipped, "skills": SKILLS})

    def handle_compress(self, path):
        cid = path.split("/")[3]
        conv = get_conversation(cid)
        if not conv:
            return self.send_json({"error": "会话不存在"}, 404)
        cfg = load_config()
        provider = find_provider(cfg)
        params = cfg.get("params") or {}
        try:
            res = compress_conversation(conv, provider, params)
        except ProviderError as e:
            return self.send_json({"error": "压缩失败：" + str(e)}, 502)
        except Exception as e:
            return self.send_json({"error": "压缩失败：" + str(e)}, 500)
        if not res:
            return self.send_json({"ok": True, "skipped": True,
                                   "message": "消息太少，暂时不需要压缩"})
        return self.send_json({"ok": True, "skipped": False, "result": res})

    def handle_test(self):
        body = self.read_json()
        cfg = load_config()
        p = find_provider(cfg, body.get("providerId"))
        p = dict(p)
        if body.get("baseUrl"):
            p["baseUrl"] = body["baseUrl"]
        if body.get("apiKey"):
            p["apiKey"] = body["apiKey"]
        if body.get("model"):
            p["model"] = body["model"]
        if not p.get("model"):
            return self.send_json({"ok": False, "message": "请先填写模型名称"})
        t0 = time.time()
        got = {"n": 0}

        def emit(_):
            got["n"] += 1
            if got["n"] > 3:
                raise ProviderError("__stop__")

        try:
            run_model(p, [{"role": "user", "content": "回复：好"}],
                      {"temperature": 0.2, "maxTokens": 16}, emit)
            ms = int((time.time() - t0) * 1000)
            return self.send_json({"ok": True, "message": "连接成功 · %d ms" % ms, "latency": ms})
        except ProviderError as e:
            if str(e) == "__stop__":
                ms = int((time.time() - t0) * 1000)
                return self.send_json({"ok": True, "message": "连接成功 · %d ms" % ms, "latency": ms})
            return self.send_json({"ok": False, "message": str(e)})
        except Exception as e:
            return self.send_json({"ok": False, "message": str(e)})

    def handle_export(self):
        body = self.read_json()
        c = get_conversation(body.get("id", ""))
        if not c:
            return self.send_json({"error": "会话不存在"}, 404)
        lines = ["# " + (c.get("title") or "未命名创作"), ""]
        proj = c.get("project") or {}
        labels = {"title": "作品名", "genre": "类型 / 题材", "audience": "目标读者",
                  "logline": "一句话故事", "characters": "人物设定", "world": "世界观与规则",
                  "outline": "大纲", "style": "文风要求", "notes": "备注"}
        if any(proj.values()):
            lines.append("## 创作档案")
            for k, v in proj.items():
                if v:
                    lines.append("**%s**：%s" % (labels.get(k, k), v))
            lines.append("")
        for m in c.get("messages", []):
            if m["role"] == "user":
                lines.append("---\n\n**我：**\n\n" + m["content"] + "\n")
            else:
                lines.append("**砚：**\n\n" + m["content"] + "\n")
        text = "\n".join(lines)
        return self.send_json({"ok": True, "filename": (c.get("title") or "创作") + ".md", "content": text})

    # -- 书稿
    @staticmethod
    def _parts(path):
        return [x for x in path.split("/") if x]

    def handle_book_get(self, path):
        p = self._parts(path)
        if len(p) < 3:
            return self.send_text("Not Found", 404)
        bid = p[2]
        if len(p) == 3:
            ov = books.book_overview(bid)
            if not ov:
                return self.send_json({"error": "书稿不存在"}, 404)
            return self.send_json(ov)
        act = p[3]
        if act == "chapters" and len(p) >= 5:
            c = books.read_chapter(bid, p[4])
            if not c:
                return self.send_json({"error": "章节不存在"}, 404)
            return self.send_json(c)
        if act == "snapshots" and len(p) >= 5:
            if len(p) == 5:
                return self.send_json({"snapshots": books.list_snapshots(bid, p[4])})
            return self.send_json({"text": books.read_snapshot(bid, p[4], p[5])})
        if act == "bible":
            return self.send_json(books.load_bible(bid))
        if act == "outline":
            return self.send_json(books.load_outline(bid))
        return self.send_text("Not Found", 404)

    def handle_book_post(self, path):
        p = self._parts(path)
        bid = p[2] if len(p) > 2 else ""
        act = p[3] if len(p) > 3 else ""
        if not books.get_book(bid):
            return self.send_json({"error": "书稿不存在"}, 404)
        body = self.read_json()

        if act == "chapters":
            return self.send_json(books.create_chapter(
                bid, body.get("volumeId"), body.get("title"),
                body.get("after"), body.get("text") or ""))

        if act == "import":
            data = body.get("data") or ""
            if data.strip().startswith("data:") and "," in data:
                data = data.split(",", 1)[1]
            try:
                raw = base64.b64decode(data)
            except Exception:
                return self.send_json({"error": "文件解码失败"}, 400)
            name = body.get("filename") or "book.txt"
            try:
                text = extract_text(name, raw)
            except ValueError as e:
                return self.send_json({"error": str(e)}, 400)
            title = body.get("title") or name.rsplit(".", 1)[0]
            try:
                res = books.import_book(title, text, body.get("genre") or "", name, bid)
            except ValueError as e:
                return self.send_json({"error": str(e)}, 400)
            return self.send_json({"ok": True, "book": res["book"], "chapters": res["chapters"]})

        if act == "search":
            q = body.get("query") or ""
            hits = books.search(bid, q, int(body.get("k") or 8))
            return self.send_json({"ok": True, "query": q, "hits": hits})

        if act == "locate":
            return self.send_json(books.locate(bid, body.get("name")))

        if act == "restore":
            return self.send_json(books.restore_snapshot(bid, body.get("chapterId"), body.get("ts")))

        if act == "export":
            fmt = body.get("format") or "md"
            fn, data = books.export_book(bid, fmt, bool(body.get("split")))
            return self.send_json({"ok": True, "filename": fn,
                                   "data": base64.b64encode(data).decode()})

        if act == "names":
            return self.send_json({"names": books.scan_names(bid, int(body.get("limit") or 40))})

        if act == "rhythm":
            return self.send_json({"ok": True, "chapters": books.check_rhythm(bid)})

        if act == "terms":
            return self.send_json({"ok": True, "result": books.check_terms(bid)})

        if act == "foreshadow":
            return self.send_json({"ok": True, "items": books.check_foreshadow(bid)})

        if act == "index":
            idx = books.build_index(bid, force=True)
            return self.send_json({"ok": True, "chunks": len(idx.get("chunks") or [])})

        if act == "summarize":
            return self.handle_book_summarize(bid, body)

        if act == "check":
            return self.handle_book_check(bid, body)

        if act == "relations":
            return self.handle_book_relations(bid, body)

        if act == "branch":
            return self.handle_book_branch(bid, body)

        if act == "write":
            return self.handle_book_write(bid, body)

        return self.send_text("Not Found", 404)

    def handle_book_patch(self, path):
        p = self._parts(path)
        bid = p[2]
        b = books.get_book(bid)
        if not b:
            return self.send_json({"error": "书稿不存在"}, 404)
        body = self.read_json()
        for k in ("title", "genre", "author", "audience", "logline", "style", "notes"):
            if k in body:
                b[k] = body[k]
        if isinstance(body.get("volumes"), list):
            old = {}
            for v in b.get("volumes", []):
                for ch in v.get("chapters", []):
                    old[ch["id"]] = ch
            vols = []
            for vi, v in enumerate(body["volumes"]):
                chs = []
                for ch in (v.get("chapters") or []):
                    cid = ch.get("id")
                    if not cid or cid not in old:
                        continue
                    base = dict(old[cid])
                    if ch.get("title") is not None:
                        base["title"] = ch["title"]
                    chs.append(base)
                vols.append({"id": v.get("id") or ("v%d" % (vi + 1)),
                             "title": v.get("title") or ("第%d卷" % (vi + 1)),
                             "chapters": chs})
            if vols:
                b["volumes"] = vols
        books.save_book(b)
        return self.send_json({"ok": True, "book": b})

    def handle_book_put(self, path):
        p = self._parts(path)
        bid = p[2]
        if not books.get_book(bid):
            return self.send_json({"error": "书稿不存在"}, 404)
        body = self.read_json()
        if len(p) >= 5 and p[3] == "chapters":
            return self.send_json(books.write_chapter(
                bid, p[4], body.get("text") or "", body.get("title")))
        if len(p) >= 4 and p[3] == "bible":
            return self.send_json({"ok": True, "bible": books.save_bible(bid, body)})
        if len(p) >= 4 and p[3] == "outline":
            return self.send_json(books.save_outline(
                bid, body.get("scope") or "chapter", body.get("key") or "", body.get("text") or ""))
        return self.send_text("Not Found", 404)

    def handle_book_delete(self, path):
        p = self._parts(path)
        bid = p[2]
        if len(p) >= 5 and p[3] == "chapters":
            return self.send_json(books.delete_chapter(bid, p[4]))
        books.delete_book(bid)
        return self.send_json({"ok": True})

    # -- 书稿：模型侧能力
    def handle_book_summarize(self, bid, body):
        cfg = load_config()
        provider = find_provider(cfg)
        params = cfg.get("params") or {}
        scope = body.get("scope") or "chapter"
        ids = body.get("ids") or ([body.get("chapterId")] if body.get("chapterId") else [])
        b = books.get_book(bid)
        if not b:
            return self.send_json({"error": "书稿不存在"}, 404)
        out = []

        if scope == "chapter":
            for cid in ids[:4]:
                ch = books.read_chapter(bid, cid)
                if not ch or not ch["text"].strip():
                    continue
                user = "本章标题：%s\n\n正文：\n%s" % (ch["title"], ch["text"][:9000])
                try:
                    txt = ask_model(provider, params, SUMMARY_SYS, user, 900)
                except ProviderError as e:
                    return self.send_json({"error": str(e)}, 502)
                data = _json_of(txt) or {"summary": txt.strip()[:300]}
                _save_chapter_meta(bid, cid, data)
                out.append({"chapterId": cid, "title": ch["title"], "data": data})
            return self.send_json({"ok": True, "results": out})

        if scope == "volume":
            vid = body.get("volumeId") or (b["volumes"][0]["id"] if b.get("volumes") else "")
            vol = next((v for v in b.get("volumes", []) if v["id"] == vid), None)
            if not vol:
                return self.send_json({"error": "分卷不存在"}, 404)
            blocks = []
            for ch in vol["chapters"]:
                c = books.read_chapter(bid, ch["id"])
                if c and c.get("summary"):
                    blocks.append("【%s】%s" % (c["title"], c["summary"]))
            if not blocks:
                return self.send_json({"error": "这一卷还没有章节摘要，请先生成单章摘要"}, 400)
            user = "卷名：%s\n\n各章摘要：\n%s" % (vol.get("title"), "\n".join(blocks))
            try:
                txt = ask_model(provider, params, VOLUME_SUM_SYS, user, 1200)
            except ProviderError as e:
                return self.send_json({"error": str(e)}, 502)
            books.save_outline(bid, "volume", vid, "# " + (vol.get("title") or "") + " · 卷摘要\n\n" + txt)
            return self.send_json({"ok": True, "text": txt})

        # 全书
        blocks = []
        for v in b.get("volumes", []):
            sums = []
            for ch in v["chapters"]:
                c = books.read_chapter(bid, ch["id"])
                if c and c.get("summary"):
                    sums.append(c["summary"])
            if sums:
                blocks.append("【%s】%s" % (v.get("title"), " ".join(sums)[:2000]))
        if not blocks:
            return self.send_json({"error": "还没有章节摘要，请先生成"}, 400)
        try:
            txt = ask_model(provider, params, BOOK_SUM_SYS,
                            "书名：%s\n\n各卷梗概：\n%s" % (b.get("title"), "\n\n".join(blocks)), 1600)
        except ProviderError as e:
            return self.send_json({"error": str(e)}, 502)
        books.save_outline(bid, "book", "", "# 全书梗概\n\n" + txt)
        return self.send_json({"ok": True, "text": txt})

    def handle_book_check(self, bid, body):
        kind = body.get("kind") or "ooc"
        if kind == "terms":
            return self.send_json({"ok": True, "result": books.check_terms(bid)})
        if kind == "rhythm":
            return self.send_json({"ok": True, "chapters": books.check_rhythm(bid)})
        if kind == "foreshadow":
            return self.send_json({"ok": True, "items": books.check_foreshadow(bid)})
        if kind == "names":
            return self.send_json({"ok": True, "names": books.scan_names(bid, 60)})
        if kind != "ooc":
            return self.send_json({"error": "未知的检查类型"}, 400)

        cid = body.get("chapterId")
        if not cid:
            return self.send_json({"error": "请指定要检查的章节"}, 400)
        ch = books.read_chapter(bid, cid)
        if not ch or not ch["text"].strip():
            return self.send_json({"error": "这一章还没有正文"}, 400)
        mat = books.check_ooc_candidates(bid, cid)
        if not mat["characters"]:
            return self.send_json({"ok": True, "issues": [],
                                   "note": "本章没有出现设定库中的人物，无法比对"})
        cards = "\n\n".join("### " + c["name"] + "\n" + books._char_card(c) for c in mat["characters"])
        user = ("# 人物档案\n\n" + cards +
                "\n\n# 本章正文（%s）\n\n" % ch["title"] + ch["text"][:9000])
        cfg = load_config()
        try:
            txt = ask_model(find_provider(cfg), cfg.get("params") or {}, OOC_SYS, user, 1400)
        except ProviderError as e:
            return self.send_json({"error": str(e)}, 502)
        data = _json_of(txt) or {"issues": []}
        return self.send_json({"ok": True, "issues": data.get("issues") or [],
                               "checked": len(mat["characters"])})

    def handle_book_relations(self, bid, body):
        b = books.get_book(bid)
        bible = books.load_bible(bid)
        chars = bible.get("characters", [])
        if not chars:
            return self.send_json({"error": "设定库里还没有人物，先加几个人物卡"}, 400)
        cfg = load_config()
        cards = []
        for c in chars[:40]:
            cards.append("### " + (c.get("name") or "") + "\n" + books._char_card(c))
        sums = []
        for ch in books.flat_chapters(b):
            c = books.read_chapter(bid, ch["id"])
            if c and c.get("summary"):
                sums.append("第%d章：%s" % (ch["no"], c["summary"]))
        user = "# 人物档案\n\n" + "\n\n".join(cards)
        if sums:
            user += "\n\n# 各章摘要\n\n" + "\n".join(sums)[:6000]
        try:
            txt = ask_model(find_provider(cfg), cfg.get("params") or {}, REL_SYS, user, 2200)
        except ProviderError as e:
            return self.send_json({"error": str(e)}, 502)
        data = _json_of(txt) or {"nodes": [], "edges": []}
        _write_json_soft(os.path.join(books.bdir(bid), "relations.json"), data)
        return self.send_json({"ok": True, "graph": data})

    def handle_book_branch(self, bid, body):
        cid = body.get("chapterId")
        ch = books.read_chapter(bid, cid) if cid else None
        ctx = books.context_for(bid, cid, body.get("situation") or "", 5000) if cid else ""
        situ = body.get("situation") or "当前章节的结尾"
        cfg = load_config()
        user = "# 当前节点\n%s\n\n# 已知上下文\n%s\n\n请给出 3 条不同的剧情走向。" % (situ, ctx)
        try:
            txt = ask_model(find_provider(cfg), cfg.get("params") or {}, BRANCH_SYS, user, 2200)
        except ProviderError as e:
            return self.send_json({"error": str(e)}, 502)
        data = _json_of(txt) or {"branches": []}
        return self.send_json({"ok": True, "branches": data.get("branches") or []})

    def handle_book_write(self, bid, body):
        """章节续写 / 局部改写，流式返回。不自动落盘，由用户确认后插入。"""
        cfg = load_config()
        provider = find_provider(cfg, body.get("providerId"))
        params = dict(cfg.get("params") or {})
        if body.get("params"):
            params.update(body["params"])
        cid = body.get("chapterId") or ""
        mode = body.get("mode") or "continue"
        ch = books.read_chapter(bid, cid) if cid else None
        if not ch:
            return self.send_json({"error": "章节不存在"}, 404)
        text = (body.get("text") or "").strip()
        persona = (body.get("persona") or "").strip()
        extra = (body.get("instruction") or "").strip()

        sys_parts = [BASE_WRITER]
        ctx = books.context_for(bid, cid, extra or text[:200], 6000)
        if ctx:
            sys_parts.append("# 上下文（本书既有事实，不得冲突）\n\n" + ctx)
        rule = WRITE_MODES.get(mode, WRITE_MODES["continue"]).format(persona=persona or "该角色")
        sys_parts.append("# 本次任务\n\n" + rule)
        if extra:
            sys_parts.append("# 作者附加要求\n\n" + extra)
        if body.get("style"):
            sys_parts.append("# 文风\n\n" + body["style"])

        if mode == "continue":
            tail = text or ch["text"][-2500:]
            user = ("以下是本章已写到的位置，请接着往下写。\n\n" + tail +
                    "\n\n（从这里继续）")
        else:
            if not text:
                text = ch["text"]
            user = "待处理文本：\n\n" + text[:12000]

        messages = [{"role": "system", "content": "\n\n".join(sys_parts)},
                    {"role": "user", "content": user}]

        acc = []
        closed = {"v": False}

        def sse(event, data):
            if closed["v"]:
                return
            try:
                self.wfile.write(("event: %s\ndata: %s\n\n" % (
                    event, json.dumps(data, ensure_ascii=False))).encode("utf-8"))
                self.wfile.flush()
            except Exception:
                closed["v"] = True

        def emit(piece):
            if closed["v"]:
                raise ProviderError("__abort__")
            acc.append(piece)
            sse("delta", {"text": piece})

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self.end_headers()
        sse("meta", {"mode": mode, "chapterId": cid, "title": ch["title"],
                     "model": provider.get("model")})
        t0 = time.time()
        try:
            text_out, finish = run_model(provider, messages, params, emit)
        except ProviderError as e:
            sse("error", {"message": str(e)})
            return
        except Exception as e:
            sse("error", {"message": "生成中断：%s" % e})
            return
        sse("done", {"chars": len(text_out), "ms": int((time.time() - t0) * 1000),
                     "finish": finish or "interrupted",
                     "truncated": str(finish or "").lower() in ("length", "max_tokens"),
                     "incomplete": not finish})
        closed["v"] = True
        try:
            self.close_connection = True
        except Exception:
            pass

    def handle_storage(self, path):
        parts = self._parts(path)
        act = parts[2] if len(parts) > 2 else ""
        body = self.read_json()
        if act == "reveal":
            target = body.get("path") or DATA
            try:
                if not os.path.isdir(target):
                    raise ValueError("目录不存在")
                os.startfile(target)
            except Exception as e:
                return self.send_json({"error": "打开失败：%s" % e}, 500)
            return self.send_json({"ok": True})
        if act == "move":
            try:
                new = move_data(body.get("path"))
            except ValueError as e:
                return self.send_json({"error": str(e)}, 400)
            except Exception as e:
                return self.send_json({"error": "迁移失败：%s" % e}, 500)
            return self.send_json({"ok": True, "dataDir": new, "restart": True})
        if act == "reset":
            try:
                d = reset_data_dir()
            except ValueError as e:
                return self.send_json({"error": str(e)}, 400)
            return self.send_json({"ok": True, "dataDir": d, "restart": True})
        return self.send_text("Not Found", 404)

    def handle_chat(self):
        body = self.read_json()
        cfg = load_config()
        cid = body.get("conversationId")
        conv = get_conversation(cid) if cid else None
        if not conv:
            conv = new_conversation(body.get("skillId", "novel-engine"))
        if body.get("skillId"):
            conv["skillId"] = body["skillId"]
        if body.get("project") is not None:
            conv["project"] = body["project"]

        content = (body.get("content") or "").strip()
        regen = bool(body.get("regenerate"))
        cont = bool(body.get("continue"))

        if cont:
            if not conv["messages"] or conv["messages"][-1]["role"] != "assistant":
                return self.send_json({"error": "没有可续写的内容"}, 400)
        elif regen:
            while conv["messages"] and conv["messages"][-1]["role"] == "assistant":
                conv["messages"].pop()
            if not conv["messages"]:
                return self.send_json({"error": "没有可重新生成的内容"}, 400)
        else:
            if not content:
                return self.send_json({"error": "内容为空"}, 400)
            conv["messages"].append({"role": "user", "content": content, "ts": time.time()})
            if conv.get("title") in (None, "", "未命名创作"):
                conv["title"] = re.sub(r"\s+", " ", content)[:22]

        provider = find_provider(cfg, body.get("providerId"))
        params = dict(cfg.get("params") or {})
        if body.get("params"):
            params.update(body["params"])
        skill = SKILL_MAP.get(conv.get("skillId")) or SKILLS[0]

        # 上下文预算：超出就把早期消息压成「前情提要」
        budget = int((cfg.get("params") or {}).get("contextBudget") or 16000)
        sc = int(conv.get("summaryCount") or 0)
        if conv_chars(conv["messages"][sc:]) > budget:
            try:
                compress_conversation(conv, provider, params)
                sc = int(conv.get("summaryCount") or 0)
            except Exception as e:
                print("[compact] 自动压缩失败:", e)

        system = build_system(skill, conv, cfg.get("prefs"))
        if conv.get("summary"):
            system += ("\n\n# 前情提要（更早的对话已压缩）\n\n" + conv["summary"] +
                       "\n\n写作时保持与提要保持一致，不要与其中已确定的事实冲突。")

        history = conv["messages"][sc:][-24:]
        messages = [{"role": "system", "content": system}]
        for m in history:
            if m["role"] in ("user", "assistant") and m.get("content"):
                messages.append({"role": m["role"], "content": m["content"]})
        if cont:
            messages.append({"role": "user", "content":
                             "请紧接着上面的内容继续写，从中断处直接接续。"
                             "不要重复已写内容，不要重新开头，不要加任何说明、总结或过渡语。"})

        # SSE 开始
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "close")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()

        closed = {"v": False}
        acc = []

        def sse(event, data):
            if closed["v"]:
                return
            try:
                self.wfile.write(("event: %s\ndata: %s\n\n" % (event, json.dumps(data, ensure_ascii=False))).encode("utf-8"))
                self.wfile.flush()
            except Exception:
                closed["v"] = True

        def emit(piece):
            if closed["v"]:
                raise ProviderError("__abort__")
            acc.append(piece)
            sse("delta", {"text": piece})

        sse("meta", {"conversationId": conv["id"], "title": conv.get("title"),
                     "skill": skill["name"] if skill else "",
                     "model": provider.get("model"), "provider": provider.get("name")})

        t0 = time.time()
        try:
            text, finish = run_model(provider, messages, params, emit)
        except ProviderError as e:
            if str(e) == "__abort__":
                # 客户端主动停止：把已生成的部分保留下来
                if acc:
                    save_partial(conv, "".join(acc), cont, "stopped")
                return
            if acc:
                # 中途断开也要保住半截，用户还能「继续写」
                save_partial(conv, "".join(acc), cont, "interrupted")
            sse("error", {"message": str(e)})
            return
        except Exception as e:
            if acc:
                save_partial(conv, "".join(acc), cont, "interrupted")
            sse("error", {"message": "生成中断：%s" % e})
            return

        if not text.strip():
            sse("error", {"message": "模型返回为空。可能是模型名不正确，或该模型不支持当前接口。"})
            return

        truncated = str(finish or "").lower() in ("length", "max_tokens", "max_output_tokens")
        # 没有收到 finish_reason 就说明对端把连接掐了（本地服务常见），不是正常写完
        interrupted = not finish
        final_finish = finish or "interrupted"
        if cont:
            target = conv["messages"][-1]
            target["content"] = (target.get("content") or "") + text
            target.pop("incomplete", None)
            target["finish"] = final_finish
            target["truncated"] = truncated
            if interrupted:
                target["incomplete"] = True
        else:
            msg = {"role": "assistant", "content": text,
                   "skillId": conv.get("skillId"), "ts": time.time(),
                   "ms": int((time.time() - t0) * 1000),
                   "finish": final_finish, "truncated": truncated}
            if interrupted:
                msg["incomplete"] = True
            conv["messages"].append(msg)
        save_conversation(conv)
        print("[chat] %s | finish=%s | %d 字 | %.1fs" % (
            provider.get("model"), final_finish, len(text), time.time() - t0))
        sse("done", {"chars": len(text), "ms": int((time.time() - t0) * 1000),
                     "conversationId": conv["id"], "title": conv.get("title"),
                     "finish": final_finish, "truncated": truncated,
                     "incomplete": interrupted, "continue": cont,
                     "limit": int(params.get("maxTokens") or 0)})
        closed["v"] = True
        try:
            self.close_connection = True
        except Exception:
            pass


def serve_in_thread(port=0):
    """在后台线程里启动 HTTP 服务，返回 (server, 实际端口)。
    桌面版用它把界面内嵌到原生窗口，不对外暴露端口。"""
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, srv.server_address[1]


def main():
    port = int(os.environ.get("INKSTONE_PORT", "8765"))
    srv, port = serve_in_thread(port)
    print("")
    print("  砚 Inkstone · 写作智能体")
    print("  ------------------------------------")
    print("  已加载技能 %d 个" % len(SKILLS))
    print("  数据目录 %s" % DATA)
    print("  打开 http://127.0.0.1:%d" % port)
    print("  Ctrl+C 停止")
    print("")
    if "--open" in sys.argv:
        import webbrowser
        threading.Timer(0.9, lambda: webbrowser.open("http://127.0.0.1:%d" % port)).start()
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n  已停止")
        srv.shutdown()


if __name__ == "__main__":
    main()
