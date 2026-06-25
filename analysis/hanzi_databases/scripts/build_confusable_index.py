"""离线构建「全量形近字索引」：每个字 → 最像它的 top-N 个字（OCR 易混候选）。

复用 full_universe_cl_analysis.py 里那套 CHISE IDS 结构相似度（共享部件 + IDS 编辑距离，
相似度 ≥0.6、笔画差 ≤2），但**不截断**——对全字表算完再按字取 top-N，落成运行时产物
`apps/api/ocrforge_web/data/confusable_index.v1.json`，供 OCR 校对挑候选。

依赖原始 dump（CHISE / Unihan，放在 raw/，忽略提交），产物随仓库提交。重建：
    pixi run python analysis/hanzi_databases/scripts/build_confusable_index.py
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from analyze_external_databases import REPO_ROOT, load_chise_ids, load_unihan  # noqa: E402

V2_PATH = REPO_ROOT / "apps" / "api" / "ocrforge_web" / "data" / "relumine_char_db.v2.json"
OUT_PATH = REPO_ROOT / "apps" / "api" / "ocrforge_web" / "data" / "confusable_index.v1.json"

_IDS_OPS = set("⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻")

SIM_MIN = 0.6        # 相似度阈值（同 full_universe_cl_analysis）
STROKE_MAX_DIFF = 2  # 笔画差阈值
TOP_N = 10           # 每字保留候选数
CURATED_SIM = 0.9    # 人工原子形近组的相似度（排在部件家族噪声之上）

# 人工补充：部件法覆盖不到的「原子字」形近组（无 IDS 分解、靠笔画微差区分）。
# 古籍 OCR 输出为繁体，故用繁体形；多数原子字繁简同形，繁简有别者两形都列。
# 每组内两两互为形近候选。
CURATED_GROUPS = [
    "己已巳", "戊戌戍戎", "土士", "未末", "日曰目", "曰日月",
    "大太犬夨夫天", "人入", "八入", "干千", "于干", "刀力刁",
    "王玉壬主", "戈弋戔", "田由甲申", "木朮", "本木", "末未",
    "失矢失", "史吏", "比北", "母毋毌", "卯卬", "厂广", "几凡",
    "卜卞", "夭天", "牛午", "句勾旬", "貝見", "見貝目自", "烏鳥焉",
    "鳥烏", "魚黑", "辰辱", "戍戌", "刺剌", "刺棘", "栗粟",
    "侯候", "微徵徽", "卷券", "辨辯辦瓣辧", "拆折", "曰白",
    "氏民氐", "戊戎", "亥豕", "千于干", "毋母", "巳已己",
    "甲申由田", "玉王", "丸凡", "刃刀", "乇千", "夬央夫",
]


def _merge_curated(link) -> None:
    for group in CURATED_GROUPS:
        chars = list(dict.fromkeys(group))  # 去重保序
        for i in range(len(chars)):
            for j in range(i + 1, len(chars)):
                link(chars[i], chars[j], CURATED_SIM)


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

    # ── 字形宇宙：网格里出现的繁体字（规范繁 + 合并来源）+ 各自简体 ──
    glyphs: set[str] = set()
    glyph_to_simp: dict[str, str] = {}
    for record in full_records + slim_records:
        simplified = record["simplified"]
        cands = [record.get("canonical_traditional") or simplified] + [
            item["char"]
            for item in record.get("traditional_sources") or []
            if item.get("char")
        ]
        for ch in cands:
            if ch and ch not in glyphs:
                glyphs.add(ch)
                glyph_to_simp[ch] = simplified

    ids_of = {
        ch: chise[ch]["ids"]
        for ch in glyphs
        if ch in chise and len(chise[ch]["ids"]) >= 3
    }

    def components(ids: str, self_char: str) -> list[str]:
        return [ch for ch in ids if ch != self_char and ch not in _IDS_OPS and ord(ch) >= 0x2E80]

    # 候选对：共享部件 + 笔画接近
    by_component: dict[str, list[str]] = defaultdict(list)
    for ch, ids in ids_of.items():
        for comp in set(components(ids, ch)):
            by_component[comp].append(ch)

    # links[x] = {cand: best_similarity}
    links: dict[str, dict[str, float]] = defaultdict(dict)

    def link(x: str, y: str, sim: float) -> None:
        if not x or not y or x == y or len(x) != 1 or len(y) != 1:
            return
        if links[x].get(y, -1.0) < sim:
            links[x][y] = sim
        if links[y].get(x, -1.0) < sim:
            links[y][x] = sim

    seen_pairs: set[tuple[str, str]] = set()
    pair_count = 0
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
                if sa is None or sb is None or abs(sa - sb) > STROKE_MAX_DIFF:
                    continue
                ids_a, ids_b = ids_of[a], ids_of[b]
                max_len = max(len(ids_a), len(ids_b))
                cap = max(2, int(max_len * 0.45))
                dist = levenshtein(ids_a, ids_b, cap)
                if dist > cap:
                    continue
                similarity = round(1 - dist / max_len, 3)
                if similarity < SIM_MIN:
                    continue
                pair_count += 1
                # 只按繁体字形建（古籍 OCR 即繁体）。不做简体投影——简化常削掉共享
                # 部件，繁体形近的字简化后未必形近（如 慄/憐 形近，但简体 栗/怜 毫不像）。
                link(a, b, similarity)

    # 人工原子形近组（部件法盲区）合并进来
    _merge_curated(link)

    # 每字按相似度降序取 top-N（同分按字稳定排序）
    index = {
        ch: [c for c, _ in sorted(cands.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_N]]
        for ch, cands in links.items()
    }
    index = {ch: cands for ch, cands in index.items() if cands}

    payload = {
        "schema_version": "relumine-confusable-index-v1",
        "generated_from": "relumine_char_db.v2.json + CHISE IDS + Unihan strokes",
        "method": "CHISE IDS 结构编辑距离，共享部件 + 笔画差≤%d + 相似度≥%.1f，每字 top-%d"
        % (STROKE_MAX_DIFF, SIM_MIN, TOP_N),
        "pair_count": pair_count,
        "char_count": len(index),
        "index": index,
    }
    OUT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"pairs={pair_count}  chars_indexed={len(index)}  out={OUT_PATH}  ({size_kb:.0f} KB)")
    # 抽样
    for s in ["後", "己", "戊", "土", "未"]:
        print(f"  {s} → {index.get(s)}")


if __name__ == "__main__":
    main()
