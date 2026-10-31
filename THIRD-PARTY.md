# 第三方内容声明（Third-Party Notices）

本仓库 `skills/` 目录下的写作技能提示词，部分改编自以下开源项目。
原始作品版权归各原作者所有，本项目在原有基础上做了中文化、结构重排与场景适配。

> 说明：本项目代码以 [MIT](LICENSE) 授权；下列技能文件保留其原始许可，**不因收录于本仓库而改为 MIT**。

## 已确认来源（16 个）

| 技能文件 | 原项目 | 许可 | 改动说明 |
|---|---|---|---|
| `skills/novel-engine.md` | [leenbj/novel-creator-skill](https://github.com/leenbj/novel-creator-skill) | MIT | 提炼「真值层 / 状态回写 / 反向刹车 / 章节控制卡」为单文件技能；原项目为多文件 + Python 脚本的完整框架，此处只保留方法论 |
| `skills/chapter-craft.md` | [leenbj/novel-creator-skill](https://github.com/leenbj/novel-creator-skill) | MIT | 采用其「事件矩阵与冷却」表（冲突爽点 2 章 / 人物羁绊 1 章 / 风土人情 3 章等）与「每 5 章至少一次羁绊」规则 |
| `skills/character-world.md` | [leenbj/novel-creator-skill](https://github.com/leenbj/novel-creator-skill) | MIT | 参考其角色追踪器与知识图谱节点设计；「知情边界」「这句话只有他会说吗」为本项目补充 |
| `skills/seven-step.md` | [wordflowlab/novel-writer-skills](https://github.com/wordflowlab/novel-writer-skills) | MIT | 采用其七步方法论（创作宪法 / 故事规格 / 澄清 / 计划 / 任务 / 写作 / 验证），压缩为单技能 |
| `skills/book-analysis.md` | [Wooooooooood/ai-fiction-writer](https://github.com/Wooooooooood/ai-fiction-writer) | MIT | 提炼「扫榜五维 / 六维评分 / 文风卡 / 套路清单」，增加「无实时榜单数据不得编造排名」的约束 |
| `skills/scene-craft.md` | [lemnt-ai/skills](https://github.com/lemnt-ai/skills)（novel-studio） | MIT | 合并 write_dialogue / write_combat / write_emotional_scene 为单技能的四个阶段 |
| `skills/deai.md` | [blader/humanizer](https://github.com/blader/humanizer) v3.1.0 | MIT | 采用 26 条模式 A–F 分类与事实保真框架；保留中文七类词表，英文专属规则（破折号 / 弯引号 / -ing）只迁移结构性部分 |
| `skills/short-drama.md` | [0xsline/short-drama](https://github.com/0xsline/short-drama) | MIT | 保留四层反派、五种钩子、节奏曲线、爽感矩阵，适配小说场景 |
| `skills/official-doc.md` | [gongyu0918-debug/chinese-official-writing-skill](https://github.com/gongyu0918-debug/chinese-official-writing-skill) | MIT | 保留文种速查、缘由—事项—结语结构、事实纪律、复核清单 |
| `skills/research-deep.md` | [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills)（hv-analysis） | MIT | 只保留纵横分析方法论，移除原项目的 WeasyPrint 出 PDF 与子 Agent 并行搜索依赖 |
| `skills/wechat-article.md` | [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills)（khazix-writer） | MIT | 保留「有见识的普通人在认真聊一件打动他的事」立场、四层自检、禁忌词表；标题公式与结构字数配额为本项目补充 |
| `skills/longform.md` | [ComposioHQ/awesome-claude-skills](https://github.com/ComposioHQ/awesome-claude-skills)（content-research-writer） | Apache-2.0 | 保留澄清六问、协作大纲、3 个开头方案、逐节反馈、「这听起来像你吗」声音保护；压缩为单文件技能 |
| `skills/academic-polish.md` | [Yila-AI/sci-ssci-skills](https://github.com/Yila-AI/sci-ssci-skills) | Apache-2.0 | 保留「Fluent is not always faithful」核心与断言强度阶梯，中文化 |
| `skills/doc-coauthor.md` | [anthropics/skills](https://github.com/anthropics/skills)（doc-coauthoring） | Apache-2.0 | 保留三阶段结构与「只给改动段落」原则，压缩为单文件技能 |
| `skills/brand-voice.md` | [anthropics/skills](https://github.com/anthropics/skills)（brand-guidelines） | Apache-2.0 | **大幅改造**：原技能是视觉规范（配色 / 字体），此处改为纯文字六要素文风卡 |
| `skills/work-comms.md` | [anthropics/skills](https://github.com/anthropics/skills)（internal-comms） | Apache-2.0 | 保留 3P 周报、向上汇报、FAQ、事故复盘四类模板 |

## 待补充来源（3 个）

以下技能在开发过程中参考了开源仓库，但**未能定位到具体项目地址**，目前状态为「来源未核实」：

| 技能文件 | 特征内容（便于回溯） |
|---|---|
| `skills/academic.md` | 三阶段 Frame & outline / Plan & write / Check & revise；四遍审稿（论证与结构 / 证据与范围 / 学术语言 / 交付完整性） |
| `skills/interactive.md` | 互动推演、每回合三段（场景推进 / 选项 / 当前状态）、每 5 回合局势回顾 |
| `skills/review.md` | 四视角审稿（编辑 / 读者 / 平台 / 作者）、五要素问题格式【位置】【问题】【证据】【后果】【建议】 |

### 重要声明

**这 3 个文件不随本仓库的 MIT 许可授权。** 在来源确认之前，它们处于「许可状态未知」，
使用者如需商用或再分发，请自行判断风险，或改用上表中已确认来源的技能。

### 如果你是原作者

本项目无意侵占任何人的劳动成果。如果你认为这 3 个文件中有你创作的内容：

- **希望署名** → 开一个 [Issue](../../issues)，附上你的项目地址和许可，
  我们会在上表补全来源、保留你的版权声明，并在文件 frontmatter 中加上 `origin` 与 `license` 字段
- **不希望被收录** → 同样开 Issue 说明，我们会**从仓库和 git 历史中一并移除**，
  并重新生成历史，确保 clone 下来也拿不到

我们会尽快响应，不需要你提供额外的法律文件。

## 许可全文

- MIT 许可全文见各原项目仓库根目录 `LICENSE`
- Apache-2.0 许可全文见 [`LICENSES/Apache-2.0.txt`](LICENSES/Apache-2.0.txt)

使用 Apache-2.0 来源的作品时，须保留原始版权声明与许可声明，并说明修改内容（即上表「改动说明」列）。
