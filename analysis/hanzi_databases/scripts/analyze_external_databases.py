from __future__ import annotations

import csv
import json
import re
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYSIS_DIR = REPO_ROOT / "analysis" / "hanzi_databases"
RAW_DIR = ANALYSIS_DIR / "raw"
OUT_DIR = ANALYSIS_DIR / "processed"
PROJECT_DB = REPO_ROOT / "apps" / "api" / "ocrforge_web" / "data" / "evolution.json"

SOURCE_URLS = {
    "Unihan": "https://www.unicode.org/Public/UCD/latest/ucd/Unihan.zip",
    "OpenCC": "https://github.com/BYVoid/OpenCC/tree/master/data/dictionary",
    "CC-CEDICT": "https://cc-cedict.org/editor/editor.php?handler=Download",
    "CHISE IDS": "https://gitlab.nijl.ac.jp/CHISE/ids",
}

HAN_RE = re.compile(
    "["
    "\u3400-\u4dbf"
    "\u4e00-\u9fff"
    "\uf900-\ufaff"
    "\U00020000-\U0002ebef"
    "\U00030000-\U000323af"
    "]"
)
U_CODE_RE = re.compile(r"U\+([0-9A-Fa-f]{4,6})")


def is_han(ch: str) -> bool:
    return bool(ch and HAN_RE.fullmatch(ch))


def extract_han(text: str) -> list[str]:
    return HAN_RE.findall(text or "")


def code_to_char(code: str) -> str:
    return chr(int(code[2:] if code.startswith("U+") else code, 16))


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


@dataclass
class ProjectData:
    records: list[dict]
    chars: set[str]
    roles: dict[str, set[str]]
    mappings: dict[str, set[str]]


def load_project_data() -> ProjectData:
    records = json.loads(PROJECT_DB.read_text(encoding="utf-8"))
    chars: set[str] = set()
    roles: dict[str, set[str]] = defaultdict(set)
    mappings: dict[str, set[str]] = defaultdict(set)

    for rec in records:
        simplified = rec["simplified"]
        chars.add(simplified)
        roles[simplified].add("simplified")

        for ch in extract_han(rec.get("traditional", "")):
            chars.add(ch)
            roles[ch].add("traditional")
            mappings[simplified].add(ch)

        for ch in rec.get("merges", []):
            if is_han(ch):
                chars.add(ch)
                roles[ch].add("merge_source")
                mappings[simplified].add(ch)

        for stage in rec.get("stages", []):
            for ch in extract_han(stage.get("form", "")):
                chars.add(ch)
                roles[ch].add("stage_form")

    return ProjectData(records=records, chars=chars, roles=roles, mappings=mappings)


def load_unihan() -> dict[str, dict[str, str]]:
    path = RAW_DIR / "Unihan.zip"
    props: dict[str, dict[str, str]] = defaultdict(dict)
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if not name.startswith("Unihan_") or not name.endswith(".txt"):
                continue
            with zf.open(name) as raw:
                for line_bytes in raw:
                    line = line_bytes.decode("utf-8").strip()
                    if not line or line.startswith("#"):
                        continue
                    code, key, value = line.split("\t", 2)
                    props[code_to_char(code)][key] = value
    return props


def unihan_variant_chars(value: str | None) -> set[str]:
    if not value:
        return set()
    return {code_to_char(match.group(1)) for match in U_CODE_RE.finditer(value)}


def parse_opencc_dict(path: Path) -> dict[str, list[str]]:
    table: dict[str, list[str]] = {}
    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "\t" not in line:
                continue
            key, value = line.split("\t", 1)
            table[key] = [item for item in value.split(" ") if item]
    return table


