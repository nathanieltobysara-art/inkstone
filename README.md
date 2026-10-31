# 砚 Inkstone · 写作智能体

> 一个能装下 30 万字书稿的本地 AI 写作工作台。桌面端单文件运行，数据全部留在自己电脑上。

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Windows-10%2F11-0078D4)](https://www.microsoft.com/windows)
[![Deps](https://img.shields.io/badge/deps-pywebview%20only-success)]()
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

---

## 为什么做这个

市面上的 AI 写作工具大多把「书稿」当成一段超长 prompt 塞进模型。写到 10 万字就开始截断，人物名字前后不一致，伏笔埋了就忘。

砚的做法不一样：**「书」是一等公民**，不是聊天记录的附属品。

```
data/books/<bid>/
├── book.json          元信息 + 卷章树
├── chapters/c001.md   一章一文件
├── bible.json         世界观 / 人物 / 势力 / 道具 / 时间线 / 伏笔 / 术语
├── outline/           全书 / 卷 / 章三级提纲
├── snapshots/c001/    章节历史快照
└── index.json         BM25 索引（可重建）
```

续写时，程序自己去检索、拼装上下文——**只把该进模型的那 6000 字送进去**，而不是 45 万字全文。

实测一本 30 万字书稿：

| 操作 | 耗时 |
|---|---|
| 导入 30 万字 | 0.4 s |
| 建立 BM25 索引 | 0.06 s |
| 检索一次 | 40 ms |
| 定位到章节 | 6 ms |
| **实际注入 system prompt** | **3609 字**（而非 45 万字） |

---

## 功能

### 书稿层

- **多卷分章**：卷 → 章树形结构，一章一文件，单章可独立打开、快照、回滚
- **设定库（Bible）**：世界观、人物卡、势力、道具、时间线、伏笔、术语表
- **混合检索**：纯 Python BM25 + 中文 bigram 分词 + 精确子串加权（人名检索靠这一条）
- **上下文注入**：上一章结尾 1200 字 → 本章提纲 → 检索片段 → 相关人物卡 → 世界观 → 未回收伏笔，总预算 6000 字
- **一致性校验**：程序抽候选（正则 + 姓氏表 + 跨章覆盖度），模型只做局部比对，绝不读全文
- **伏笔追踪**：埋点标记 + 未回收提醒
- **人物关系图**：SVG 力导向布局，按章节范围过滤
- **节奏分析**：章长、对话占比、冲突密度曲线
- **三级摘要**：章 → 卷 → 全书，逐层蒸馏
- **版本快照**：任意章节随时存档，随时对比回滚

### 创作辅助

- **19 个写作技能**：长篇小说引擎、场景刻画、人物与世界观、去 AI 味、学术润色、公文、公众号、短剧、深度研究……全部是纯 Markdown，可自己改、可导入
- **6 条工作流**：新书启动（7 步）、日更（4 步）、资料研究（3 步）、润色（3 步）、短剧（4 步）、文章（4 步）——每步都带可直接发送的指令
- **11 个写作模板**：6 个章节模板（冲突章 / 打脸章 / 过渡章 / 感情线章 / 悬念章 / 高潮章）+ 5 个结构模板（黄金三章 / 三幕剧 / 起承转合 / 英雄之旅 / 爽文节奏表）
- **素材导入**：txt / md / docx / epub / pdf / html / csv，自动抽取正文

### 工程

- **11 个模型供应商开箱可用**：DeepSeek、OpenAI、Claude、Kimi、智谱 GLM、通义千问、硅基流动、OpenRouter、Ollama、LM Studio、vLLM / 任意 OpenAI 兼容接口
- **流式输出**：SSE 增量推送，中断也保留半截，可「继续写」
- **会话自动压缩**：超预算时把早期对话压成「前情提要」，不丢线索
- **工作区可迁移**：数据目录随便换，复制不删除，换完自动重启生效
- **主题系统**：纸感 / 深色多套主题，背景图、透明度、字号、圆角全可调

---

## 快速开始

### 方式一：直接下载（Windows）

从 [Releases](releases) 下载 `Inkstone.exe`，双击运行。单文件，无需安装 Python。

> 需要系统已安装 [Microsoft Edge WebView2 运行时](https://developer.microsoft.com/microsoft-edge/webview2/)（Win10 1803+ / Win11 通常自带）。

### 方式二：从源码运行

```bash
git clone https://github.com/<你的用户名>/inkstone.git
cd inkstone
pip install -r requirements.txt
python app.py
```

没装 `pywebview` 也能跑——会自动降级成浏览器模式（`python server.py` 起本地服务，手动打开提示的地址）。

### 配置模型

打开 **设置 → 模型**，选一个供应商，填 API Key，点「测试连接」。

本地模型（Ollama / LM Studio）地址填 `http://localhost:11434` 或 `http://localhost:1234/v1` 即可，Key 留空——本地回环地址会强制绕过系统代理，不会被 Clash / WARP 之类拦成 502。

想用任何其他 OpenAI 兼容服务？**新增供应商 → 自定义服务**，填 Base URL 和模型名就行。

---

## 数据与隐私

- 所有书稿、对话、设定、背景图都存在本地 `data/` 目录
- 配置文件 `data/config.json` 里的 API Key **明文存储**，不会上传到任何地方
- 唯一的对外请求就是你自己配置的那个模型接口
- 想换个盘？**设置 → 存储 → 更改位置**，会把整个工作区复制过去（只复制，不删除）

---

## 架构

```
app.py        202 行   pywebview 原生窗口 + JS Bridge（保存对话框、选目录、重启）
server.py    2042 行   HTTP 服务 + SSE 流式 + 供应商适配 + 会话压缩 + 提示词装配
books.py     1077 行   书稿数据模型 + BM25 检索 + 上下文注入 + 一致性校验
corpus.py     492 行   语料库子系统：几百本参考书 + SQLite/FTS5 检索 + 蒸馏任务队列
static/      5980 行   纯前端，零框架零构建（app.js / styles.css / templates.js / workflows.js）
skills/        19 个   Markdown 技能定义，热加载
tools/                压测、mock LLM、截图、演示数据生成
```

- 后端只用标准库 `http.server`，没有 FastAPI / Flask
- 前端没有 React / Vue / 打包工具，改完刷新就行
- 依赖只有 `pywebview` 一个
- 打包用 PyInstaller，产物约 14 MB

```bash
pyinstaller Inkstone.spec
```

---

## 已知限制

- **语料库（`corpus.py`）目前只有命令行，还没有界面**。批量蒸馏的 worker 和聚合报告仍在开发中
- 只在 Windows 上验证过。`app.py` 里 `os.startfile`、`gui="edgechromium"` 这些是 Windows 专用，macOS / Linux 需要改几处
- BM25 索引是全量重建，不是增量更新。几百万字级别会慢，但一本书的量级毫无压力
- 一致性校验是「程序抽候选 + 模型局部比对」，不是全自动真理机。它会漏，也会误报，最终还是要作者判断
- 没有多人协作、没有云端同步——这是刻意的

---

## 许可

代码以 [MIT](LICENSE) 授权。

`skills/` 目录下的技能提示词**不全是原创**，部分改编自开源项目，各自保留原许可（MIT / Apache-2.0）。具体来源、原作者与改动说明见 [THIRD-PARTY.md](THIRD-PARTY.md)。

如果你要二次分发或商用，请连同 `THIRD-PARTY.md` 一起保留——这是 MIT 和 Apache-2.0 的共同要求。
