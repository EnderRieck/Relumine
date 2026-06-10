# 汉字数据库对比分析

这个目录用于把项目自建的 `evolution.json` 和外部公开汉字数据库放在一起做计算对比。

## 已下载的数据

原始数据放在 `raw/`，该目录已加入 `.gitignore`，避免把外部大文件误提交到仓库。

| 数据库 | 下载内容 | 用途 |
| --- | --- | --- |
| Unihan | `Unihan.zip` | Unicode、读音、释义、笔画、变体字段 |
| OpenCC | `STCharacters.txt`、`TSCharacters.txt` | 字级繁简转换和多候选映射 |
| CC-CEDICT | `cedict_ts.u8` zip | 词级繁简对齐、拼音、英文释义 |
| CHISE IDS | `chise_ids/` Git 仓库 | 汉字 IDS 结构分解 |

## 重新下载

```bash
mkdir -p analysis/hanzi_databases/raw

curl -L --fail \
  -o analysis/hanzi_databases/raw/Unihan.zip \
  https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip \
  -o analysis/hanzi_databases/raw/opencc_STCharacters.txt \
  https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/STCharacters.txt \
  -o analysis/hanzi_databases/raw/opencc_TSCharacters.txt \
  https://raw.githubusercontent.com/BYVoid/OpenCC/master/data/dictionary/TSCharacters.txt \
  -o analysis/hanzi_databases/raw/cc_cedict.zip \
  'https://cc-cedict.org/editor/editor_export_cedict.php?c=zip'

git clone --depth 1 \
  https://gitlab.nijl.ac.jp/CHISE/ids.git \
  analysis/hanzi_databases/raw/chise_ids
```

## 重新生成结果

```bash
python3 analysis/hanzi_databases/scripts/analyze_external_databases.py
```

生成文件：

- `DATABASE_COMPARISON.md`：中文分析报告。
- `processed/source_inventory.csv`：外部数据库规模和字段说明。
- `processed/project_char_coverage.csv`：项目相关字形在外部数据库中的覆盖情况。
- `processed/mapping_comparison.csv`：项目繁简映射与外部数据库的对比。

## 构建项目自有数据库

```bash
python3 analysis/hanzi_databases/scripts/build_relumine_database.py
```

生成文件：

- `apps/api/ocrforge_web/data/relumine_char_db.v1.json`：Relumine 自建汉字数据库 v1。
- `processed/relumine_char_db_summary.csv`：v1 数据库摘要。
- `processed/cultural_computation_summary.csv`：语义歧义、OCR 风险、字频优先级等文化计算摘要。
- `processed/opencc_merge_candidates.csv`：后续扩充候选字表。
- `RELUMINE_CHAR_DB_V1.md`：v1 数据库结构说明。

## 前端展示能力

当前字形流变页面已经接入 `relumine_char_db.v1.json`，支持：

- 单字详情：繁简来源、笔画削减、外部数据库证据、文化计算指标。
- 数据库总览：OCR 高风险、高语义歧义、多繁一简、高频用字统计。
- Top 榜单：OCR 风险、语义歧义、笔画削减、字频排名。
- 筛选排序：按高 OCR 风险、高语义歧义、多繁一简、古字复用、人工精修筛选，并可按字频、风险、来源数、笔画削减排序。
- 语料覆盖率：粘贴古籍文本或 OCR 输出后，统计本数据库命中字、命中次数、高风险字命中。
- 数据导出：在前端导出当前 100 字数据库的 JSON 或 CSV。
