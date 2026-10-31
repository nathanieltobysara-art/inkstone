[中文](README.md) | **English**

# Inkstone · AI Writing Studio

> A local-first AI workbench for long-form fiction. Ships as a single desktop executable; your manuscripts never leave your machine.

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Windows-10%2F11-0078D4)](https://www.microsoft.com/windows)
[![Deps](https://img.shields.io/badge/deps-pywebview%20only-success)]()
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## Why this exists

Most AI writing tools treat a manuscript as one giant prompt. Around 100,000 characters the model starts truncating, character names drift, and foreshadowing planted in chapter 3 is forgotten by chapter 40.

Inkstone treats **the book itself as a first-class entity**, not an appendage of the chat log.

```
data/books/<bid>/
├── book.json          metadata + volume/chapter tree
├── chapters/c001.md   one file per chapter
├── bible.json         world / characters / factions / items / timeline / foreshadowing / terms
├── outline/           book, volume and chapter outlines
├── snapshots/c001/    per-chapter history
└── index.json         BM25 index (rebuildable)
```

When you continue writing, the app retrieves and assembles context itself — **only the 6,000 characters that matter reach the model**, not the full 450,000.

Measured on a 300,000-character manuscript:

| Operation | Time |
|---|---|
| Import 300k characters | 0.4 s |
| Build BM25 index | 0.06 s |
| One retrieval | 40 ms |
| Locate a chapter | 6 ms |
| **Actually injected into system prompt** | **3,609 characters** (out of 450,000) |

---

## Features

### Manuscript layer

- **Volumes and chapters** — a tree structure, one file per chapter, each independently openable, snapshottable and revertible
- **Story bible** — world, character cards, factions, items, timeline, foreshadowing, glossary
- **Hybrid retrieval** — pure-Python BM25 with Chinese bigram tokenisation plus exact-substring boosting (this is what makes character-name lookup work)
- **Context injection** — previous chapter's closing 1,200 characters → this chapter's outline → retrieved passages → relevant character cards → world rules → unresolved foreshadowing, capped at 6,000 characters
- **Consistency checks** — the program extracts candidates (regex + surname list + cross-chapter coverage); the model only compares locally, never reads the whole book
- **Foreshadowing tracker** — mark a plant, get reminded when it is never resolved
- **Character relationship graph** — SVG force-directed layout, filterable by chapter range
- **Pacing analysis** — chapter length, dialogue ratio, conflict density curves
- **Three-tier summaries** — chapter → volume → book, distilled layer by layer
- **Version snapshots** — archive any chapter at any time, diff and revert

### Writing aids

- **19 writing skills** — long-form novel engine, scene craft, character and world building, de-AI-ifying prose, academic polishing, official documents, WeChat articles, short drama, deep research… all plain Markdown, editable and importable
- **6 workflows** — new book (7 steps), daily writing (4), research (3), polishing (3), short drama (4), articles (4); each step ships with a ready-to-send instruction
- **11 writing templates** — 6 chapter templates (conflict / face-slap / transition / romance / suspense / climax) plus 5 structural templates (golden first three chapters, three-act, four-part, hero's journey, web-novel pacing table)
- **Source material import** — txt / md / docx / epub / pdf / html / csv, with automatic body extraction

### Engineering

- **11 model providers out of the box** — DeepSeek, OpenAI, Claude, Kimi, Zhipu GLM, Qwen, SiliconFlow, OpenRouter, Ollama, LM Studio, vLLM, or any OpenAI-compatible endpoint
- **Streaming output** — SSE deltas; an interrupted generation keeps its partial text and can be resumed
- **Automatic conversation compaction** — when a session exceeds its budget, earlier turns are folded into a recap instead of being dropped
- **Portable workspace** — move the data directory anywhere; it copies rather than moves, then restarts to apply
- **Theming** — paper and dark themes, with adjustable background image, opacity, font size and corner radius

---

## Quick start

### Option 1: download (Windows)

Grab `Inkstone.exe` from [Releases](../../releases) and double-click it. Single file, no Python installation required.

> Requires the [Microsoft Edge WebView2 runtime](https://developer.microsoft.com/microsoft-edge/webview2/) (usually preinstalled on Windows 11 and Windows 10 1803+).

### Option 2: run from source

```bash
git clone https://github.com/nathanieltobysara-art/inkstone.git
cd inkstone
pip install -r requirements.txt
python app.py
```

It also runs without `pywebview` — the app falls back to browser mode (`python server.py` starts a local server and prints the address).

### Configure a model

Open **Settings → Models**, pick a provider, paste your API key, click **Test connection**.

For local models (Ollama / LM Studio) use `http://localhost:11434` or `http://localhost:1234/v1` and leave the key empty — loopback addresses bypass the system proxy, so Clash / WARP and friends cannot turn them into a 502.

Using something else? **Add provider → Custom service**, then fill in the base URL and model name.

---

## Data and privacy

- Manuscripts, conversations, settings and background images all live in a local `data/` directory
- API keys in `data/config.json` are stored **in plain text** and never uploaded anywhere
- The only outbound request is the model endpoint you configured yourself
- Moving to another drive: **Settings → Storage → Change location** copies the whole workspace (copy, never move)

---

## Architecture

```
app.py        202 lines   pywebview window + JS bridge (save dialog, folder picker, restart)
server.py   2,042 lines   HTTP server + SSE streaming + provider adapters + compaction + prompt assembly
books.py    1,077 lines   manuscript model + BM25 retrieval + context injection + consistency checks
corpus.py     492 lines   corpus subsystem: hundreds of reference books + SQLite/FTS5 + distillation queue
static/     5,980 lines   plain frontend, no framework, no build step (app.js / styles.css / templates.js / workflows.js)
skills/          19 files Markdown skill definitions, hot-reloaded
tools/                    benchmarks, mock LLM, screenshots, demo data
```

- The backend uses nothing but the standard library's `http.server` — no FastAPI, no Flask
- The frontend has no React, no Vue, no bundler; edit and refresh
- The only dependency is `pywebview`
- Packaged with PyInstaller, roughly 14 MB

```bash
pyinstaller Inkstone.spec
```

---

## Known limitations

- **The corpus subsystem (`corpus.py`) is CLI-only** — there is no UI yet, and the batch distillation worker and aggregate reports are still in progress
- Only verified on Windows. `os.startfile` and `gui="edgechromium"` in `app.py` are Windows-specific; macOS and Linux need a few changes
- The BM25 index is rebuilt in full rather than incrementally. Fine for one book, slower at the multi-million-character scale
- Consistency checking is "program extracts candidates + model compares locally" — not an oracle. It misses things and it raises false positives; the author still decides
- No collaboration, no cloud sync. That is deliberate

---

## License

Code is licensed under [MIT](LICENSE).

The skill prompts under `skills/` are **not all original** — several are adapted from open-source projects and keep their original licenses (MIT / Apache-2.0). See [THIRD-PARTY.md](THIRD-PARTY.md) for sources, authors and a description of the changes.

Three files (`academic`, `interactive`, `review`) have not yet been traced to their origin and are **excluded from this repository's MIT grant**. Judge the risk yourself before commercial use.

If you redistribute or use this commercially, keep `THIRD-PARTY.md` alongside it — that is required by both MIT and Apache-2.0.
