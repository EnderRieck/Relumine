from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from analyze_external_databases import (
    ANALYSIS_DIR,
    OUT_DIR,
    RAW_DIR,
    REPO_ROOT,
    SOURCE_URLS,
    extract_han,
    is_han,
    load_cedict,
    load_chise_ids,
    load_project_data,
    load_unihan,
    parse_opencc_dict,
    unihan_variant_chars,
    write_csv,
)


DATABASE_PATH = REPO_ROOT / "apps" / "api" / "ocrforge_web" / "data" / "relumine_char_db.v1.json"
DATABASE_V2_PATH = REPO_ROOT / "apps" / "api" / "ocrforge_web" / "data" / "relumine_char_db.v2.json"
SQLITE_PATH = REPO_ROOT / "apps" / "api" / "ocrforge_web" / "data" / "relumine_char_db.v2.sqlite"
SUMMARY_PATH = OUT_DIR / "relumine_char_db_summary.csv"
CANDIDATES_PATH = OUT_DIR / "opencc_merge_candidates.csv"
QUALITY_CHECK_PATH = OUT_DIR / "relumine_char_db_quality_check.json"
CULTURAL_SUMMARY_PATH = OUT_DIR / "cultural_computation_summary.csv"
FINAL_TARGET_RECORDS = 100
_IDS_OPS = set("⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻")


def char_codepoint(ch: str) -> str:
    return f"U+{ord(ch):04X}"


def char_label(ch: str) -> str:
    return f"{ch} ({char_codepoint(ch)})"


def value_chars(value: str | None) -> list[str]:
    return sorted(unihan_variant_chars(value), key=lambda ch: (ord(ch), ch))


def unihan_profile(ch: str, unihan: dict[str, dict[str, str]]) -> dict[str, Any]:
    props = unihan.get(ch, {})
    return {
        "char": ch,
        "codepoint": char_codepoint(ch),
        "mandarin": props.get("kMandarin"),
        "definition": props.get("kDefinition"),
        "total_strokes": props.get("kTotalStrokes"),
        "radical_stroke": props.get("kRSUnicode"),
        "kangxi": props.get("kKangXi"),
        "traditional_variants": value_chars(props.get("kTraditionalVariant")),
        "simplified_variants": value_chars(props.get("kSimplifiedVariant")),
        "semantic_variants": value_chars(props.get("kSemanticVariant")),
        "z_variants": value_chars(props.get("kZVariant")),
        "source": "Unihan" if props else None,
    }


def infer_simplification_types(record: dict[str, Any]) -> list[str]:
    text = json.dumps(record, ensure_ascii=False)
    out: list[str] = []
    if len(record.get("merges", [])) > 1 or "多对一" in text or "合并" in text:
        out.append("多对一合并")
    if "草书" in text:
        out.append("草书楷化")
    if "符号化" in text or "简省" in text or "省略" in text:
        out.append("符号化简省")
    if "古字" in text or "并回" in text or "恢复" in text:
        out.append("古字复用")
    if "俗字" in text or "异体字" in text or "异体" in text:
        out.append("异体字采纳")
    if not out:
        out.append("待人工标注")
    return out


def source_role(source: str, record: dict[str, Any]) -> str:
    simplified = record["simplified"]
    traditional = record.get("traditional", "")
    merges = set(record.get("merges", []))
    if source == simplified:
        return "identity_or_reused_form"
    if source == traditional:
        return "canonical_traditional"
    if source in merges:
        return "merge_source"
    return "stage_or_related_form"


def cedict_examples_for_pair(
    entries: list[dict[str, str]],
    traditional_char: str,
    simplified_char: str,
    limit: int = 5,
) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    for entry in entries:
        traditional = entry["traditional"]
        simplified = entry["simplified"]
        if len(traditional) != len(simplified):
            continue
        ok = False
        for trad_ch, simp_ch in zip(traditional, simplified):
            if trad_ch == traditional_char and simp_ch == simplified_char:
                ok = True
                break
        if not ok:
            continue
        if traditional == traditional_char and simplified == simplified_char:
            # Single-character entries are useful, but word examples are better
            # for explaining ambiguity to non-technical readers.
            priority = 1
        else:
            priority = 0
        examples.append({**entry, "_priority": str(priority)})
    examples.sort(key=lambda item: (item["_priority"], len(item["traditional"]), item["traditional"]))
    cleaned = []
    for item in examples[:limit]:
        cleaned.append(
            {
                "traditional": item["traditional"],
                "simplified": item["simplified"],
                "pinyin": item["pinyin"],
                "definition": item["definition"],
            }
        )
    return cleaned


def build_traditional_source(
    source: str,
    simplified: str,
    record: dict[str, Any],
    unihan: dict[str, dict[str, str]],
    opencc_st: dict[str, list[str]],
    opencc_ts: dict[str, list[str]],
    cedict_entries: list[dict[str, str]],
    cedict_pairs: Counter,
    chise: dict[str, dict[str, str]],
) -> dict[str, Any]:
    simp_props = unihan.get(simplified, {})
    source_props = unihan.get(source, {})
    unihan_support = []
    if source in unihan_variant_chars(simp_props.get("kTraditionalVariant")):
        unihan_support.append("simplified.kTraditionalVariant")
    if simplified in unihan_variant_chars(source_props.get("kSimplifiedVariant")):
        unihan_support.append("source.kSimplifiedVariant")

    opencc_t2s = opencc_ts.get(source, [])
    opencc_s2t = opencc_st.get(simplified, [])
    return {
        "char": source,
        "codepoint": char_codepoint(source),
        "role": source_role(source, record),
        "unihan": unihan_profile(source, unihan),
        "chise_ids": chise.get(source, {}).get("ids"),
        "opencc": {
            "traditional_to_simplified_candidates": opencc_t2s,
            "traditional_to_simplified_has_target": simplified in opencc_t2s,
            "simplified_to_traditional_candidates": opencc_s2t,
            "simplified_to_traditional_has_source": source in opencc_s2t,
        },
        "cc_cedict": {
            "aligned_pair_count": int(cedict_pairs.get((source, simplified), 0)),
            "examples": cedict_examples_for_pair(cedict_entries, source, simplified),
        },
        "unihan_variant_support": unihan_support,
    }