def load_cedict() -> tuple[list[dict], Counter, Counter, Counter]:
    path = RAW_DIR / "cc_cedict.zip"
    entries: list[dict] = []
    trad_counter: Counter = Counter()
    simp_counter: Counter = Counter()
    pair_counter: Counter = Counter()
    pattern = re.compile(r"^(\S+) (\S+) \[(.*?)\] /(.*)/$")

    with zipfile.ZipFile(path) as zf:
        with zf.open("cedict_ts.u8") as raw:
            for line_bytes in raw:
                line = line_bytes.decode("utf-8").strip()
                if not line or line.startswith("#"):
                    continue
                match = pattern.match(line)
                if not match:
                    continue
                traditional, simplified, pinyin, definition = match.groups()
                entries.append(
                    {
                        "traditional": traditional,
                        "simplified": simplified,
                        "pinyin": pinyin,
                        "definition": definition,
                    }
                )
                trad_counter.update(extract_han(traditional))
                simp_counter.update(extract_han(simplified))
                if len(traditional) == len(simplified):
                    for trad_ch, simp_ch in zip(traditional, simplified):
                        if is_han(trad_ch) and is_han(simp_ch):
                            pair_counter[(trad_ch, simp_ch)] += 1
    return entries, trad_counter, simp_counter, pair_counter


