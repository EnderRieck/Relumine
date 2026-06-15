---
name: char-deep-dive
description: 对单个汉字做"繁简来源 + 形声流变 + 文化释义"的深度小报告，串联字库与（可选）联网检索。
tools: [get_character_detail, convert_text, search_characters, web_search]
---

# 汉字深解（char-deep-dive）

当用户想"深入了解某个汉字"时，按以下流程产出一份结构化小报告：

1. 先用 `get_character_detail` 取该简体字的完整记录（stages 演化、merges 繁体来源、
   notes、extensions 里的 cultural_computation / ocr_risk / stroke_profile 等）。
   - 如果用户给的是繁体字，先用 `convert_text`（direction=t2s）转成简体再查。
2. 若该字是"多对一合并字"（merges 含多个繁体来源），用 `convert_text` 或库内信息
   说明每个繁体来源的语义差异，指出合并带来的歧义/OCR 风险。
3. 仅当库内信息不足、且用户需要历史文化背景时，才调用 `web_search` 补充，并标注来源。
4. 输出格式（Markdown）：
   - **字头**：简体 / 繁体 / 拼音 / 部首 / 笔画(繁→简)
   - **繁简来源**：逐个来源繁体 + 语义
   - **形声流变**：按 stages 时间顺序简述
   - **文化计算要点**：OCR 风险、语义歧义、简化方式
   - **小结**：1-2 句话

只陈述有数据依据的内容；库中没有的不要杜撰，缺失项标注"暂无"。