def project_source_chars(record: dict[str, Any]) -> list[str]:
    simplified = record["simplified"]
    chars = set(extract_han(record.get("traditional", "")))
    chars.update(ch for ch in record.get("merges", []) if is_han(ch))
    if not chars:
        chars.add(simplified)
    if simplified in record.get("merges", []):
        chars.add(simplified)
    return sorted(chars, key=lambda ch: (ch != record.get("traditional", ""), ord(ch), ch))


def opencc_merge_candidate_rows(
    opencc_st: dict[str, list[str]],
    unihan: dict[str, dict[str, str]],
    cedict_entries: list[dict[str, str]],
    cedict_pairs: Counter,
    chise: dict[str, dict[str, str]],
    project_simplified: set[str],
) -> list[dict[str, Any]]:
    rows = []
    for simplified, candidates in opencc_st.items():
        han_candidates = [candidate for candidate in candidates if len(candidate) == 1 and is_han(candidate)]
        if len(han_candidates) <= 1 or not is_han(simplified):
            continue
        pair_counts = [int(cedict_pairs.get((candidate, simplified), 0)) for candidate in han_candidates]
        quality_candidates = [
            candidate
            for candidate, count in zip(han_candidates, pair_counts)
            if candidate in unihan and candidate in chise and count > 0
        ]
        excluded_candidates = [candidate for candidate in han_candidates if candidate not in quality_candidates]
        source_chars_with_cedict_evidence = sum(1 for count in pair_counts if count > 0)
        source_chars_with_unihan = sum(1 for candidate in han_candidates if candidate in unihan)
        source_chars_with_chise = sum(1 for candidate in han_candidates if candidate in chise)
        example_bits = []
        for candidate in han_candidates[:3]:
            examples = cedict_examples_for_pair(cedict_entries, candidate, simplified, limit=1)
            if examples:
                example_bits.append(f"{examples[0]['traditional']}->{examples[0]['simplified']}")
        rows.append(
            {
                "simplified": simplified,
                "candidates": han_candidates,
                "quality_candidates": quality_candidates,
                "excluded_candidates": excluded_candidates,
                "traditional_candidates": " ".join(han_candidates),
                "retained_traditional_candidates": " ".join(quality_candidates),
                "excluded_traditional_candidates": " ".join(excluded_candidates),
                "candidate_count": len(han_candidates),
                "retained_candidate_count": len(quality_candidates),
                "cc_cedict_pair_evidence": sum(pair_counts),
                "source_chars_with_cedict_evidence": source_chars_with_cedict_evidence,
                "source_chars_with_unihan": source_chars_with_unihan,
                "source_chars_with_chise": source_chars_with_chise,
                "quality_gate": (
                    "pass"
                    if simplified in unihan
                    and simplified in chise
                    and sum(pair_counts) > 0
                    and len(quality_candidates) > 1
                    else "review"
                ),
                "unihan_traditional_variants": " ".join(value_chars(unihan.get(simplified, {}).get("kTraditionalVariant"))),
                "has_chise_ids": "yes" if simplified in chise else "no",
                "already_in_project": "yes" if simplified in project_simplified else "no",
                "example_pairs": " | ".join(example_bits),
            }
        )
    rows.sort(
        key=lambda row: (
            row["quality_gate"] != "pass",
            row["already_in_project"] == "yes",
            -int(row["retained_candidate_count"]),
            -int(row["cc_cedict_pair_evidence"]),
            row["simplified"],
        )
    )
    return rows


def _brief_meaning(source_rec: dict[str, Any]) -> str:
    """Extract a brief English meaning from Unihan definition (first phrase before ; or ,)."""
    definition = (source_rec.get("unihan") or {}).get("definition") or ""
    if not definition:
        examples = (source_rec.get("cc_cedict") or {}).get("examples") or []
        return examples[0]["traditional"] if examples else ""
    phrase = definition.split(";")[0].split(",")[0].strip()
    return phrase[:28].rstrip() + ("…" if len(phrase) > 28 else "")


def _stroke_count(unihan_block: dict[str, Any] | None) -> int | None:
    if not unihan_block:
        return None
    raw = unihan_block.get("total_strokes")
    if not raw:
        return None
    value = str(raw).split()[0]
    return int(value) if value.isdigit() else None


def _ids_components(ids: str | None, self_char: str) -> list[str]:
    if not ids:
        return []
    components: list[str] = []
    for ch in ids:
        if ch == self_char or ch in _IDS_OPS or ord(ch) < 0x2E80:
            continue
        if ch not in components:
            components.append(ch)
    return components


def _risk_level(score: int) -> str:
    if score >= 6:
        return "高"
    if score >= 3:
        return "中"
    return "低"