def load_chise_ids() -> dict[str, dict[str, str]]:
    root = RAW_DIR / "chise_ids"
    out: dict[str, dict[str, str]] = {}
    for path in sorted(root.glob("IDS-UCS*.txt")):
        with path.open(encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if not line or line.startswith(";;"):
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                code, ch, ids = parts[:3]
                if len(ch) != 1 or not is_han(ch):
                    continue
                out[ch] = {"codepoint": code, "ids": ids, "file": path.name}
    return out


def source_inventory(
    project: ProjectData,
    unihan: dict[str, dict[str, str]],
    opencc_st: dict[str, list[str]],
    opencc_ts: dict[str, list[str]],
    cedict_entries: list[dict],
    cedict_trad: Counter,
    cedict_simp: Counter,
    chise: dict[str, dict[str, str]],
) -> list[dict]:
    return [
        {
            "database": "Relumine evolution.json",
            "local_path": str(PROJECT_DB.relative_to(REPO_ROOT)),
            "record_count": len(project.records),
            "unique_chars": len(project.chars),
            "main_fields": "simplified, traditional, pinyin, stages, merges, notes",
            "best_for": "本项目自建字形流变与简化历程",
            "license_or_note": "项目内部数据",
            "source_url": "",
        },
        {
            "database": "Unihan",
            "local_path": "analysis/hanzi_databases/raw/Unihan.zip",
            "record_count": sum(len(props) for props in unihan.values()),
            "unique_chars": len(unihan),
            "main_fields": "kMandarin, kDefinition, kTotalStrokes, kRSUnicode, kTraditionalVariant, kSimplifiedVariant",
            "best_for": "编码、读音、释义、笔画、异体/繁简变体",
            "license_or_note": "Unicode 数据文件",
            "source_url": SOURCE_URLS["Unihan"],
        },
        {
            "database": "OpenCC",
            "local_path": "analysis/hanzi_databases/raw/opencc_STCharacters.txt; analysis/hanzi_databases/raw/opencc_TSCharacters.txt",
            "record_count": len(opencc_st) + len(opencc_ts),
            "unique_chars": len(set(opencc_st) | set(opencc_ts) | {v for vals in opencc_st.values() for v in vals} | {v for vals in opencc_ts.values() for v in vals}),
            "main_fields": "STCharacters, TSCharacters",
            "best_for": "繁简转换、繁简多候选关系",
            "license_or_note": "Apache-2.0",
            "source_url": SOURCE_URLS["OpenCC"],
        },
        {
            "database": "CC-CEDICT",
            "local_path": "analysis/hanzi_databases/raw/cc_cedict.zip",
            "record_count": len(cedict_entries),
            "unique_chars": len(set(cedict_trad) | set(cedict_simp)),
            "main_fields": "traditional word, simplified word, pinyin, English definition",
            "best_for": "词级繁简对齐、读音、释义例证",
            "license_or_note": "CC BY-SA 4.0",
            "source_url": SOURCE_URLS["CC-CEDICT"],
        },
        {
            "database": "CHISE IDS",
            "local_path": "analysis/hanzi_databases/raw/chise_ids",
            "record_count": len(chise),
            "unique_chars": len(chise),
            "main_fields": "codepoint, character, IDS",
            "best_for": "汉字结构分解、部件分析",
            "license_or_note": "GPL-2.0-or-later",
            "source_url": SOURCE_URLS["CHISE IDS"],
        },
    ]


def build_project_char_rows(
    project: ProjectData,
    unihan: dict[str, dict[str, str]],
    opencc_st: dict[str, list[str]],
    opencc_ts: dict[str, list[str]],
    cedict_trad: Counter,
    cedict_simp: Counter,
    chise: dict[str, dict[str, str]],
) -> list[dict]:
    rows = []
    for ch in sorted(project.chars, key=lambda c: (ord(c), c)):
        u_props = unihan.get(ch, {})
        rows.append(
            {
                "char": ch,
                "codepoint": f"U+{ord(ch):04X}",
                "project_roles": ";".join(sorted(project.roles.get(ch, []))),
                "in_unihan": "yes" if ch in unihan else "no",
                "unihan_mandarin": u_props.get("kMandarin", ""),
                "unihan_definition": u_props.get("kDefinition", ""),
                "unihan_total_strokes": u_props.get("kTotalStrokes", ""),
                "unihan_traditional_variant": u_props.get("kTraditionalVariant", ""),
                "unihan_simplified_variant": u_props.get("kSimplifiedVariant", ""),
                "opencc_s2t": " ".join(opencc_st.get(ch, [])),
                "opencc_t2s": " ".join(opencc_ts.get(ch, [])),
                "cedict_trad_occurrences": cedict_trad.get(ch, 0),
                "cedict_simp_occurrences": cedict_simp.get(ch, 0),
                "chise_ids": chise.get(ch, {}).get("ids", ""),
                "chise_file": chise.get(ch, {}).get("file", ""),
            }
        )
    return rows


def build_mapping_rows(
    project: ProjectData,
    unihan: dict[str, dict[str, str]],
    opencc_st: dict[str, list[str]],
    opencc_ts: dict[str, list[str]],
    cedict_pairs: Counter,
) -> list[dict]:
    rows = []
    for simplified, sources in sorted(project.mappings.items(), key=lambda item: item[0]):
        for traditional in sorted(sources, key=lambda c: (ord(c), c)):
            simp_props = unihan.get(simplified, {})
            trad_props = unihan.get(traditional, {})
            unihan_support = []
            if traditional in unihan_variant_chars(simp_props.get("kTraditionalVariant")):
                unihan_support.append("simp.kTraditionalVariant")
            if simplified in unihan_variant_chars(trad_props.get("kSimplifiedVariant")):
                unihan_support.append("trad.kSimplifiedVariant")

            opencc_t2s_values = opencc_ts.get(traditional, [])
            opencc_s2t_values = opencc_st.get(simplified, [])
            rows.append(
                {
                    "simplified": simplified,
                    "traditional_source": traditional,
                    "in_project_mapping": "yes",
                    "opencc_t2s_candidates": " ".join(opencc_t2s_values),
                    "opencc_t2s_has_project_simplified": "yes" if simplified in opencc_t2s_values else "no",
                    "opencc_s2t_candidates": " ".join(opencc_s2t_values),
                    "opencc_s2t_has_project_traditional": "yes" if traditional in opencc_s2t_values else "no",
                    "unihan_variant_support": ";".join(unihan_support),
                    "cedict_aligned_pair_count": cedict_pairs.get((traditional, simplified), 0),
                }
            )
    return rows


def summarize_mapping_rows(rows: list[dict]) -> dict[str, int]:
    return {
        "project_mapping_pairs": len(rows),
        "opencc_t2s_supported": sum(1 for row in rows if row["opencc_t2s_has_project_simplified"] == "yes"),
        "opencc_s2t_supported": sum(1 for row in rows if row["opencc_s2t_has_project_traditional"] == "yes"),
        "unihan_variant_supported": sum(1 for row in rows if row["unihan_variant_support"]),
        "cedict_evidence_supported": sum(1 for row in rows if int(row["cedict_aligned_pair_count"]) > 0),
    }


def write_report(
    inventory: list[dict],
    project_rows: list[dict],
    mapping_rows: list[dict],
) -> None:
    project_count = next(row for row in inventory if row["database"] == "Relumine evolution.json")
    unihan = next(row for row in inventory if row["database"] == "Unihan")
    opencc = next(row for row in inventory if row["database"] == "OpenCC")
    cedict = next(row for row in inventory if row["database"] == "CC-CEDICT")
    chise = next(row for row in inventory if row["database"] == "CHISE IDS")
    summary = summarize_mapping_rows(mapping_rows)

    fully_covered = [
        row["char"]
        for row in project_rows
        if row["in_unihan"] == "yes" and row["chise_ids"]
    ]
    no_chise = [row["char"] for row in project_rows if not row["chise_ids"]]
    no_unihan = [row["char"] for row in project_rows if row["in_unihan"] == "no"]

    lines = [
        "# 外部汉字数据库对比分析",
        "",
        "## 任务理解",
        "",
        "老师说的“多找一些数据库，然后做计算语言学上的事情”，可以落到一个比较清楚的工作流：先把公开汉字数据库下载到本地，再把它们和项目自建的 `evolution.json` 放在同一套字段下统计。这样不仅能说明我们参考了哪些成熟资源，也能看出自己的数据库补在哪里。",
        "",
        "本次已经下载并解析了四类外部资源：",
        "",
        "| 数据库 | 本地记录数 | 覆盖字符数 | 主要用途 |",
        "| --- | ---: | ---: | --- |",
    ]
    for row in [unihan, opencc, cedict, chise]:
        lines.append(
            f"| {row['database']} | {row['record_count']} | {row['unique_chars']} | {row['best_for']} |"
        )
    lines.extend(
        [
            "",
            f"项目当前自建数据库 `evolution.json` 有 {project_count['record_count']} 条单字记录，抽取到 {project_count['unique_chars']} 个相关字形（包括简体字、繁体字、合并来源和演化阶段字形）。",
            "",
            "## 统计结果",
            "",
            f"- 项目繁简/合并映射共 {summary['project_mapping_pairs']} 对。",
            f"- OpenCC 的繁转简方向支持 {summary['opencc_t2s_supported']} 对，简转繁方向支持 {summary['opencc_s2t_supported']} 对。",
            f"- Unihan 的变体字段直接支持 {summary['unihan_variant_supported']} 对。",
            f"- CC-CEDICT 的词条对齐能给出词级证据的有 {summary['cedict_evidence_supported']} 对。",
            f"- 项目相关字形中，同时能在 Unihan 和 CHISE IDS 找到的有 {len(fully_covered)} 个。",
        ]
    )
    if no_unihan:
        lines.append(f"- 没有在 Unihan 中找到的项目字形：{'、'.join(no_unihan)}。")
    if no_chise:
        lines.append(f"- 没有在 CHISE IDS 中找到结构分解的项目字形：{'、'.join(no_chise)}。")

    lines.extend(
        [
            "",
            "## 可以怎么对比分析",
            "",
            "1. 覆盖率分析：统计项目字库中的字，在 Unihan、OpenCC、CC-CEDICT、CHISE IDS 中分别是否出现。这个结果对应 `project_char_coverage.csv`。",
            "2. 繁简映射一致性分析：把项目里的 `學→学`、`發/髮→发`、`臺/檯/颱/台→台` 等关系，与 OpenCC 和 Unihan 的变体字段逐项比较。这个结果对应 `mapping_comparison.csv`。",
            "3. 词级证据分析：用 CC-CEDICT 的繁简词条对齐来验证某些字的实际词汇用例，例如 `發財/发财`、`理髮/理发` 这类词能证明同一个简体字在不同语义下承接了不同繁体来源。",
            "4. 字形结构分析：用 CHISE IDS 的部件分解补充本项目的“形声流变”板块。项目原来偏历史叙述，CHISE 可以补成机器可计算的部件结构字段。",
            "",
            "## 对项目数据库的启发",
            "",
            "目前项目自己的优势是把“简化历程”和“文化解释”写得比较清楚，这是 OpenCC 和 CC-CEDICT 没有的；但它的规模还小，字段也偏展示。后续可以吸收外部数据库的长处，把每个字扩成更完整的结构：",
            "",
            "- 基础层：从 Unihan 引入 Unicode、普通话读音、英文释义、笔画和变体字段。",
            "- 转换层：用 OpenCC 校验繁简映射，并标记多对一合并冲突。",
            "- 词汇层：用 CC-CEDICT 给每个争议映射补充词级例子和释义。",
            "- 字形层：用 CHISE IDS 给每个字补充 IDS 部件分解，便于做部件统计和形声结构分析。",
            "- 项目特色层：保留自己的 `stages`、`merges`、`notes`，专门描述历史演化和简化依据。",
            "",
            "这样最后形成的就不是简单复制某一个数据库，而是“博采众长”的组合型数据库：外部资源负责规模和可验证性，项目自建字段负责解释力和课程主题。",
            "",
            "## 输出文件",
            "",
            "- `processed/source_inventory.csv`：每个外部数据库的规模、字段、用途和来源。",
            "- `processed/project_char_coverage.csv`：项目相关字形在各数据库中的覆盖情况。",
            "- `processed/mapping_comparison.csv`：项目繁简映射与 OpenCC、Unihan、CC-CEDICT 的对比。",
            "",
            "## 数据来源",
            "",
            f"- Unihan: {SOURCE_URLS['Unihan']}",
            f"- OpenCC: {SOURCE_URLS['OpenCC']}",
            f"- CC-CEDICT: {SOURCE_URLS['CC-CEDICT']}",
            f"- CHISE IDS: {SOURCE_URLS['CHISE IDS']}",
            "",
        ]
    )
    (ANALYSIS_DIR / "DATABASE_COMPARISON.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    project = load_project_data()
    unihan = load_unihan()
    opencc_st = parse_opencc_dict(RAW_DIR / "opencc_STCharacters.txt")
    opencc_ts = parse_opencc_dict(RAW_DIR / "opencc_TSCharacters.txt")
    cedict_entries, cedict_trad, cedict_simp, cedict_pairs = load_cedict()
    chise = load_chise_ids()

    inventory = source_inventory(
        project,
        unihan,
        opencc_st,
        opencc_ts,
        cedict_entries,
        cedict_trad,
        cedict_simp,
        chise,
    )
    project_rows = build_project_char_rows(
        project,
        unihan,
        opencc_st,
        opencc_ts,
        cedict_trad,
        cedict_simp,
        chise,
    )
    mapping_rows = build_mapping_rows(project, unihan, opencc_st, opencc_ts, cedict_pairs)

    write_csv(
        OUT_DIR / "source_inventory.csv",
        inventory,
        [
            "database",
            "local_path",
            "record_count",
            "unique_chars",
            "main_fields",
            "best_for",
            "license_or_note",
            "source_url",
        ],
    )
    write_csv(
        OUT_DIR / "project_char_coverage.csv",
        project_rows,
        [
            "char",
            "codepoint",
            "project_roles",
            "in_unihan",
            "unihan_mandarin",
            "unihan_definition",
            "unihan_total_strokes",
            "unihan_traditional_variant",
            "unihan_simplified_variant",
            "opencc_s2t",
            "opencc_t2s",
            "cedict_trad_occurrences",
            "cedict_simp_occurrences",
            "chise_ids",
            "chise_file",
        ],
    )
    write_csv(
        OUT_DIR / "mapping_comparison.csv",
        mapping_rows,
        [
            "simplified",
            "traditional_source",
            "in_project_mapping",
            "opencc_t2s_candidates",
            "opencc_t2s_has_project_simplified",
            "opencc_s2t_candidates",
            "opencc_s2t_has_project_traditional",
            "unihan_variant_support",
            "cedict_aligned_pair_count",
        ],
    )
    write_report(inventory, project_rows, mapping_rows)

    print(json.dumps({
        "sources": len(inventory),
        "project_chars": len(project.chars),
        "mapping_pairs": len(mapping_rows),
        "outputs": [
            str((OUT_DIR / "source_inventory.csv").relative_to(REPO_ROOT)),
            str((OUT_DIR / "project_char_coverage.csv").relative_to(REPO_ROOT)),
            str((OUT_DIR / "mapping_comparison.csv").relative_to(REPO_ROOT)),
            str((ANALYSIS_DIR / "DATABASE_COMPARISON.md").relative_to(REPO_ROOT)),
        ],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
