# ICAICE 2026 投稿合规说明与英文版对应关系

日期：2026-10-18

## 一、会议硬性要求（来源：会议官网页面）

| 项目 | 要求 | 我们当前的状态 |
|---|---|---|
| 语言 | **会议仅接受英文投稿** | 中文稿**不符合**；英文版已生成 |
| 出版 | IEEE 出版，ISBN 979-8-3195-9875-2，提交 IEEE Xplore / EI Compendex / Scopus | 符合 |
| 模板 | IEEE 会议模板（官网提供 Word / LaTeX 双通道） | 已按 IEEEtran conference 生成 `.tex`，Word 版为双栏 10pt |
| 页数 | **不得少于 4 页**（无明确上限；版面费按 4 页计，第 5 页起 400 元/页） | 英文版 8 页 |
| 查重 | 全文（含参考文献）低于 30%，需保证参考文献 DOI 可核实 | 待自行查重 |
| 审稿 | 2–3 位专家，投稿后 7 个工作日给结果 | 终轮截稿 10 月 31 日 23:59 |

**结论**：中文稿不能直接投 ICAICE，语言是第一道硬门槛；中文稿的作用是内容母本（
可投中文期刊、学位论文或项目验收材料）。面向 ICAICE 的交付物是 `main_IEEE.docx`
与 `main.tex`。

## 二、英文版文件

| 文件 | 用途 | 说明 |
|---|---|---|
| `main_IEEE.docx` | Word 通道投稿 | 双栏、10pt、8 页；页边距 0.65/0.75 in；表题在表上方（TABLE I–V） |
| `main.tex` | LaTeX 通道（Overleaf） | `\documentclass[conference]{IEEEtran}`，图片用 `\columnwidth`，表用 `p{}` 定宽 |
| `content.py` | 唯一内容源 | 改文字只改这里，两个构建脚本共用，避免两份手抄不一致 |
| `build_docx.py` / `build_tex.py` | 构建脚本 | `python build_docx.py` / `python build_tex.py` |

英文版与中文稿**同源同数**：22 条规则、450 次执行、404 次命中、覆盖 150/150、
考试与等级差距漏报 0、网格 200/200、求值 0.0122 ms、模型 26/26、引用 4.75 个事实、
端到端 105 s，全部取自 `eval/results/metrics.json` 与 `model_eval.json`。

## 三、英文版结构（8 页）

| 节 | 内容 | 图表 |
|---|---|---|
| I | Introduction（背景、个体差异、现有系统不足、三类风险、四点贡献） | — |
| II | Existing Routes and Their Limitations（固定课件、大模型、RAG、图谱与规则引擎、定位） | TABLE I |
| III | System Architecture（约束、三层、规则引擎、护栏与回退） | Fig. 1–2、TABLE II–III、式 1–2 |
| IV | Key Implementation（规则集、事实适配与个性化、契约、语料与微调） | 式 3–7 |
| V | Experiments（设置、协议、规则有效性、性能、模型质量、对比） | Fig. 3–4、TABLE IV–V、式 8 |
| VI | Applicability and Discussion（条件、场景、不适用、关系、局限） | — |
| VII | Conclusion | — |

为适配 IEEE 双栏，英文版相对中文稿做了三处压缩：省去 DSL 字段表与算子表（改为文字描述）、
省去算法伪代码（改为一段过程描述）、省去损失曲线图（数字保留在正文）。
若审稿意见要求补细节，这三处可随时加回，预计各增加 0.3–0.4 页。

## 四、提交前必办清单

1. **作者信息**：`content.py` 顶部 `AUTHORS` / `AFFIL` 目前是占位符，需填真实姓名、
   单位、城市、邮编、通信作者邮箱；英文姓名建议 "Given Family" 顺序。
2. **模板核对**：从官网 `event-icaice.org/download` 下载当前 IEEE 模板，比对字号、
   页边距、参考文献格式（IEEE 风格为 `[1] A. B. Author, "Title," ...`），
   我们的参考文献目前是中文期刊风格（`Author. Title[J]. Journal, year, vol(issue): pages.`），
   投稿前建议改成 IEEE 格式。
3. **查重**：iThenticate 全文低于 30%。参考文献部分占比高时优先删减不重要条目。
4. **DOI 可核实**：会议明确要求每条参考文献的 DOI 或链接可访问。
   我们的 25 条中，中文两条给了 DOI 与原文链接，其余为 arXiv DOI 或会议 DOI。
5. **图表清晰度**：图片为 400 dpi PNG，双栏宽 3.35 in，可直接用。
6. **页数成本**：8 页 = 3800 + 4×400 = 5400 元。若需压到 6 页（4600 元），
   可去掉 Fig. 4 与 TABLE V，并把第 VI 节压到两段。

## 五、中文稿的定位

`中文稿_变电运维个性化Agent.docx`（26 页、22 表、5 图、8 式、25 文献）保留为：
中文期刊投稿底稿、学位论文章节、项目验收与答辩材料。它与英文版共享同一份数据与结论，
不存在口径冲突；两版的差别只在篇幅与语言。
