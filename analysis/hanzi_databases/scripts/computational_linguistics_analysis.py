from __future__ import annotations

"""
计算语言学分析：Relumine 汉字数据库 v1

分析维度：
  1. 简化类型分布 — 草书楷化/古字复用/多对一合并 等类型的数量与比例
  2. 笔画削减量化 — 繁→简笔画差的均值、分布、极值
  3. 合并复杂度   — 每个简体字承接多少个繁体来源
  4. 跨库一致性   — Unihan / OpenCC / CC-CEDICT 三库对每对繁简关系的支持程度
  5. 语义歧义影响 — 合并后一个简体承接多少个不同语义
  6. 字频分布     — CC-CEDICT 词频代理排名
  7. 部件频率     — CHISE IDS 中出现最多的构字部件
"""

import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
ANALYSIS_DIR = REPO_ROOT / "analysis" / "hanzi_databases"
DATABASE_PATH = REPO_ROOT / "apps" / "api" / "ocrforge_web" / "data" / "relumine_char_db.v1.json"
OUT_DIR = ANALYSIS_DIR / "processed"
REPORT_PATH = ANALYSIS_DIR / "CL_ANALYSIS.md"
STATS_PATH = OUT_DIR / "cl_analysis_stats.json"
FIGURE_DIR = OUT_DIR / "figures"

# CHISE IDS composition operators
_IDS_OPS = set("⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻")


# ─────────────────────────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────────────────────────

def load_database() -> dict[str, Any]:
    return json.loads(DATABASE_PATH.read_text(encoding="utf-8"))


# ─────────────────────────────────────────────────────────────────
# 1. 简化类型分布
# ─────────────────────────────────────────────────────────────────

def _refine_type(char: dict[str, Any]) -> list[str]:
    """Infer a more accurate simplification type for auto_external records."""
    simplified = char["simplified"]
    source_chars = [s["char"] for s in char["traditional_sources"]]

    if char["curation_level"] == "handcrafted":
        return list(char["simplification_types"])

    # If the simplified char is itself one of the traditional sources
    # (e.g. 系→[系,係,繫]), it is an "古字复用" merge, not just a plain merge.
    if simplified in source_chars and len(source_chars) > 1:
        return ["多对一合并", "古字复用（简体兼用古体）"]
    if len(source_chars) == 1:
        return ["一对一映射"]
    return ["多对一合并"]


def simplification_type_analysis(chars: list[dict]) -> dict[str, Any]:
    type_counter: Counter[str] = Counter()
    chars_by_type: dict[str, list[str]] = defaultdict(list)

    for char in chars:
        for t in _refine_type(char):
            type_counter[t] += 1
            chars_by_type[t].append(char["simplified"])

    return {
        "distribution": dict(type_counter.most_common()),
        "chars_by_type": dict(chars_by_type),
        "handcrafted_types": {
            c["simplified"]: c["simplification_types"]
            for c in chars
            if c["curation_level"] == "handcrafted"
        },
        "ancient_reuse_chars": chars_by_type.get("古字复用（简体兼用古体）", []),
    }


# ─────────────────────────────────────────────────────────────────
# 2. 笔画削减量化
# ─────────────────────────────────────────────────────────────────

def _strokes(unihan_block: dict | None) -> int | None:
    if not unihan_block:
        return None
    raw = unihan_block.get("total_strokes")
    if not raw:
        return None
    return int(str(raw).split()[0])


