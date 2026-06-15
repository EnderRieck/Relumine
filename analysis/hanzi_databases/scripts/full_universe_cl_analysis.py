"""Full-universe computational-linguistics analysis over relumine_char_db.v2.json.

Produces apps/api/ocrforge_web/data/cl_analysis.v1.json consumed by the web UI,
plus a processed/ JSON copy for the report. Four analyses:

1. stroke-reduction distribution on all 4,941 chars vs the curated 100
2. least-effort check: does frequency correlate with stroke reduction?
3. homophony classification of every multi-source merge group
4. OCR confusion-pair prediction from CHISE IDS structural similarity
   (prediction only — validation against real OCR errors needs GPU runs)
"""

from __future__ import annotations

import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from analyze_external_databases import OUT_DIR, RAW_DIR, REPO_ROOT, load_chise_ids, load_unihan

V2_PATH = REPO_ROOT / "apps" / "api" / "ocrforge_web" / "data" / "relumine_char_db.v2.json"
OUT_API_PATH = REPO_ROOT / "apps" / "api" / "ocrforge_web" / "data" / "cl_analysis.v1.json"
OUT_PROCESSED_PATH = OUT_DIR / "full_universe_cl_analysis.json"

_IDS_OPS = set("⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻")


def strip_tone(syllable: str) -> str:
    decomposed = unicodedata.normalize("NFD", syllable)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def readings(pinyin: str | None) -> list[str]:
    if not pinyin:
        return []
    return [part for part in str(pinyin).split() if part]


def reduction_bucket(value: int | None) -> str:
    if value is None:
        return "未知"
    if value <= 0:
        return "≤0"
    if value <= 3:
        return "1–3"
    if value <= 6:
        return "4–6"
    if value <= 9:
        return "7–9"
    return "≥10"