def build_cultural_computation(record: dict[str, Any], frequency_rank: int) -> dict[str, Any]:
    simplified = record["simplified"]
    sources = record["traditional_sources"]
    source_count = len(sources)
    types = record.get("simplification_types", [])
    occurrence_count = int(record["external_profile"].get("cc_cedict_as_simplified_occurrences") or 0)

    meanings = []
    for source in sources:
        meaning = _brief_meaning(source)
        if meaning:
            meanings.append({"char": source["char"], "meaning": meaning})
    unique_meanings = []
    seen_meanings: set[str] = set()
    for item in meanings:
        if item["meaning"] in seen_meanings:
            continue
        seen_meanings.add(item["meaning"])
        unique_meanings.append(item)

    semantic_score = source_count + max(len(unique_meanings) - 1, 0)
    semantic_level = "高" if semantic_score >= 5 else "中" if semantic_score >= 3 else "低"

    simp_strokes = _stroke_count(record["external_profile"].get("unihan"))
    reductions = []
    for source in sources:
        trad_strokes = _stroke_count(source.get("unihan"))
        if trad_strokes is None or simp_strokes is None or source["char"] == simplified:
            continue
        reductions.append(trad_strokes - simp_strokes)
    avg_reduction = round(sum(reductions) / len(reductions), 1) if reductions else 0

    canonical = next(
        (source for source in sources if source["char"] == record["canonical_traditional"]),
        sources[0] if sources else None,
    )
    simplified_components = _ids_components(record["external_profile"].get("chise_ids"), simplified)
    traditional_components = _ids_components(
        canonical.get("chise_ids") if canonical else None,
        canonical["char"] if canonical else simplified,
    )
    removed = [ch for ch in traditional_components if ch not in simplified_components]
    added = [ch for ch in simplified_components if ch not in traditional_components]
    shared = [ch for ch in traditional_components if ch in simplified_components]

    ocr_score = 0
    reasons = []
    if source_count >= 3:
        ocr_score += 3
        reasons.append("多繁一简来源较多")
    elif source_count == 2:
        ocr_score += 2
        reasons.append("存在两个繁体来源")
    if "多对一合并" in types:
        ocr_score += 2
        reasons.append("简化后依赖上下文区分语义")
    if any("古字复用" in t for t in types):
        ocr_score += 1
        reasons.append("简体兼用旧有字形")
    if avg_reduction >= 8:
        ocr_score += 2
        reasons.append("笔画削减幅度大")
    elif avg_reduction >= 4:
        ocr_score += 1
        reasons.append("笔画削减幅度中等")
    if removed:
        ocr_score += 1
        reasons.append("字形部件发生替换或省略")

    frequency_tier = "高频" if occurrence_count >= 200 else "中频" if occurrence_count >= 100 else "低频"
    tags = []
    if source_count >= 3:
        tags.append("多源合并")
    if any("古字复用" in t for t in types):
        tags.append("古字复用")
    if avg_reduction >= 8:
        tags.append("大幅简化")
    if frequency_tier == "高频":
        tags.append("高频用字")
    if not tags:
        tags.append("基础样本")

    return {
        "semantic_ambiguity": {
            "level": semantic_level,
            "source_count": source_count,
            "distinct_meaning_count": len(unique_meanings),
            "meanings": unique_meanings[:4],
            "note": f"该简体承接 {source_count} 个传统来源，语义区分主要依赖上下文。",
        },
        "component_shift": {
            "traditional_components": traditional_components[:8],
            "simplified_components": simplified_components[:8],
            "removed_components": removed[:8],
            "added_components": added[:8],
            "shared_components": shared[:8],
            "change_count": len(removed) + len(added),
        },
        "ocr_risk": {
            "level": _risk_level(ocr_score),
            "score": ocr_score,
            "reasons": reasons[:4],
        },
        "frequency_profile": {
            "cc_cedict_occurrences": occurrence_count,
            "rank_in_database": frequency_rank,
            "tier": frequency_tier,
        },
        "stroke_profile": {
            "average_reduction": avg_reduction,
            "max_reduction": max(reductions) if reductions else 0,
            "pair_count": len(reductions),
        },
        "cultural_tags": tags,
    }


def _generate_auto_note(
    simplified: str,
    sources: list[str],
    source_records: list[dict[str, Any]],
) -> str:
    """Generate a character-specific note for an auto_external record."""
    is_reused = simplified in sources
    other_sources = [s for s in sources if s != simplified]

    # Build a brief per-source description using Unihan definitions
    rec_by_char = {r["char"]: r for r in source_records}
    descs: list[str] = []
    for src in sources[:4]:
        rec = rec_by_char.get(src, {})
        meaning = _brief_meaning(rec)
        descs.append(f"「{src}」" + (f"（{meaning}）" if meaning else ""))

    others_str = "、".join(f"「{s}」" for s in other_sources[:3])
    descs_str = "、".join(descs)

    if is_reused:
        return (
            f"「{simplified}」本身即传统字形之一，"
            f"1956 年简化方案将其与 {others_str} 归并为同一字形。"
            f"各来源原有独立语义：{descs_str}。语义区分今依赖上下文。"
        )
    return (
        f"「{simplified}」由 {descs_str} 合并简化而来，"
        f"共 {len(sources)} 个繁体来源。各来源原有独立语义，简化后统一写作「{simplified}」，"
        "历史演化时间线待人工补写。"
    )


def choose_canonical_traditional(
    simplified: str,
    candidates: list[str],
    unihan: dict[str, dict[str, str]] | None = None,
) -> str:
    # Prefer the first candidate that is not the simplified char itself.
    # When OpenCC lists the simplified form first (e.g. 系→[系,係,繫]),
    # picking it as canonical_traditional is misleading.
    for candidate in candidates:
        if candidate != simplified:
            return candidate
    # All candidates are the simplified char — fall back to Unihan kTraditionalVariant.
    if unihan:
        for trad in value_chars(unihan.get(simplified, {}).get("kTraditionalVariant")):
            if trad != simplified:
                return trad
    return candidates[0]