def stroke_reduction_analysis(chars: list[dict]) -> dict[str, Any]:
    pairs: list[dict[str, Any]] = []

    for char in chars:
        simplified = char["simplified"]
        simp_s = _strokes(char["external_profile"].get("unihan"))
        if simp_s is None:
            continue

        for source in char["traditional_sources"]:
            trad = source["char"]
            if trad == simplified:
                continue
            trad_s = _strokes(source.get("unihan"))
            if trad_s is None:
                continue
            reduction = trad_s - simp_s
            pairs.append({
                "simplified": simplified,
                "traditional": trad,
                "simp_strokes": simp_s,
                "trad_strokes": trad_s,
                "reduction": reduction,
                "reduction_pct": round(reduction / trad_s * 100, 1) if trad_s else 0,
            })

    pairs.sort(key=lambda p: -p["reduction"])
    vals = [p["reduction"] for p in pairs]

    return {
        "pairs_analyzed": len(pairs),
        "mean_reduction": round(mean(vals), 2) if vals else 0,
        "median_reduction": int(median(vals)) if vals else 0,
        "max_reduction": pairs[0] if pairs else None,
        "min_reduction": pairs[-1] if pairs else None,
        "distribution": {
            "negative_or_zero": sum(1 for r in vals if r <= 0),
            "1_to_3": sum(1 for r in vals if 1 <= r <= 3),
            "4_to_6": sum(1 for r in vals if 4 <= r <= 6),
            "7_to_9": sum(1 for r in vals if 7 <= r <= 9),
            "10_plus": sum(1 for r in vals if r >= 10),
        },
        "top_reductions": pairs[:10],
    }


# ─────────────────────────────────────────────────────────────────
# 3. 合并复杂度
# ─────────────────────────────────────────────────────────────────

def merge_complexity_analysis(chars: list[dict]) -> dict[str, Any]:
    source_counts = Counter(len(c["traditional_sources"]) for c in chars)
    all_counts = [len(c["traditional_sources"]) for c in chars]

    high_merge = sorted(
        [
            {
                "simplified": c["simplified"],
                "canonical_traditional": c["canonical_traditional"],
                "source_count": len(c["traditional_sources"]),
                "sources": [s["char"] for s in c["traditional_sources"]],
            }
            for c in chars
            if len(c["traditional_sources"]) >= 3
        ],
        key=lambda x: -x["source_count"],
    )

    return {
        "distribution": dict(sorted(source_counts.items())),
        "mean_sources": round(mean(all_counts), 2),
        "total_source_pairs": sum(all_counts),
        "chars_with_2plus": sum(1 for n in all_counts if n >= 2),
        "chars_with_3plus": sum(1 for n in all_counts if n >= 3),
        "chars_with_4plus": sum(1 for n in all_counts if n >= 4),
        "high_merge_chars": high_merge,
    }


# ─────────────────────────────────────────────────────────────────
# 4. 跨库一致性
# ─────────────────────────────────────────────────────────────────

def database_agreement_analysis(chars: list[dict]) -> dict[str, Any]:
    buckets: Counter[int] = Counter()
    pairs: list[dict[str, Any]] = []

    for char in chars:
        simplified = char["simplified"]
        for source in char["traditional_sources"]:
            trad = source["char"]
            if trad == simplified:
                continue
            agreeing = []
            if source.get("unihan_variant_support"):
                agreeing.append("Unihan")
            if source.get("opencc", {}).get("traditional_to_simplified_has_target"):
                agreeing.append("OpenCC")
            if source.get("cc_cedict", {}).get("aligned_pair_count", 0) > 0:
                agreeing.append("CC-CEDICT")

            buckets[len(agreeing)] += 1
            pairs.append({
                "simplified": simplified,
                "traditional": trad,
                "agreement_count": len(agreeing),
                "agreeing_databases": agreeing,
            })

    total = len(pairs)
    return {
        "total_pairs": total,
        "agreement_distribution": dict(sorted(buckets.items())),
        "high_confidence_ratio": round(
            sum(1 for p in pairs if p["agreement_count"] >= 2) / total, 3
        ) if total else 0,
        "low_confidence_pairs": [p for p in pairs if p["agreement_count"] == 0],
        "all_three_agree_pairs": [p for p in pairs if p["agreement_count"] == 3],
    }


# ─────────────────────────────────────────────────────────────────
# 5. 语义歧义影响
# ─────────────────────────────────────────────────────────────────

