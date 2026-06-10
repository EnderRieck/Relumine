# Relumine 自建汉字数据库 v1

## 位置

数据库文件：

```text
apps/api/ocrforge_web/data/relumine_char_db.v1.json
```

生成脚本：

```text
analysis/hanzi_databases/scripts/build_relumine_database.py
```

## 数据库定位

这个 v1 数据库不是简单搬运外部数据，而是以项目原有的 `evolution.json` 为核心，把外部数据库作为证据层补进去。

当前每条记录按“简体字”聚合。比如 `发` 是一条记录，下面挂 `發`、`髮` 两个繁体来源，并分别记录 OpenCC、Unihan、CC-CEDICT 和 CHISE IDS 的支持情况。

数据库建设采用分层目标：

| 阶段 | 字数 | 定位 |
| --- | ---: | --- |
| v1 精修层 | 10 | 已有人工作业说明、字形演化阶段和外部证据 |
| v1 阶段版 | 50 | 10 个精修字 + 40 个自动扩展字，可用于统计和展示数据库规模 |
| v1 目标版 | 100 | 10 个精修字 + 90 个高证据自动扩展字，作为当前课程展示主库 |

最终目标建议定为 **100 个字**。理由是：100 个字足够覆盖主要简化类型和常见多繁合一冲突，工作量又不会失控；如果做成几千个字，外部证据可以自动挂上去，但人工考据、演化说明和展示质量很难保证。

## 字段结构

顶层字段：

| 字段 | 含义 |
| --- | --- |
| `schema_version` | 数据库结构版本 |
| `generated_at` | 生成时间 |
| `source_files` | 本地数据来源 |
| `source_urls` | 外部数据库来源 |
| `summary` | 数据库规模统计 |
| `characters` | 字符记录列表 |

单字记录字段：

| 字段 | 含义 |
| --- | --- |
| `simplified` | 简体字 |
| `curation_level` | `handcrafted` 表示人工精修，`auto_external` 表示外部数据库自动扩展 |
| `canonical_traditional` | 项目当前认定的主繁体 |
| `record_type` | `one_to_one_or_single_source` 或 `multi_source_merge` |
| `simplification_types` | 自动推断的简化类型，如草书楷化、多对一合并、古字复用 |
| `project_interpretation` | 项目原有的演化阶段、合并关系和说明 |
| `external_profile` | 简体字本身在外部数据库中的信息 |
| `traditional_sources` | 每个繁体来源的证据记录 |
| `cultural_computation` | 基于外部证据计算出的语义歧义、OCR 风险、部件变化、字频优先级 |
| `coverage` | 该字是否有 Unihan、CHISE、OpenCC、CC-CEDICT 支持 |

繁体来源字段：

| 字段 | 含义 |
| --- | --- |
| `char` | 繁体/来源字 |
| `role` | 主繁体、合并来源、复用字形等 |
| `unihan` | Unihan 的读音、释义、笔画、变体 |
| `chise_ids` | CHISE IDS 的部件结构分解 |
| `opencc` | OpenCC 繁简候选和是否支持当前映射 |
| `cc_cedict` | CC-CEDICT 中的词级证据和例词 |
| `unihan_variant_support` | Unihan 变体字段如何支持该映射 |

## 当前规模

当前 v1 数据库已经扩展为 100 个字，其中 10 个来自项目已有的人工精修核心字：

```text
学、书、东、车、发、后、面、台、余、杰
```

统计摘要：

| 指标 | 数值 |
| --- | ---: |
| 最终目标 | 100 |
| 单字记录 | 100 |
| 人工精修记录 | 10 |
| 自动扩展记录 | 90 |
| 多来源合并记录 | 96 |
| 繁体来源关系 | 211 |
| 有 Unihan 支持 | 100 |
| 有 CHISE IDS 支持 | 100 |
| 有 OpenCC 映射支持 | 100 |
| 有 CC-CEDICT 词级证据 | 100 |
| 通过质量门槛 | 100 |

90 个自动扩展字来自 OpenCC 多候选映射，质量门槛是：简体字和来源字均能接入 Unihan / CHISE IDS，并且每个来源关系都有 CC-CEDICT 词级例证。前部候选例如：

