# 外部汉字数据库对比分析

## 任务理解

老师说的“多找一些数据库，然后做计算语言学上的事情”，可以落到一个比较清楚的工作流：先把公开汉字数据库下载到本地，再把它们和项目自建的 `evolution.json` 放在同一套字段下统计。这样不仅能说明我们参考了哪些成熟资源，也能看出自己的数据库补在哪里。

本次已经下载并解析了四类外部资源：

| 数据库 | 本地记录数 | 覆盖字符数 | 主要用途 |
| --- | ---: | ---: | --- |
| Unihan | 1555629 | 102998 | 编码、读音、释义、笔画、异体/繁简变体 |
| OpenCC | 8130 | 8169 | 繁简转换、繁简多候选关系 |
| CC-CEDICT | 125002 | 14382 | 词级繁简对齐、读音、释义例证 |
| CHISE IDS | 97431 | 97431 | 汉字结构分解、部件分析 |

项目当前自建数据库 `evolution.json` 有 10 条单字记录，抽取到 28 个相关字形（包括简体字、繁体字、合并来源和演化阶段字形）。

## 统计结果

- 项目繁简/合并映射共 18 对。
- OpenCC 的繁转简方向支持 13 对，简转繁方向支持 17 对。
- Unihan 的变体字段直接支持 18 对。
- CC-CEDICT 的词条对齐能给出词级证据的有 18 对。
- 项目相关字形中，同时能在 Unihan 和 CHISE IDS 找到的有 28 个。

## 可以怎么对比分析

1. 覆盖率分析：统计项目字库中的字，在 Unihan、OpenCC、CC-CEDICT、CHISE IDS 中分别是否出现。这个结果对应 `project_char_coverage.csv`。
2. 繁简映射一致性分析：把项目里的 `學→学`、`發/髮→发`、`臺/檯/颱/台→台` 等关系，与 OpenCC 和 Unihan 的变体字段逐项比较。这个结果对应 `mapping_comparison.csv`。
3. 词级证据分析：用 CC-CEDICT 的繁简词条对齐来验证某些字的实际词汇用例，例如 `發財/发财`、`理髮/理发` 这类词能证明同一个简体字在不同语义下承接了不同繁体来源。
4. 字形结构分析：用 CHISE IDS 的部件分解补充本项目的“形声流变”板块。项目原来偏历史叙述，CHISE 可以补成机器可计算的部件结构字段。

## 对项目数据库的启发

目前项目自己的优势是把“简化历程”和“文化解释”写得比较清楚，这是 OpenCC 和 CC-CEDICT 没有的；但它的规模还小，字段也偏展示。后续可以吸收外部数据库的长处，把每个字扩成更完整的结构：

- 基础层：从 Unihan 引入 Unicode、普通话读音、英文释义、笔画和变体字段。
- 转换层：用 OpenCC 校验繁简映射，并标记多对一合并冲突。
- 词汇层：用 CC-CEDICT 给每个争议映射补充词级例子和释义。
- 字形层：用 CHISE IDS 给每个字补充 IDS 部件分解，便于做部件统计和形声结构分析。
- 项目特色层：保留自己的 `stages`、`merges`、`notes`，专门描述历史演化和简化依据。

这样最后形成的就不是简单复制某一个数据库，而是“博采众长”的组合型数据库：外部资源负责规模和可验证性，项目自建字段负责解释力和课程主题。

## 输出文件

- `processed/source_inventory.csv`：每个外部数据库的规模、字段、用途和来源。
- `processed/project_char_coverage.csv`：项目相关字形在各数据库中的覆盖情况。
- `processed/mapping_comparison.csv`：项目繁简映射与 OpenCC、Unihan、CC-CEDICT 的对比。

## 数据来源

- Unihan: https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip
- OpenCC: https://github.com/BYVoid/OpenCC/tree/master/data/dictionary
- CC-CEDICT: https://cc-cedict.org/editor/editor.php?handler=Download
- CHISE IDS: https://gitlab.nijl.ac.jp/CHISE/ids