def semantic_ambiguity_analysis(chars: list[dict]) -> dict[str, Any]:
    cases = []

    for char in chars:
        if len(char["traditional_sources"]) < 2:
            continue
        simplified = char["simplified"]
        meanings = []
        for source in char["traditional_sources"]:
            trad = source["char"]
            definition = (source.get("unihan") or {}).get("definition", "")
            examples = (source.get("cc_cedict") or {}).get("examples", [])
            example_words = [
                f"{e['traditional']}/{e['simplified']}"
                for e in examples[:2]
                if e["traditional"] != e["simplified"]
            ]
            meanings.append({
                "traditional": trad,
                "definition": (definition[:70] + "…") if len(definition) > 70 else definition,
                "example_words": example_words,
            })
        cases.append({
            "simplified": simplified,
            "canonical_traditional": char["canonical_traditional"],
            "merged_count": len(meanings),
            "sources": meanings,
        })

    cases.sort(key=lambda x: -x["merged_count"])
    return {
        "chars_with_merge": len(cases),
        "mean_merged_per_char": round(mean(c["merged_count"] for c in cases), 2) if cases else 0,
        "top_ambiguous_cases": cases[:12],
    }


# ─────────────────────────────────────────────────────────────────
# 6. 字频分布
# ─────────────────────────────────────────────────────────────────

def frequency_analysis(chars: list[dict]) -> dict[str, Any]:
    data = sorted(
        [
            {
                "simplified": c["simplified"],
                "cedict_occurrences": c["external_profile"]["cc_cedict_as_simplified_occurrences"],
                "curation_level": c["curation_level"],
                "source_count": len(c["traditional_sources"]),
            }
            for c in chars
        ],
        key=lambda x: -x["cedict_occurrences"],
    )
    for rank, item in enumerate(data, 1):
        item["frequency_rank"] = rank

    occ = [d["cedict_occurrences"] for d in data]
    return {
        "mean_occurrences": round(mean(occ), 1),
        "median_occurrences": int(median(occ)),
        "top_20": data[:20],
        "bottom_20": data[-20:],
        "tiers": {
            "high_200plus": sum(1 for x in occ if x >= 200),
            "mid_100_199": sum(1 for x in occ if 100 <= x < 200),
            "low_under_100": sum(1 for x in occ if x < 100),
        },
        "ranked": data,
    }


# ─────────────────────────────────────────────────────────────────
# 7. 部件频率（CHISE IDS）
# ─────────────────────────────────────────────────────────────────

def component_analysis(chars: list[dict]) -> dict[str, Any]:
    counter: Counter[str] = Counter()

    for char in chars:
        simplified = char["simplified"]
        ids_str = (char.get("external_profile") or {}).get("chise_ids") or ""
        for ch in ids_str:
            if ch in _IDS_OPS:
                continue
            if ord(ch) < 0x2E80:
                continue
            if ch == simplified:
                continue
            counter[ch] += 1

    most_common = [{"component": ch, "count": n} for ch, n in counter.most_common(20)]
    return {
        "unique_components": len(counter),
        "most_common": most_common,
        "singleton_components": sum(1 for n in counter.values() if n == 1),
    }


# ─────────────────────────────────────────────────────────────────
# 8. 前端文化计算指标
# ─────────────────────────────────────────────────────────────────