def build_auto_external_record(
    candidate: dict[str, Any],
    unihan: dict[str, dict[str, str]],
    opencc_st: dict[str, list[str]],
    opencc_ts: dict[str, list[str]],
    cedict_entries: list[dict[str, str]],
    cedict_pairs: Counter,
    cedict_trad: Counter,
    cedict_simp: Counter,
    chise: dict[str, dict[str, str]],
) -> dict[str, Any]:
    simplified = candidate["simplified"]
    sources = candidate["quality_candidates"]
    canonical = choose_canonical_traditional(simplified, sources, unihan)
    source_records = [
        build_traditional_source(
            source,
            simplified,
            {"simplified": simplified, "traditional": canonical, "merges": sources},
            unihan,
            opencc_st,
            opencc_ts,
            cedict_entries,
            cedict_pairs,
            chise,
        )
        for source in sources
    ]
    return {
        "id": f"relumine-{char_codepoint(simplified).lower().replace('+', '')}",
        "curation_level": "auto_external",
        "simplified": simplified,
        "codepoint": char_codepoint(simplified),
        "record_type": "multi_source_merge",
        "pinyin": unihan.get(simplified, {}).get("kMandarin"),
        "canonical_traditional": canonical,
        "simplification_types": ["多对一合并", "待人工考据"],
        "project_interpretation": {
            "stages": [],
            "merges": sources,
            "notes": _generate_auto_note(simplified, sources, source_records),
            "extensions": {
                "selection_reason": "OpenCC 多候选映射 + CC-CEDICT 词级证据",
                "cc_cedict_pair_evidence": int(candidate["cc_cedict_pair_evidence"]),
                "example_pairs": candidate["example_pairs"],
                "opencc_all_candidates": candidate["candidates"],
                "excluded_sources": candidate["excluded_candidates"],
                "requires_historical_review": True,
            },
        },
        "external_profile": {
            "unihan": unihan_profile(simplified, unihan),
            "chise_ids": chise.get(simplified, {}).get("ids"),
            "opencc_simplified_to_traditional": opencc_st.get(simplified, []),
            "cc_cedict_as_simplified_occurrences": int(cedict_simp.get(simplified, 0)),
            "cc_cedict_as_traditional_occurrences": int(cedict_trad.get(simplified, 0)),
        },
        "traditional_sources": source_records,
        "coverage": {
            "has_unihan": simplified in unihan,
            "has_chise_ids": simplified in chise,
            "has_opencc_mapping": bool(opencc_st.get(simplified) or any(opencc_ts.get(source) for source in sources)),
            "has_cedict_evidence": any(item["cc_cedict"]["aligned_pair_count"] > 0 for item in source_records),
        },
    }


def build_database() -> dict[str, Any]:
    project = load_project_data()
    unihan = load_unihan()
    opencc_st = parse_opencc_dict(RAW_DIR / "opencc_STCharacters.txt")
    opencc_ts = parse_opencc_dict(RAW_DIR / "opencc_TSCharacters.txt")
    cedict_entries, cedict_trad, cedict_simp, cedict_pairs = load_cedict()
    chise = load_chise_ids()

    records = []
    for record in project.records:
        simplified = record["simplified"]
        sources = project_source_chars(record)
        source_records = [
            build_traditional_source(
                source,
                simplified,
                record,
                unihan,
                opencc_st,
                opencc_ts,
                cedict_entries,
                cedict_pairs,
                chise,
            )
            for source in sources
        ]
        record_type = "multi_source_merge" if len(sources) > 1 else "one_to_one_or_single_source"
        records.append(
            {
                "id": f"relumine-{char_codepoint(simplified).lower().replace('+', '')}",
                "curation_level": "handcrafted",
                "simplified": simplified,
                "codepoint": char_codepoint(simplified),
                "record_type": record_type,
                "pinyin": record.get("pinyin"),
                "canonical_traditional": record.get("traditional"),
                "simplification_types": infer_simplification_types(record),
                "project_interpretation": {
                    "stages": record.get("stages", []),
                    "merges": record.get("merges", []),
                    "notes": record.get("notes"),
                    "extensions": record.get("extensions", {}),
                },
                "external_profile": {
                    "unihan": unihan_profile(simplified, unihan),
                    "chise_ids": chise.get(simplified, {}).get("ids"),
                    "opencc_simplified_to_traditional": opencc_st.get(simplified, []),
                    "cc_cedict_as_simplified_occurrences": int(cedict_simp.get(simplified, 0)),
                    "cc_cedict_as_traditional_occurrences": int(cedict_trad.get(simplified, 0)),
                },
                "traditional_sources": source_records,
                "coverage": {
                    "has_unihan": simplified in unihan,
                    "has_chise_ids": simplified in chise,
                    "has_opencc_mapping": bool(opencc_st.get(simplified) or any(opencc_ts.get(source) for source in sources)),
                    "has_cedict_evidence": any(item["cc_cedict"]["aligned_pair_count"] > 0 for item in source_records),
                },
            }
        )

    project_simplified = {record["simplified"] for record in project.records}
    expansion_needed = max(FINAL_TARGET_RECORDS - len(records), 0)
    if expansion_needed:
        candidates = [
            row
            for row in opencc_merge_candidate_rows(opencc_st, unihan, cedict_entries, cedict_pairs, chise, project_simplified)
            if row["already_in_project"] == "no" and row["quality_gate"] == "pass"
        ]
        for candidate in candidates[:expansion_needed]:
            records.append(
                build_auto_external_record(
                    candidate,
                    unihan,
                    opencc_st,
                    opencc_ts,
                    cedict_entries,
                    cedict_pairs,
                    cedict_trad,
                    cedict_simp,
                    chise,
                )
            )

    ranked = sorted(
        records,
        key=lambda item: -int(item["external_profile"].get("cc_cedict_as_simplified_occurrences") or 0),
    )
    rank_by_char = {item["simplified"]: rank for rank, item in enumerate(ranked, 1)}
    for item in records:
        item["cultural_computation"] = build_cultural_computation(
            item,
            rank_by_char[item["simplified"]],
        )

    summary = {
        "final_target_records": FINAL_TARGET_RECORDS,
        "records": len(records),
        "handcrafted_records": sum(1 for item in records if item["curation_level"] == "handcrafted"),
        "auto_external_records": sum(1 for item in records if item["curation_level"] == "auto_external"),
        "multi_source_records": sum(1 for item in records if item["record_type"] == "multi_source_merge"),
        "traditional_source_pairs": sum(len(item["traditional_sources"]) for item in records),
        "records_with_unihan": sum(1 for item in records if item["coverage"]["has_unihan"]),
        "records_with_chise_ids": sum(1 for item in records if item["coverage"]["has_chise_ids"]),
        "records_with_opencc_mapping": sum(1 for item in records if item["coverage"]["has_opencc_mapping"]),
        "records_with_cedict_evidence": sum(1 for item in records if item["coverage"]["has_cedict_evidence"]),
        "records_passing_quality_gate": sum(
            1
            for item in records
            if item["coverage"]["has_unihan"]
            and item["coverage"]["has_chise_ids"]
            and item["coverage"]["has_opencc_mapping"]
            and item["coverage"]["has_cedict_evidence"]
        ),
    }

    return {
        "schema_version": "relumine-char-db-v1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "description": "Relumine 自建汉字数据库 v1：以项目字形流变记录为核心，融合 Unihan、OpenCC、CC-CEDICT 和 CHISE IDS 的可计算字段；当前为 100 字目标版。",
        "source_files": {
            "project_evolution": "apps/api/ocrforge_web/data/evolution.json",
            "unihan": "analysis/hanzi_databases/raw/Unihan.zip",
            "opencc_st": "analysis/hanzi_databases/raw/opencc_STCharacters.txt",
            "opencc_ts": "analysis/hanzi_databases/raw/opencc_TSCharacters.txt",
            "cc_cedict": "analysis/hanzi_databases/raw/cc_cedict.zip",
            "chise_ids": "analysis/hanzi_databases/raw/chise_ids",
        },
        "source_urls": SOURCE_URLS,
        "summary": summary,
        "characters": records,
    }


