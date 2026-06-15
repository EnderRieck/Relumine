---
name: corpus-audit
description: 对一段古籍语料做"识读风险审计"——统计字库覆盖，挑出高 OCR 风险字逐字解析，产出风险报告。
tools: [analyze_corpus_coverage, get_character_detail, search_characters, convert_text]
---

# 古籍语料识读风险审计（corpus-audit）

当用户给出一段古籍原文 / OCR 输出，想知道"这段文字里哪些字容易识错、繁简上有哪些坑"时，按以下流程产出一份审计报告：

1. 调 `analyze_corpus_coverage(text)`：拿到总汉字数、命中字库的记录数、高风险命中数(highRiskHits)、
   覆盖率(coveragePct) 与 Top 命中字(topHits)。这一步同时会在"形声流变·语料覆盖率"面板展示结果。
2. 从命中字中挑出**高 OCR 风险**与**多对一合并**的字（结合 topHits 与常识），对其中最关键的
   3-8 个字逐个调 `get_character_detail`，逐字说明：
   - 繁体来源：是否多对一合并（如 发=發/髮、后=后/後），列出来源繁体；
   - OCR 易混原因：字形相近、部件相似（看 extensions 里的 ocr_risk / component_shift）；
   - 语义歧义：合并是否带来歧义（semantic_ambiguity）。
3. 如有助于说明，用 `convert_text`（t2s）演示该段繁→简结果，并指出多对一碰撞位置。
4. 产出**识读风险报告**（Markdown）：
   - **概览**：总字数 / 命中字数 / 覆盖率% / 高风险命中数
   - **高风险字清单**：表格 `字 | 繁体来源 | 风险类型 | 说明`
   - **校对建议**：识读时需重点人工复核的字
   - **小结**：1-2 句

只基于工具返回的真实数据，不杜撰；字库里没有的字标注"库外字"，不要编造其繁体来源或风险。