def cultural_computation_analysis(chars: list[dict]) -> dict[str, Any]:
    semantic_levels: Counter[str] = Counter()
    ocr_levels: Counter[str] = Counter()
    frequency_tiers: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()
    high_priority: list[dict[str, Any]] = []

    for char in chars:
        cultural = char.get("cultural_computation") or {}
        semantic = cultural.get("semantic_ambiguity") or {}
        risk = cultural.get("ocr_risk") or {}
        frequency = cultural.get("frequency_profile") or {}
        stroke = cultural.get("stroke_profile") or {}

        semantic_levels[semantic.get("level", "待算")] += 1
        ocr_levels[risk.get("level", "待算")] += 1
        frequency_tiers[frequency.get("tier", "待算")] += 1
        tag_counter.update(cultural.get("cultural_tags") or [])

        if risk.get("level") == "高" or semantic.get("level") == "高":
            high_priority.append(
                {
                    "simplified": char["simplified"],
                    "canonical_traditional": char["canonical_traditional"],
                    "semantic_level": semantic.get("level", "待算"),
                    "source_count": semantic.get("source_count", 0),
                    "ocr_risk_level": risk.get("level", "待算"),
                    "ocr_risk_score": risk.get("score", 0),
                    "frequency_tier": frequency.get("tier", "待算"),
                    "frequency_rank": frequency.get("rank_in_database", 0),
                    "avg_stroke_reduction": stroke.get("average_reduction", 0),
                    "tags": "、".join(cultural.get("cultural_tags") or []),
                }
            )

    high_priority.sort(
        key=lambda row: (
            -int(row["ocr_risk_score"]),
            int(row["frequency_rank"]) if row["frequency_rank"] else 999,
            row["simplified"],
        )
    )

    return {
        "semantic_levels": dict(semantic_levels),
        "ocr_risk_levels": dict(ocr_levels),
        "frequency_tiers": dict(frequency_tiers),
        "top_tags": dict(tag_counter.most_common(10)),
        "high_priority_chars": high_priority[:15],
    }


# ─────────────────────────────────────────────────────────────────
# Visualizations
# ─────────────────────────────────────────────────────────────────