def write_summary(database: dict[str, Any]) -> None:
    rows = []
    for item in database["characters"]:
        rows.append(
            {
                "simplified": item["simplified"],
                "curation_level": item["curation_level"],
                "canonical_traditional": item["canonical_traditional"],
                "record_type": item["record_type"],
                "simplification_types": ";".join(item["simplification_types"]),
                "source_count": len(item["traditional_sources"]),
                "traditional_sources": " ".join(source["char"] for source in item["traditional_sources"]),
                "has_unihan": item["coverage"]["has_unihan"],
                "has_chise_ids": item["coverage"]["has_chise_ids"],
                "has_opencc_mapping": item["coverage"]["has_opencc_mapping"],
                "has_cedict_evidence": item["coverage"]["has_cedict_evidence"],
                "quality_gate": (
                    "pass"
                    if item["coverage"]["has_unihan"]
                    and item["coverage"]["has_chise_ids"]
                    and item["coverage"]["has_opencc_mapping"]
                    and item["coverage"]["has_cedict_evidence"]
                    else "review"
                ),
            }
        )
    write_csv(
        SUMMARY_PATH,
        rows,
        [
            "simplified",
            "curation_level",
            "canonical_traditional",
            "record_type",
            "simplification_types",
            "source_count",
            "traditional_sources",
            "has_unihan",
            "has_chise_ids",
            "has_opencc_mapping",
            "has_cedict_evidence",
            "quality_gate",
        ],
    )


def write_cultural_summary(database: dict[str, Any]) -> None:
    rows = []
    for item in database["characters"]:
        cultural = item["cultural_computation"]
        rows.append(
            {
                "simplified": item["simplified"],
                "canonical_traditional": item["canonical_traditional"],
                "source_count": cultural["semantic_ambiguity"]["source_count"],
                "semantic_level": cultural["semantic_ambiguity"]["level"],
                "distinct_meaning_count": cultural["semantic_ambiguity"]["distinct_meaning_count"],
                "ocr_risk_level": cultural["ocr_risk"]["level"],
                "ocr_risk_score": cultural["ocr_risk"]["score"],
                "frequency_tier": cultural["frequency_profile"]["tier"],
                "frequency_rank": cultural["frequency_profile"]["rank_in_database"],
                "cc_cedict_occurrences": cultural["frequency_profile"]["cc_cedict_occurrences"],
                "avg_stroke_reduction": cultural["stroke_profile"]["average_reduction"],
                "component_change_count": cultural["component_shift"]["change_count"],
                "cultural_tags": ";".join(cultural["cultural_tags"]),
            }
        )

    write_csv(
        CULTURAL_SUMMARY_PATH,
        rows,
        [
            "simplified",
            "canonical_traditional",
            "source_count",
            "semantic_level",
            "distinct_meaning_count",
            "ocr_risk_level",
            "ocr_risk_score",
            "frequency_tier",
            "frequency_rank",
            "cc_cedict_occurrences",
            "avg_stroke_reduction",
            "component_change_count",
            "cultural_tags",
        ],
    )


def build_opencc_merge_candidates(limit: int | None = None) -> list[dict[str, Any]]:
    unihan = load_unihan()
    opencc_st = parse_opencc_dict(RAW_DIR / "opencc_STCharacters.txt")
    cedict_entries, _cedict_trad, _cedict_simp, cedict_pairs = load_cedict()
    chise = load_chise_ids()
    project = load_project_data()
    project_simplified = {record["simplified"] for record in project.records}

    rows = opencc_merge_candidate_rows(
        opencc_st,
        unihan,
        cedict_entries,
        cedict_pairs,
        chise,
        project_simplified,
    )
    return rows if limit is None else rows[:limit]


