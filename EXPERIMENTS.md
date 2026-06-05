# OCR 探究实验记录

用于简单记录 OCR 相关探索结果，后续实验继续追加即可。

## 2026-04-28 Tokenizer 字符覆盖率

问题：当前 `CultureCourse/models/DeepSeek-OCR-2` 的 tokenizer 能否覆盖数据集
GT 中出现的字，是否会出现 `unk`。

范围：统计 TKH、MTH、ICDAR2019-HDRC-Chinese 当前全部 train/test split，
共 2,670 个 GT 文件。

结果：

| 项目 | 数值 |
| --- | ---: |
| 非空白字符总数 | 734,081 |
| 非空白唯一字符 | 5,238 |
| CJK 汉字总数 | 730,564 |
| CJK 唯一汉字 | 5,197 |
| 无法编码字符 | 0 |
| `unk` 字符 | 0 |

补充：CJK 唯一汉字中，3,230 个是单 token，1,967 个会被拆成多 token。
例如 `大 -> [547]`，`諦 -> [5981, 102]`，`㩲 -> [162, 105, 113]`。

结论：当前 tokenizer 不会因为词表缺失把数据集中的字编码成 `unk`；罕见字和扩展区
汉字会被 byte-level/BPE 拆成多个 token，但可以正常还原。
