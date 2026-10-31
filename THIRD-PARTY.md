# 第三方内容声明（Third-Party Notices）

本仓库 `skills/` 目录下的写作技能提示词，部分改编自以下开源项目。
原始作品版权归各原作者所有，本项目在原有基础上做了中文化、结构重排与场景适配。

> 说明：本项目代码以 [MIT](LICENSE) 授权；下列技能文件保留其原始许可，**不因收录于本仓库而改为 MIT**。

## 已确认来源

| 技能文件 | 原项目 | 许可 | 改动说明 |
|---|---|---|---|
| `skills/book-analysis.md` | [Wooooooooood/ai-fiction-writer](https://github.com/Wooooooooood/ai-fiction-writer) | MIT | 提炼「扫榜五维 / 六维评分 / 文风卡 / 套路清单」，增加「无实时榜单数据不得编造排名」的约束 |
| `skills/scene-craft.md` | [lemnt-ai/skills](https://github.com/lemnt-ai/skills)（novel-studio） | MIT | 合并 write_dialogue / write_combat / write_emotional_scene 为单技能的四个阶段 |
| `skills/deai.md` | [blader/humanizer](https://github.com/blader/humanizer) v3.1.0 | MIT | 采用 26 条模式 A–F 分类与事实保真框架；保留中文七类词表，英文专属规则（破折号 / 弯引号 / -ing）只迁移结构性部分 |
| `skills/short-drama.md` | [0xsline/short-drama](https://github.com/0xsline/short-drama) | MIT | 保留四层反派、五种钩子、节奏曲线、爽感矩阵，适配小说场景 |
| `skills/official-doc.md` | [gongyu0918-debug/chinese-official-writing-skill](https://github.com/gongyu0918-debug/chinese-official-writing-skill) | MIT | 保留文种速查、缘由—事项—结语结构、事实纪律、复核清单 |
| `skills/research-deep.md` | [KKKKhazix/khazix-skills](https://github.com/KKKKhazix/khazix-skills)（hv-analysis） | MIT | 只保留纵横分析方法论，移除原项目的 WeasyPrint 出 PDF 与子 Agent 并行搜索依赖 |
| `skills/academic-polish.md` | [Yila-AI/sci-ssci-skills](https://github.com/Yila-AI/sci-ssci-skills) | Apache-2.0 | 保留「Fluent is not always faithful」核心与断言强度阶梯，中文化 |
| `skills/doc-coauthor.md` | [anthropics/skills](https://github.com/anthropics/skills)（doc-coauthoring） | Apache-2.0 | 保留三阶段结构与「只给改动段落」原则，压缩为单文件技能 |
| `skills/brand-voice.md` | [anthropics/skills](https://github.com/anthropics/skills)（brand-guidelines） | Apache-2.0 | **大幅改造**：原技能是视觉规范（配色 / 字体），此处改为纯文字六要素文风卡 |
| `skills/work-comms.md` | [anthropics/skills](https://github.com/anthropics/skills)（internal-comms） | Apache-2.0 | 保留 3P 周报、向上汇报、FAQ、事故复盘四类模板 |

## 待补充来源

以下 9 个技能在开发过程中参考了开源仓库，但**未记录具体项目地址**。在补充来源前，它们的状态是「来源未核实」：

`academic.md`、`chapter-craft.md`、`character-world.md`、`interactive.md`、
`longform.md`、`novel-engine.md`、`review.md`、`seven-step.md`、`wechat-article.md`

维护者需要补齐上表后，才能视为完成许可合规。若无法确认来源，应将这些文件从仓库中移除，改由用户自行导入。

## 许可全文

- MIT 许可全文见各原项目仓库根目录 `LICENSE`
- Apache-2.0 许可全文：<https://www.apache.org/licenses/LICENSE-2.0>

使用 Apache-2.0 来源的作品时，须保留原始版权声明与许可声明，并说明修改内容（即上表「改动说明」列）。