```text
干、蒙、里、复、系、周、苏、胡、向、汇、钟、采、并、只、泛、毁、熏、戚、家、克……
```

## 文化计算字段

当前 100 字均已生成 `cultural_computation` 字段，并接入前端单字详情页。它不是新的外部数据库，而是基于四个外部数据库和本项目字段计算出的解释层。

| 子字段 | 含义 |
| --- | --- |
| `semantic_ambiguity` | 按繁体来源数和释义差异估计语义歧义等级 |
| `component_shift` | 基于 CHISE IDS 比较主繁体和简体的部件保留、删除、新增 |
| `ocr_risk` | 综合多繁一简、古字复用、笔画削减和部件变化，估计 OCR/转写风险 |
| `frequency_profile` | 用 CC-CEDICT 中作为简体出现的次数作为字频代理，并给出库内排名 |
| `stroke_profile` | 统计该字各繁简来源对的平均和最大笔画削减 |
| `cultural_tags` | 面向前端展示的标签，如多源合并、古字复用、大幅简化、高频用字 |

当前统计结果：

| 指标 | 数值 |
| --- | ---: |
| 语义歧义高等级字 | 12 |
| OCR 风险高等级字 | 73 |
| 高频用字 | 33 |
| 中频用字 | 52 |
| 低频用字 | 15 |

典型例子：`台` 对应 `臺 / 檯 / 颱 / 台` 四个传统来源，语义歧义等级为高，OCR 风险为高，前端会展示其来源数、风险原因、部件变化和字频排名。

## 配套输出

```text
analysis/hanzi_databases/processed/relumine_char_db_summary.csv      — 100 字摘要表
analysis/hanzi_databases/processed/cultural_computation_summary.csv  — 文化计算摘要表
analysis/hanzi_databases/processed/opencc_merge_candidates.csv       — 下轮扩充候选
analysis/hanzi_databases/processed/relumine_char_db_quality_check.json
analysis/hanzi_databases/processed/cl_analysis_stats.json            — CL 分析结构化结果
analysis/hanzi_databases/CL_ANALYSIS.md                              — 计算语言学分析报告
```

`CL_ANALYSIS.md` 是核心分析报告，包含：简化类型分布、笔画削减统计、合并复杂度、跨库一致性、语义歧义影响、字频分布、部件频率、前端文化计算指标和数据库贡献对比。

`relumine_char_db_summary.csv` 是 v1 数据库摘要。

`cultural_computation_summary.csv` 是文化计算摘要，可用于快速筛选高歧义、高 OCR 风险、需要人工精修的字。

`opencc_merge_candidates.csv` 是下一轮扩充候选表，从 OpenCC 中筛出”一个简体对应多个繁体”的字，并按候选数量和 CC-CEDICT 词级证据排序。

`relumine_char_db_quality_check.json` 是质量检查结果。

## 重新生成

确保 `analysis/hanzi_databases/raw/` 下已有外部数据库后运行：

```bash
# 1. 重新生成数据库（含 canonical_traditional 质量修复）
python3 analysis/hanzi_databases/scripts/build_relumine_database.py

# 2. 生成计算语言学分析报告
python3 analysis/hanzi_databases/scripts/computational_linguistics_analysis.py
```

## 当前 100 字构成和后续精修

当前 100 字已经完成结构化构建，但其中 90 个是 `auto_external`，主要价值是“证据齐全、可计算、可统计”。后续如果继续提高展示质量，可以按类型逐步人工精修：

| 类型 | 建议数量 | 说明 |
| --- | ---: | --- |
| 多繁合一 / 异体合并 | 50 | 最能体现本项目特色，如 `发、干、复、台、只` |
| 草书楷化 | 15 | 如 `学、书、东、车` 这一类 |
| 古字复用 | 10 | 如 `后、云、万、干` 等 |
| 偏旁类推 / 结构简省 | 15 | 适合连接 CHISE IDS 做部件统计 |
| 高频文化/古籍常用字 | 10 | 根据 OCR 古籍语料频率补齐 |

后续真正要“精修”的，是从 90 个自动扩展字里优先挑 20-30 个，补上 `stages`、`notes` 和简化依据。外部数据库证据已经自动接好了，人工主要负责历史解释和展示文本。