def generate_figures(stats: dict[str, Any]) -> dict[str, str]:
    os.environ.setdefault("MPLCONFIGDIR", str(OUT_DIR / ".matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = [
        "Arial Unicode MS",
        "PingFang SC",
        "Heiti SC",
        "Songti SC",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    paths: dict[str, str] = {}

    def save(name: str) -> str:
        path = FIGURE_DIR / name
        plt.tight_layout()
        plt.savefig(path, dpi=180, bbox_inches="tight")
        plt.close()
        return str(path.relative_to(ANALYSIS_DIR))

    # 1. Stroke reduction distribution
    stroke_dist = stats["stroke_reduction"]["distribution"]
    labels = ["≤0", "1-3", "4-6", "7-9", "≥10"]
    values = [
        stroke_dist["negative_or_zero"],
        stroke_dist["1_to_3"],
        stroke_dist["4_to_6"],
        stroke_dist["7_to_9"],
        stroke_dist["10_plus"],
    ]
    plt.figure(figsize=(7.2, 4.2))
    bars = plt.bar(labels, values, color="#9a2a1f")
    plt.title("笔画削减分布")
    plt.xlabel("繁体笔画数 - 简体笔画数")
    plt.ylabel("繁简关系对数")
    for bar, value in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width() / 2, value + 0.6, str(value), ha="center", va="bottom")
    paths["stroke_reduction"] = save("stroke_reduction_distribution.png")

    # 2. Simplification type pie
    type_dist = stats["simplification_types"]["distribution"]
    type_labels = list(type_dist.keys())
    type_values = list(type_dist.values())
    plt.figure(figsize=(7.2, 5.2))
    plt.pie(
        type_values,
        labels=type_labels,
        autopct="%1.1f%%",
        startangle=90,
        textprops={"fontsize": 9},
    )
    plt.title("简化类型标签分布")
    paths["simplification_types"] = save("simplification_type_pie.png")

    # 3. Traditional source count distribution
    merge_dist = stats["merge_complexity"]["distribution"]
    source_labels = [str(k) for k in merge_dist.keys()]
    source_values = list(merge_dist.values())
    plt.figure(figsize=(7.2, 4.2))
    bars = plt.bar(source_labels, source_values, color="#c2a96a")
    plt.title("繁体来源数分布")
    plt.xlabel("每个简体字对应的来源字数")
    plt.ylabel("简体字数量")
    for bar, value in zip(bars, source_values):
        plt.text(bar.get_x() + bar.get_width() / 2, value + 0.6, str(value), ha="center", va="bottom")
    paths["source_counts"] = save("traditional_source_count_distribution.png")

    # 4. Frequency top 20
    top20 = list(reversed(stats["frequency"]["top_20"]))
    chars = [item["simplified"] for item in top20]
    freqs = [item["cedict_occurrences"] for item in top20]
    plt.figure(figsize=(8.4, 6.2))
    bars = plt.barh(chars, freqs, color="#4a4845")
    plt.title("CC-CEDICT 字频代理 Top 20")
    plt.xlabel("作为简体出现在词条中的次数")
    for bar, value in zip(bars, freqs):
        plt.text(value + 8, bar.get_y() + bar.get_height() / 2, str(value), va="center", fontsize=8)
    paths["frequency_top20"] = save("frequency_top20_bar.png")

    return paths


# ─────────────────────────────────────────────────────────────────
# Markdown report
# ─────────────────────────────────────────────────────────────────

def _table(headers: list[str], rows: list[list]) -> list[str]:
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    return lines


def generate_report(stats: dict[str, Any]) -> str:
    lines: list[str] = []

    lines += [
        "# 计算语言学分析报告：Relumine 汉字数据库 v1",
        "",
        "> 本报告从 Relumine 自建汉字数据库 v1（100 字）出发，融合 Unihan、OpenCC、CC-CEDICT、CHISE IDS"
        " 四个外部数据库，从七个维度做定量分析，展示「博采众长」形成的可计算汉字知识库的特征与价值。",
        "",
        "---",
    ]

    figures = stats.get("figures", {})
    if figures:
        lines += [
            "",
            "## 可视化图表",
            "",
            "下面四张图对应本文的核心计算语言学指标，便于在汇报中直接展示。",
            "",
            f"![笔画削减分布]({figures['stroke_reduction']})",
            "",
            f"![简化类型饼图]({figures['simplification_types']})",
            "",
            f"![繁体来源数分布]({figures['source_counts']})",
            "",
            f"![字频排名 Top 20]({figures['frequency_top20']})",
            "",
            "---",
        ]

    # ── 1. Simplification types ──
    lines += ["", "## 一、简化类型分布", ""]
    lines.append(
        "汉字简化并非一种操作，而是多种历史机制的叠加。"
        "我们对 100 字的简化类型做精化标注（auto_external 字区分「古字复用」与「纯合并」）："
    )
    lines.append("")
    st = stats["simplification_types"]
    lines += _table(
        ["简化类型", "字数", "占比"],
        [[t, n, f"{n}%"] for t, n in st["distribution"].items()],
    )
    lines += [
        "",
        "人工精修的 10 个字简化类型（最具典型性）：",
        "",
    ]
    for simp, types in st["handcrafted_types"].items():
        lines.append(f"- **{simp}**：{'、'.join(types)}")

    ancient = st["ancient_reuse_chars"]
    if ancient:
        example_str = "、".join(ancient[:8]) + ("……" if len(ancient) > 8 else "")
        lines += [
            "",
            (
                f"其中「简体兼用古体」型（如 `系→系/係/繫`）共 **{len(ancient)}** 字，"
                f"典型例：{example_str}。"
                "这类字的简体形式本身就是某个传统字体，故不能视为「创造新字形」，而应归入古字复用。"
            ),
        ]

    # ── 2. Stroke reduction ──
    lines += ["", "## 二、笔画削减量化分析", ""]
    sr = stats["stroke_reduction"]
    lines.append(f"共分析 **{sr['pairs_analyzed']}** 对繁→简字形，统计笔画削减量（繁体笔画 − 简体笔画）：")
    lines += [
        "",
        f"- 平均削减：**{sr['mean_reduction']} 笔**",
        f"- 中位数：**{sr['median_reduction']} 笔**",
    ]
    if sr["max_reduction"]:
        m = sr["max_reduction"]
        lines.append(
            f"- 削减最多：`{m['traditional']}→{m['simplified']}`"
            f"（{m['trad_strokes']} 笔→{m['simp_strokes']} 笔，减 **{m['reduction']} 笔**，削减率 {m['reduction_pct']}%）"
        )
    lines.append("")
    dist = sr["distribution"]
    lines += _table(
        ["笔画削减区间", "对数", "说明"],
        [
            ["≤ 0（无削减）", dist["negative_or_zero"], "简繁笔画相同或简体更复杂"],
            ["1–3 笔", dist["1_to_3"], "轻度简化"],
            ["4–6 笔", dist["4_to_6"], "中度简化"],
            ["7–9 笔", dist["7_to_9"], "重度简化"],
            ["≥ 10 笔", dist["10_plus"], "大幅简化"],
        ],
    )
    lines += ["", "削减最多的前 10 对：", ""]
    lines += _table(
        ["繁体", "简体", "繁体笔画", "简体笔画", "削减量", "削减率"],
        [
            [p["traditional"], p["simplified"], p["trad_strokes"],
             p["simp_strokes"], p["reduction"], f"{p['reduction_pct']}%"]
            for p in sr["top_reductions"]
        ],
    )

    # ── 3. Merge complexity ──
    lines += ["", "## 三、多繁一简合并复杂度", ""]
    mc = stats["merge_complexity"]
    lines.append(
        f"100 个字中，平均每个简体字对应 **{mc['mean_sources']}** 个繁体来源，"
        f"总来源关系对数 **{mc['total_source_pairs']}**："
    )
    lines.append("")
    lines += _table(
        ["繁体来源数", "字数", "占比"],
        [[k, v, f"{v}%"] for k, v in mc["distribution"].items()],
    )
    lines += ["", "来源数 ≥ 3 的字（合并最复杂，语义歧义风险最高）：", ""]
    lines += _table(
        ["简体", "规范繁体", "来源数", "全部来源字"],
        [
            [c["simplified"], c["canonical_traditional"],
             c["source_count"], "  ".join(c["sources"])]
            for c in mc["high_merge_chars"]
        ],
    )

    # ── 4. Database agreement ──
    lines += ["", "## 四、跨数据库一致性分析", ""]
    da = stats["database_agreement"]
    total = da["total_pairs"]
    lines.append(
        f"对 **{total}** 对繁→简映射，检验 Unihan 变体字段、OpenCC 繁→简词典、CC-CEDICT 词级对齐三库的支持情况："
    )
    lines.append("")
    lines += _table(
        ["一致库数", "对数", "占比", "可信度说明"],
        [
            [k, v, f"{round(v / total * 100, 1)}%",
             {0: "仅项目自有，待外部核查", 1: "单库支持，有待验证", 2: "双库一致，可信", 3: "三库全部支持，高置信"}[k]]
            for k, v in da["agreement_distribution"].items()
        ],
    )
    lines += [
        "",
        f"**高置信度对（≥2 库一致）占比：{round(da['high_confidence_ratio'] * 100, 1)}%**",
    ]
    low = da["low_confidence_pairs"]
    if low:
        lines += [
            "",
            f"零库一致的对（共 {len(low)} 对，需人工核查）：",
            " ".join(f"`{p['traditional']}→{p['simplified']}`" for p in low),
        ]

    # ── 5. Semantic ambiguity ──
    lines += ["", "## 五、语义歧义影响分析", ""]
    sa = stats["semantic_ambiguity"]
    lines.append(
        f"在 {sa['chars_with_merge']} 个多繁来源字中，每个简体字平均承接 **{sa['mean_merged_per_char']}** 个繁体字形的语义。"
        " 典型歧义案例（来源字数最多的 8 字）："
    )
    for case in sa["top_ambiguous_cases"][:8]:
        lines += ["", f"**`{case['simplified']}`**（→ `{case['canonical_traditional']}`，合并 {case['merged_count']} 个来源）"]
        for src in case["sources"]:
            ex = "、".join(src["example_words"])
            defi = src["definition"]
            lines.append(
                f"  - `{src['traditional']}`：{defi}" + (f"（例：{ex}）" if ex else "")
            )

    # ── 6. Frequency ──
    lines += ["", "## 六、字频分布（CC-CEDICT 词频代理）", ""]
    fa = stats["frequency"]
    tiers = fa["tiers"]
    lines.append(
        f"以 CC-CEDICT 词条中各字作为简体出现的次数作为实用频率的代理指标"
        f"（均值 {fa['mean_occurrences']} 次，中位数 {fa['median_occurrences']} 次）："
    )
    lines.append("")
    lines += _table(
        ["频率层", "字数", "占比"],
        [
            ["高频（≥ 200 次）", tiers["high_200plus"], f"{tiers['high_200plus']}%"],
            ["中频（100–199 次）", tiers["mid_100_199"], f"{tiers['mid_100_199']}%"],
            ["低频（< 100 次）", tiers["low_under_100"], f"{tiers['low_under_100']}%"],
        ],
    )
    lines += [
        "",
        "频率最高的 20 字：",
        "",
        " ".join(
            f"`{item['simplified']}`({item['cedict_occurrences']})"
            for item in fa["top_20"]
        ),
        "",
        "频率最低的 10 字（古籍/书面语偏重）：",
        "",
        " ".join(
            f"`{item['simplified']}`({item['cedict_occurrences']})"
            for item in fa["bottom_20"][-10:]
        ),
    ]

    # ── 7. Components ──
    lines += ["", "## 七、字形部件频率分析（CHISE IDS）", ""]
    ca = stats["components"]
    lines.append(
        f"基于 CHISE IDS 解析 100 个简体字的部件结构，共发现 **{ca['unique_components']}** 种独特部件，"
        f"其中 {ca['singleton_components']} 个仅出现一次（字形独有结构）。出现频率最高的 20 个部件："
    )
    lines.append("")
    top = ca["most_common"]
    half = len(top) // 2
    lines += _table(
        ["部件", "出现次数", "部件", "出现次数"],
        [
            [
                top[i]["component"], top[i]["count"],
                top[i + half]["component"] if i + half < len(top) else "",
                top[i + half]["count"] if i + half < len(top) else "",
            ]
            for i in range(half)
        ],
    )

    # ── 8. Frontend cultural computation ──
    lines += ["", "## 八、前端文化计算指标", ""]
    cc = stats["cultural_computation"]
    lines.append(
        "为避免分析只停留在报告层，本项目已把语义歧义、OCR 风险、字频优先级、部件变化等指标写入"
        " `relumine_char_db.v1.json`，并接入前端单字详情页。"
    )
    lines.append("")
    lines += _table(
        ["语义歧义等级", "字数"],
        [[k, v] for k, v in cc["semantic_levels"].items()],
    )
    lines.append("")
    lines += _table(
        ["OCR 风险等级", "字数"],
        [[k, v] for k, v in cc["ocr_risk_levels"].items()],
    )
    lines += ["", "优先关注的高风险/高歧义字：", ""]
    lines += _table(
        ["简体", "主繁体", "语义等级", "来源数", "OCR 风险", "字频层", "平均削减", "标签"],
        [
            [
                item["simplified"],
                item["canonical_traditional"],
                item["semantic_level"],
                item["source_count"],
                f"{item['ocr_risk_level']}({item['ocr_risk_score']})",
                item["frequency_tier"],
                item["avg_stroke_reduction"],
                item["tags"],
            ]
            for item in cc["high_priority_chars"][:10]
        ],
    )

    # ── 9. Database overview table ──
    lines += [
        "",
        "## 九、各数据库定位与贡献对比",
        "",
        "Relumine v1 数据库博采以下数据库之长，形成「规模+可验证+文化解释」三层结构：",
        "",
    ]
    lines += _table(
        ["数据库", "收录规模", "核心贡献", "许可协议"],
        [
            ["**Relumine v1**（本项目）", "100 字 · 211 来源对",
             "字形演化历程、简化文化解释、合并冲突标注", "项目内部"],
            ["Unihan（Unicode Consortium）", "102,998 字",
             "Unicode 码位、笔画数、读音、官方变体字段", "Unicode 数据文件"],
            ["OpenCC（BYVoid）", "8,130 条",
             "高精度繁简转换映射、一简多繁候选", "Apache-2.0"],
            ["CC-CEDICT", "125,002 词",
             "词级繁简对齐、读音、英文释义、词频代理", "CC BY-SA 4.0"],
            ["CHISE IDS", "97,431 字",
             "汉字结构分解（IDS 表达式）、部件可计算化", "GPL-2.0+"],
        ],
    )
    lines += [
        "",
        (
            "> **Relumine 的差异化价值**："
            "上述四个外部数据库均不记录「为什么这样简化」以及「合并带来了哪些语义歧义」。"
            "Relumine v1 在外部证据层之上叠加了演化叙述与冲突标注，"
            "是四库数据的诠释层与人文层，而非简单拼接。"
        ),
        "",
        "## 十、后续可增加的文化计算工作量",
        "",
        "- **古籍 OCR 联动标注**：OCR 输出文本后，自动标出数据库中已收录的繁简冲突字，并跳转到对应字条。",
        "- **真实语料覆盖率**：把 100 字库投到古籍 OCR 语料或公开古文语料上，统计命中率和高频缺口。",
        "- **OCR 错误样本回流**：把真实 OCR 错字记录回写到字库，形成「识别错误—字形原因—修正建议」链路。",
        "- **人工精修优先级**：继续结合字频、来源数、笔画削减量和 OCR 风险，排序下一批最值得补时间线的 20 个字。",
        "- **跨文本时代对比**：按先秦、汉魏、唐宋、明清语料分层，看哪些简化冲突更集中于古籍文本。",
        "",
        "---",
        "",
        f"*Generated from {DATABASE_PATH.name} · {stats['generated_at']}*",
    ]

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────

def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    db = load_database()
    chars = db["characters"]

    stats: dict[str, Any] = {
        "schema_version": db["schema_version"],
        "generated_at": db["generated_at"],
        "total_chars": len(chars),
        "simplification_types": simplification_type_analysis(chars),
        "stroke_reduction": stroke_reduction_analysis(chars),
        "merge_complexity": merge_complexity_analysis(chars),
        "database_agreement": database_agreement_analysis(chars),
        "semantic_ambiguity": semantic_ambiguity_analysis(chars),
        "frequency": frequency_analysis(chars),
        "components": component_analysis(chars),
        "cultural_computation": cultural_computation_analysis(chars),
    }
    stats["figures"] = generate_figures(stats)

    STATS_PATH.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    REPORT_PATH.write_text(generate_report(stats), encoding="utf-8")

    sr = stats["stroke_reduction"]
    da = stats["database_agreement"]
    print(
        json.dumps(
            {
                "total_chars": stats["total_chars"],
                "stroke_pairs_analyzed": sr["pairs_analyzed"],
                "mean_stroke_reduction": sr["mean_reduction"],
                "high_confidence_pairs_pct": f"{da['high_confidence_ratio'] * 100:.1f}%",
                "chars_with_merge": stats["semantic_ambiguity"]["chars_with_merge"],
                "unique_components": stats["components"]["unique_components"],
                "outputs": [
                    str(STATS_PATH.relative_to(REPO_ROOT)),
                    str(REPORT_PATH.relative_to(REPO_ROOT)),
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