def write_candidates() -> None:
    rows = build_opencc_merge_candidates()
    fieldnames = [
        "simplified",
        "traditional_candidates",
        "retained_traditional_candidates",
        "excluded_traditional_candidates",
        "candidate_count",
        "retained_candidate_count",
        "cc_cedict_pair_evidence",
        "source_chars_with_cedict_evidence",
        "source_chars_with_unihan",
        "source_chars_with_chise",
        "quality_gate",
        "unihan_traditional_variants",
        "has_chise_ids",
        "already_in_project",
        "example_pairs",
    ]
    write_csv(
        CANDIDATES_PATH,
        [{key: row.get(key, "") for key in fieldnames} for row in rows],
        fieldnames,
    )


def write_quality_check(database: dict[str, Any]) -> None:
    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []
    seen_chars: set[str] = set()
    duplicate_chars: list[str] = []
    missing_coverage: list[dict[str, Any]] = []
    auto_records_without_source_examples: list[str] = []

    for item in database["characters"]:
        if item["id"] in seen_ids:
            duplicate_ids.append(item["id"])
        seen_ids.add(item["id"])
        if item["simplified"] in seen_chars:
            duplicate_chars.append(item["simplified"])
        seen_chars.add(item["simplified"])

        failed = [key for key, value in item["coverage"].items() if not value]
        if failed:
            missing_coverage.append({"simplified": item["simplified"], "failed": failed})

        if item["curation_level"] == "auto_external":
            for source in item["traditional_sources"]:
                if source["cc_cedict"]["aligned_pair_count"] <= 0 or not source["cc_cedict"]["examples"]:
                    auto_records_without_source_examples.append(
                        f"{item['simplified']}<-{source['char']}"
                    )

    check = {
        "passed": (
            database["summary"]["records"] == FINAL_TARGET_RECORDS
            and not duplicate_ids
            and not duplicate_chars
            and not missing_coverage
            and not auto_records_without_source_examples
        ),
        "expected_records": FINAL_TARGET_RECORDS,
        "actual_records": database["summary"]["records"],
        "duplicate_ids": duplicate_ids,
        "duplicate_chars": duplicate_chars,
        "missing_coverage": missing_coverage,
        "auto_records_without_source_examples": auto_records_without_source_examples,
        "summary": database["summary"],
    }
    QUALITY_CHECK_PATH.write_text(json.dumps(check, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# v2 full-universe layer: slim records for every OpenCC mapping + SQLite output
# ---------------------------------------------------------------------------

_KANGXI_RADICAL_BASE = 0x2F00


def radical_char(rs_unicode: str | None) -> str | None:
    """kRSUnicode like '90.4' or \"120'.4\" -> Kangxi radical character."""
    if not rs_unicode:
        return None
    first = str(rs_unicode).split()[0]
    num = first.split(".")[0].rstrip("'")
    if not num.isdigit():
        return None
    n = int(num)
    if 1 <= n <= 214:
        return chr(_KANGXI_RADICAL_BASE + n - 1)
    return None


def _display_tier(simplified: str, traditional: str, unihan: dict[str, dict[str, str]]) -> str:
    in_bmp = all(0x4E00 <= ord(ch) <= 0x9FFF for ch in (simplified + traditional))
    has_pinyin = bool(unihan.get(simplified, {}).get("kMandarin"))
    return "grid" if in_bmp and has_pinyin else "archive"


def build_slim_record(
    simplified: str,
    trad_candidates: list[str],
    unihan: dict[str, dict[str, str]],
    chise: dict[str, dict[str, str]],
    opencc_st: dict[str, list[str]],
    cedict_simp: Counter,
) -> dict[str, Any]:
    canonical = choose_canonical_traditional(simplified, trad_candidates, unihan)
    real_sources = [ch for ch in trad_candidates if ch != simplified]
    record_type = "multi_source_merge" if len(real_sources) > 1 else "one_to_one"
    props = unihan.get(simplified, {})
    simp_strokes = _stroke_count({"total_strokes": props.get("kTotalStrokes")})
    trad_strokes = _stroke_count({"total_strokes": unihan.get(canonical, {}).get("kTotalStrokes")})
    return {
        "id": f"relumine-{char_codepoint(simplified).lower().replace('+', '')}",
        "curation_level": "auto_slim",
        "simplified": simplified,
        "codepoint": char_codepoint(simplified),
        "record_type": record_type,
        "pinyin": props.get("kMandarin"),
        "canonical_traditional": canonical,
        "simplification_types": [],
        "external_profile": {
            "unihan": {
                "char": simplified,
                "codepoint": char_codepoint(simplified),
                "mandarin": props.get("kMandarin"),
                "definition": props.get("kDefinition"),
                "total_strokes": props.get("kTotalStrokes"),
                "radical_stroke": props.get("kRSUnicode"),
            },
            "opencc_simplified_to_traditional": trad_candidates,
            "cc_cedict_as_simplified_occurrences": int(cedict_simp.get(simplified, 0)),
        },
        "traditional_sources": [
            {"char": ch, "codepoint": char_codepoint(ch), "role": "merge_source" if ch != canonical else "canonical_traditional"}
            for ch in trad_candidates
            if ch != simplified
        ],
        "coverage": {
            "has_unihan": simplified in unihan,
            "has_chise_ids": simplified in chise,
            "has_opencc_mapping": True,
            "has_cedict_evidence": int(cedict_simp.get(simplified, 0)) > 0,
        },
        "slim": {
            "radical": radical_char(props.get("kRSUnicode")),
            "simp_strokes": simp_strokes,
            "trad_strokes": trad_strokes,
            "stroke_reduction": (trad_strokes - simp_strokes) if (trad_strokes is not None and simp_strokes is not None) else None,
            "frequency": int(cedict_simp.get(simplified, 0)),
            "display_tier": _display_tier(simplified, canonical, unihan),
        },
    }


def _normalized_record_type(record: dict[str, Any]) -> str:
    raw = record.get("record_type", "")
    return "merge" if raw == "multi_source_merge" else "one_to_one"


def build_summary_row(record: dict[str, Any], unihan: dict[str, dict[str, str]]) -> dict[str, Any]:
    simplified = record["simplified"]
    canonical = record.get("canonical_traditional") or simplified
    props = unihan.get(simplified, {})
    slim = record.get("slim") or {}
    cultural = record.get("cultural_computation") or {}
    risk = cultural.get("ocr_risk") or {}
    semantic = cultural.get("semantic_ambiguity") or {}
    stroke = cultural.get("stroke_profile") or {}
    frequency_block = cultural.get("frequency_profile") or {}

    simp_strokes = slim.get("simp_strokes")
    trad_strokes = slim.get("trad_strokes")
    if simp_strokes is None:
        simp_strokes = _stroke_count({"total_strokes": props.get("kTotalStrokes")})
    if trad_strokes is None:
        trad_strokes = _stroke_count({"total_strokes": unihan.get(canonical, {}).get("kTotalStrokes")})

    frequency = slim.get("frequency")
    if frequency is None:
        frequency = int((record.get("external_profile") or {}).get("cc_cedict_as_simplified_occurrences") or 0)
    frequency_tier = frequency_block.get("tier") or ("高频" if frequency >= 200 else "中频" if frequency >= 100 else "低频")

    coverage = record.get("coverage") or {}
    return {
        "simplified": simplified,
        "traditional": canonical,
        "pinyin": record.get("pinyin"),
        "record_type": _normalized_record_type(record),
        "curation_level": record.get("curation_level"),
        "radical": slim.get("radical") or radical_char(props.get("kRSUnicode")),
        "simp_strokes": simp_strokes,
        "trad_strokes": trad_strokes,
        "stroke_reduction": slim.get("stroke_reduction")
        if slim.get("stroke_reduction") is not None
        else ((trad_strokes - simp_strokes) if (trad_strokes is not None and simp_strokes is not None) else None),
        "frequency": frequency,
        "frequency_tier": frequency_tier,
        "display_tier": slim.get("display_tier") or "grid",
        "ocr_risk_level": risk.get("level"),
        "ocr_risk_score": risk.get("score"),
        "semantic_level": semantic.get("level"),
        "avg_stroke_reduction": stroke.get("average_reduction"),
        "coverage_count": sum(1 for value in coverage.values() if value),
        "merges": " ".join(source["char"] for source in record.get("traditional_sources") or [] if source.get("char")),
    }


def build_full_universe(
    full_records: list[dict[str, Any]],
    unihan: dict[str, dict[str, str]],
    opencc_st: dict[str, list[str]],
    opencc_ts: dict[str, list[str]],
    chise: dict[str, dict[str, str]],
    cedict_simp: Counter,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (slim_records, summary_rows) covering every OpenCC mapping."""
    covered = {record["simplified"] for record in full_records}

    ts_inverted: dict[str, list[str]] = {}
    for traditional, simps in opencc_ts.items():
        if len(traditional) != 1 or not is_han(traditional):
            continue
        for simp in simps:
            if len(simp) == 1 and is_han(simp):
                ts_inverted.setdefault(simp, []).append(traditional)

    universe: dict[str, list[str]] = {}
    for simplified, candidates in opencc_st.items():
        if len(simplified) != 1 or not is_han(simplified):
            continue
        han = [ch for ch in candidates if len(ch) == 1 and is_han(ch)]
        if han:
            universe[simplified] = han
    for simplified, trads in ts_inverted.items():
        merged = universe.setdefault(simplified, [])
        for ch in trads:
            if ch not in merged:
                merged.append(ch)

    slim_records = [
        build_slim_record(simplified, trads, unihan, chise, opencc_st, cedict_simp)
        for simplified, trads in sorted(universe.items(), key=lambda kv: ord(kv[0]))
        if simplified not in covered and trads
    ]

    summary_rows = [build_summary_row(record, unihan) for record in full_records]
    summary_rows.extend(build_summary_row(record, unihan) for record in slim_records)
    return slim_records, summary_rows


def build_stats(summary_rows: list[dict[str, Any]], full_records: list[dict[str, Any]]) -> dict[str, Any]:
    def bucket_label(value: int | None) -> str:
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

    radical_counter: Counter = Counter()
    reduction_counter: Counter = Counter()
    tier_counter: Counter = Counter()
    for row in summary_rows:
        if row["display_tier"] == "grid":
            radical_counter[row["radical"] or "未知"] += 1
            reduction_counter[bucket_label(row["stroke_reduction"])] += 1
            tier_counter[row["frequency_tier"]] += 1

    reductions = [row["stroke_reduction"] for row in summary_rows if row["stroke_reduction"] is not None]
    return {
        "total": len(summary_rows),
        "grid_count": sum(1 for row in summary_rows if row["display_tier"] == "grid"),
        "archive_count": sum(1 for row in summary_rows if row["display_tier"] == "archive"),
        "merge_count": sum(1 for row in summary_rows if row["record_type"] == "merge"),
        "one_to_one_count": sum(1 for row in summary_rows if row["record_type"] == "one_to_one"),
        "handcrafted_count": sum(1 for row in summary_rows if row["curation_level"] == "handcrafted"),
        "auto_external_count": sum(1 for row in summary_rows if row["curation_level"] == "auto_external"),
        "auto_slim_count": sum(1 for row in summary_rows if row["curation_level"] == "auto_slim"),
        "high_ocr_risk_count": sum(1 for row in summary_rows if row["ocr_risk_level"] == "高"),
        "high_semantic_count": sum(1 for row in summary_rows if row["semantic_level"] == "高"),
        "high_frequency_count": sum(1 for row in summary_rows if row["frequency_tier"] == "高频"),
        "avg_stroke_reduction": round(sum(reductions) / len(reductions), 2) if reductions else 0,
        "radical_groups": [
            {"radical": radical, "count": count}
            for radical, count in sorted(radical_counter.items(), key=lambda kv: (kv[0] == "未知", kv[0]))
        ],
        "stroke_reduction_buckets": dict(reduction_counter),
        "frequency_tiers": dict(tier_counter),
    }


def write_sqlite(
    full_records: list[dict[str, Any]],
    slim_records: list[dict[str, Any]],
    summary_rows: list[dict[str, Any]],
    stats: dict[str, Any],
) -> None:
    import sqlite3

    SQLITE_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(SQLITE_PATH)
    try:
        conn.executescript(
            """
            CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE char_summary (
                simplified TEXT PRIMARY KEY,
                traditional TEXT NOT NULL,
                pinyin TEXT,
                record_type TEXT NOT NULL,
                curation_level TEXT NOT NULL,
                radical TEXT,
                simp_strokes INTEGER,
                trad_strokes INTEGER,
                stroke_reduction INTEGER,
                frequency INTEGER NOT NULL DEFAULT 0,
                frequency_tier TEXT,
                display_tier TEXT NOT NULL,
                ocr_risk_level TEXT,
                ocr_risk_score INTEGER,
                semantic_level TEXT,
                avg_stroke_reduction REAL,
                coverage_count INTEGER NOT NULL DEFAULT 0,
                merges TEXT,
                sort_order INTEGER NOT NULL
            );
            CREATE INDEX idx_summary_type ON char_summary(record_type);
            CREATE INDEX idx_summary_tier ON char_summary(display_tier);
            CREATE TABLE char_detail (
                simplified TEXT PRIMARY KEY,
                record_json TEXT NOT NULL
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO char_summary (
                simplified, traditional, pinyin, record_type, curation_level, radical,
                simp_strokes, trad_strokes, stroke_reduction, frequency, frequency_tier,
                display_tier, ocr_risk_level, ocr_risk_score, semantic_level,
                avg_stroke_reduction, coverage_count, merges, sort_order
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    row["simplified"], row["traditional"], row["pinyin"], row["record_type"],
                    row["curation_level"], row["radical"], row["simp_strokes"], row["trad_strokes"],
                    row["stroke_reduction"], row["frequency"], row["frequency_tier"], row["display_tier"],
                    row["ocr_risk_level"], row["ocr_risk_score"], row["semantic_level"],
                    row["avg_stroke_reduction"], row["coverage_count"], row["merges"], index,
                )
                for index, row in enumerate(summary_rows)
            ],
        )
        conn.executemany(
            "INSERT INTO char_detail (simplified, record_json) VALUES (?, ?)",
            [
                (record["simplified"], json.dumps(record, ensure_ascii=False))
                for record in full_records + slim_records
            ],
        )
        conn.execute(
            "INSERT INTO meta (key, value) VALUES ('stats', ?)",
            (json.dumps(stats, ensure_ascii=False),),
        )
        conn.commit()
    finally:
        conn.close()


def write_v2(database: dict[str, Any]) -> dict[str, Any]:
    project = load_project_data()
    unihan = load_unihan()
    opencc_st = parse_opencc_dict(RAW_DIR / "opencc_STCharacters.txt")
    opencc_ts = parse_opencc_dict(RAW_DIR / "opencc_TSCharacters.txt")
    _entries, _trad, cedict_simp, _pairs = load_cedict()
    chise = load_chise_ids()
    del project  # full records come from the already-built v1 database

    full_records = database["characters"]
    slim_records, summary_rows = build_full_universe(
        full_records, unihan, opencc_st, opencc_ts, chise, cedict_simp
    )
    stats = build_stats(summary_rows, full_records)

    v2 = {
        "schema_version": "relumine-char-db-v2",
        "generated_at": database["generated_at"],
        "description": "Relumine 汉字数据库 v2：满配层（精修 + 多对一文化计算）+ 全量瘦记录层（OpenCC 全部繁简映射）。",
        "stats": stats,
        "characters": full_records,
        "slim_characters": slim_records,
    }
    DATABASE_V2_PATH.write_text(json.dumps(v2, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_sqlite(full_records, slim_records, summary_rows, stats)
    return stats


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    database = build_database()
    DATABASE_PATH.write_text(json.dumps(database, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_summary(database)
    write_cultural_summary(database)
    write_candidates()
    write_quality_check(database)
    v2_stats = write_v2(database)
    print(
        json.dumps(
            {
                "database": str(DATABASE_PATH.relative_to(REPO_ROOT)),
                "database_v2": str(DATABASE_V2_PATH.relative_to(REPO_ROOT)),
                "sqlite": str(SQLITE_PATH.relative_to(REPO_ROOT)),
                "v2_stats": {k: v for k, v in v2_stats.items() if not isinstance(v, (list, dict))},
                "summary": database["summary"],
                "summary_csv": str(SUMMARY_PATH.relative_to(REPO_ROOT)),
                "cultural_summary_csv": str(CULTURAL_SUMMARY_PATH.relative_to(REPO_ROOT)),
                "candidates_csv": str(CANDIDATES_PATH.relative_to(REPO_ROOT)),
                "quality_check": str(QUALITY_CHECK_PATH.relative_to(REPO_ROOT)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