def summarize_reductions(rows: list[dict]) -> dict:
    values = [row["stroke_reduction"] for row in rows if row["stroke_reduction"] is not None]
    values.sort()
    buckets = Counter(reduction_bucket(row["stroke_reduction"]) for row in rows)
    n = len(values)
    return {
        "char_count": len(rows),
        "with_strokes": n,
        "mean": round(sum(values) / n, 2) if n else 0,
        "median": values[n // 2] if n else 0,
        "max": values[-1] if n else 0,
        "min": values[0] if n else 0,
        "buckets": {key: buckets.get(key, 0) for key in ["≤0", "1–3", "4–6", "7–9", "≥10", "未知"]},
    }


def pearson(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs) ** 0.5
    vy = sum((y - my) ** 2 for y in ys) ** 0.5
    return cov / (vx * vy) if vx and vy else 0.0


def spearman(xs: list[float], ys: list[float]) -> float:
    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg_rank = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg_rank
            i = j + 1
        return out

    return pearson(ranks(xs), ranks(ys))


def levenshtein(a: str, b: str, cap: int) -> int:
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = cur[0]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
            best = min(best, cur[j])
        if best > cap:
            return cap + 1
        prev = cur
    return prev[-1]


def main() -> None:
    db = json.loads(V2_PATH.read_text(encoding="utf-8"))
    full_records = db["characters"]
    slim_records = db["slim_characters"]
    unihan = load_unihan()
    chise = load_chise_ids()

    def strokes(ch: str) -> int | None:
        raw = unihan.get(ch, {}).get("kTotalStrokes")
        if not raw:
            return None
        first = str(raw).split()[0]
        return int(first) if first.isdigit() else None

    # unified per-char rows: simplified, canonical trad, reduction, frequency, curated flag
    rows: list[dict] = []
    merge_groups: list[dict] = []
    for record in full_records + slim_records:
        simplified = record["simplified"]
        canonical = record.get("canonical_traditional") or simplified
        simp_strokes, trad_strokes = strokes(simplified), strokes(canonical)
        slim = record.get("slim") or {}
        frequency = slim.get("frequency")
        if frequency is None:
            frequency = int((record.get("external_profile") or {}).get("cc_cedict_as_simplified_occurrences") or 0)
        rows.append(
            {
                "simplified": simplified,
                "traditional": canonical,
                "stroke_reduction": (trad_strokes - simp_strokes)
                if (trad_strokes is not None and simp_strokes is not None and canonical != simplified)
                else (0 if canonical == simplified else None),
                "frequency": frequency,
                "curated": record.get("curation_level") in ("handcrafted", "auto_external"),
            }
        )
        sources = [item["char"] for item in record.get("traditional_sources") or [] if item.get("char")]
        real_sources = [ch for ch in sources if ch != simplified]
        if len(real_sources) > 1:
            merge_groups.append({"simplified": simplified, "sources": real_sources, "record": record})

    # ── 1. stroke reduction: full universe vs curated ──
    reduction = {
        "full": summarize_reductions(rows),
        "curated": summarize_reductions([row for row in rows if row["curated"]]),
    }

    # ── 2. least-effort principle ──
    le_rows = [row for row in rows if row["stroke_reduction"] is not None and row["frequency"] > 0]
    import math

    xs = [math.log10(row["frequency"]) for row in le_rows]
    ys = [float(row["stroke_reduction"]) for row in le_rows]
    deciles = []
    ranked = sorted(le_rows, key=lambda row: row["frequency"])
    step = max(len(ranked) // 10, 1)
    for index in range(10):
        chunk = ranked[index * step : (index + 1) * step] if index < 9 else ranked[9 * step :]
        if not chunk:
            continue
        reductions = [row["stroke_reduction"] for row in chunk]
        deciles.append(
            {
                "decile": index + 1,
                "freq_range": [chunk[0]["frequency"], chunk[-1]["frequency"]],
                "mean_reduction": round(sum(reductions) / len(reductions), 2),
                "char_count": len(chunk),
            }
        )
    least_effort = {
        "char_count": len(le_rows),
        "pearson_logfreq": round(pearson(xs, ys), 4),
        "spearman": round(spearman([float(row["frequency"]) for row in le_rows], ys), 4),
        "deciles": deciles,
        "note": "频率为 CC-CEDICT 词条出现次数代理；仅含频率>0 且笔画可比的字。",
    }

    # ── 3. homophony of merge groups ──
    homophony_counter: Counter = Counter()
    homophony_examples: dict[str, list[dict]] = defaultdict(list)
    for group in merge_groups:
        simplified = group["simplified"]
        simp_readings = readings(unihan.get(simplified, {}).get("kMandarin"))
        if not simp_readings:
            homophony_counter["读音缺失"] += 1
            continue
        statuses = []
        details = []
        for source in group["sources"]:
            src_readings = readings(unihan.get(source, {}).get("kMandarin"))
            if not src_readings:
                statuses.append("missing")
                continue
            if set(src_readings) & set(simp_readings):
                statuses.append("exact")
            elif {strip_tone(r) for r in src_readings} & {strip_tone(r) for r in simp_readings}:
                statuses.append("tone")
            else:
                statuses.append("diff")
            details.append(f"{source}({'/'.join(src_readings[:2])})")
        known = [s for s in statuses if s != "missing"]
        if not known:
            label = "读音缺失"
        elif all(s == "exact" for s in known):
            label = "完全同音"
        elif all(s in ("exact", "tone") for s in known):
            label = "声同调异"
        elif any(s in ("exact", "tone") for s in known):
            label = "部分同音"
        else:
            label = "非同音"
        homophony_counter[label] += 1
        if len(homophony_examples[label]) < 6:
            homophony_examples[label].append(
                {
                    "simplified": f"{simplified}({'/'.join(simp_readings[:2])})",
                    "sources": details,
                }
            )
    homophony = {
        "group_count": len(merge_groups),
        "distribution": dict(homophony_counter),
        "examples": dict(homophony_examples),
        "note": "按 Unihan kMandarin 读音比对每组多对一合并：来源字与简体是否同音，是检验「同音替代」机制占比的数据驱动版本。",
    }

    # ── 4. OCR confusion-pair prediction (IDS structural similarity) ──
    # universe: traditional glyphs shown in the grid (canonical + merge sources)
    glyphs: set[str] = set()
    glyph_to_simp: dict[str, str] = {}
    for record in full_records + slim_records:
        simplified = record["simplified"]
        for ch in [record.get("canonical_traditional") or simplified] + [
            item["char"] for item in record.get("traditional_sources") or [] if item.get("char")
        ]:
            if ch and ch not in glyphs:
                glyphs.add(ch)
                glyph_to_simp[ch] = simplified

    ids_of = {ch: chise[ch]["ids"] for ch in glyphs if ch in chise and len(chise[ch]["ids"]) >= 3}

    def components(ids: str, self_char: str) -> list[str]:
        return [ch for ch in ids if ch != self_char and ch not in _IDS_OPS and ord(ch) >= 0x2E80]

    # candidate pairs: share a component and have close stroke counts
    by_component: dict[str, list[str]] = defaultdict(list)
    for ch, ids in ids_of.items():
        for comp in set(components(ids, ch)):
            by_component[comp].append(ch)

    seen_pairs: set[tuple[str, str]] = set()
    confusion_pairs: list[dict] = []
    for comp, members in by_component.items():
        if len(members) < 2 or len(members) > 400:
            continue
        for i in range(len(members)):
            for j in range(i + 1, len(members)):
                a, b = sorted((members[i], members[j]))
                if (a, b) in seen_pairs:
                    continue
                seen_pairs.add((a, b))
                sa, sb = strokes(a), strokes(b)
                if sa is None or sb is None or abs(sa - sb) > 2:
                    continue
                ids_a, ids_b = ids_of[a], ids_of[b]
                max_len = max(len(ids_a), len(ids_b))
                cap = max(2, int(max_len * 0.45))
                dist = levenshtein(ids_a, ids_b, cap)
                if dist > cap:
                    continue
                similarity = round(1 - dist / max_len, 3)
                if similarity < 0.6:
                    continue
                shared = sorted(set(components(ids_a, a)) & set(components(ids_b, b)))
                confusion_pairs.append(
                    {
                        "a": a,
                        "b": b,
                        "a_simplified": glyph_to_simp.get(a, ""),
                        "b_simplified": glyph_to_simp.get(b, ""),
                        "similarity": similarity,
                        "strokes": [sa, sb],
                        "shared_components": shared[:6],
                    }
                )
    confusion_pairs.sort(key=lambda item: (-item["similarity"], item["a"]))
    confusion = {
        "glyphs_with_ids": len(ids_of),
        "pair_count": len(confusion_pairs),
        "top_pairs": confusion_pairs[:120],
        "note": "基于 CHISE IDS 结构编辑距离的混淆对预测（相似度≥0.6 且笔画差≤2）。真实 OCR 错误验证待 GPU 评测恢复后进行。",
    }

    payload = {
        "schema_version": "relumine-cl-analysis-v1",
        "generated_from": "relumine_char_db.v2.json",
        "stroke_reduction": reduction,
        "least_effort": least_effort,
        "homophony": homophony,
        "ocr_confusion": confusion,
    }
    OUT_API_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    OUT_PROCESSED_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT_API_PATH.relative_to(REPO_ROOT)),
                "reduction_full_mean": reduction["full"]["mean"],
                "reduction_curated_mean": reduction["curated"]["mean"],
                "pearson_logfreq": least_effort["pearson_logfreq"],
                "spearman": least_effort["spearman"],
                "homophony": homophony["distribution"],
                "confusion_pairs": confusion["pair_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
