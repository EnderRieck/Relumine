"""Build a compact runtime traditional->simplified conversion index.

Reads the (gitignored) raw external databases under
``analysis/hanzi_databases/raw`` and distils ONLY the conversion-relevant
fields into a small committed SQLite at
``apps/api/ocrforge_web/data/hanzi_convert.sqlite`` so the API never has to
parse the full Unihan / CC-CEDICT dumps at request time.

Tables produced:
  cedict(trad PK, simp, pinyin)        -- word-level pairs (len(trad) >= 2)
  unihan_simp(trad PK, simp)           -- kSimplifiedVariant chars (space-joined)
  unihan_trad(simp PK, trad)           -- kTraditionalVariant chars (space-joined)
  chise(ch PK, ids)                    -- IDS structural decomposition
  meta(key PK, value)                  -- build provenance + counts

OpenCC is intentionally NOT stored: the running service uses the opencc
package directly for char-level t2s. Run from anywhere::

    pixi run python analysis/hanzi_databases/scripts/build_convert_index.py
"""

from __future__ import annotations

import json
import re
import sqlite3
import zipfile
from collections import Counter, defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = REPO_ROOT / "analysis" / "hanzi_databases" / "raw"
OUT_PATH = REPO_ROOT / "apps" / "api" / "ocrforge_web" / "data" / "hanzi_convert.sqlite"

HAN_RE = re.compile(
    "[㐀-䶿一-鿿豈-﫿"
    "\U00020000-\U0002ebef\U00030000-\U000323af]"
)
U_CODE_RE = re.compile(r"U\+([0-9A-Fa-f]{4,6})")
CEDICT_RE = re.compile(r"^(\S+) (\S+) \[(.*?)\] /(.*)/$")


def is_han(ch: str) -> bool:
    return bool(ch and HAN_RE.fullmatch(ch))


def code_to_char(code: str) -> str:
    return chr(int(code[2:] if code.startswith("U+") else code, 16))


def variant_chars(value: str | None) -> list[str]:
    if not value:
        return []
    return [code_to_char(m.group(1)) for m in U_CODE_RE.finditer(value)]


def build_cedict() -> list[tuple[str, str, str]]:
    """trad word -> (simp word, pinyin); keep len(trad) >= 2, majority simp."""
    path = RAW_DIR / "cc_cedict.zip"
    if not path.is_file():
        print("  [warn] cc_cedict.zip 缺失，跳过 CC-CEDICT")
        return []
    simp_votes: dict[str, Counter] = defaultdict(Counter)
    pinyin_for: dict[str, str] = {}
    with zipfile.ZipFile(path) as zf:
        member = next((n for n in zf.namelist() if n.endswith(".u8")), "cedict_ts.u8")
        with zf.open(member) as raw:
            for line_bytes in raw:
                line = line_bytes.decode("utf-8").strip()
                if not line or line.startswith("#"):
                    continue
                m = CEDICT_RE.match(line)
                if not m:
                    continue
                trad, simp, pinyin, _definition = m.groups()
                if len(trad) < 2 or len(trad) != len(simp):
                    continue
                # only keep entries that are pure Han on both sides
                if not all(is_han(c) for c in trad) or not all(is_han(c) for c in simp):
                    continue
                simp_votes[trad][simp] += 1
                pinyin_for.setdefault(trad, pinyin)
    rows: list[tuple[str, str, str]] = []
    for trad, votes in simp_votes.items():
        simp = votes.most_common(1)[0][0]
        rows.append((trad, simp, pinyin_for.get(trad, "")))
    return rows


def build_unihan() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """(trad->simp variants), (simp->trad variants) from Unihan_Variants.txt."""
    path = RAW_DIR / "Unihan.zip"
    if not path.is_file():
        print("  [warn] Unihan.zip 缺失，跳过 Unihan")
        return [], []
    simp_map: dict[str, list[str]] = {}
    trad_map: dict[str, list[str]] = {}
    with zipfile.ZipFile(path) as zf:
        members = [n for n in zf.namelist() if n.endswith("Unihan_Variants.txt")]
        target = members[0] if members else None
        if target is None:
            print("  [warn] Unihan_Variants.txt 不在压缩包内，跳过 Unihan")
            return [], []
        with zf.open(target) as raw:
            for line_bytes in raw:
                line = line_bytes.decode("utf-8").strip()
                if not line or line.startswith("#") or "\t" not in line:
                    continue
                parts = line.split("\t", 2)
                if len(parts) < 3:
                    continue
                code, key, value = parts
                ch = code_to_char(code)
                if key == "kSimplifiedVariant":
                    chars = [c for c in variant_chars(value) if c != ch]
                    if chars:
                        simp_map[ch] = chars
                elif key == "kTraditionalVariant":
                    chars = [c for c in variant_chars(value) if c != ch]
                    if chars:
                        trad_map[ch] = chars
    simp_rows = [(k, " ".join(v)) for k, v in simp_map.items()]
    trad_rows = [(k, " ".join(v)) for k, v in trad_map.items()]
    return simp_rows, trad_rows


def build_chise() -> list[tuple[str, str]]:
    root = RAW_DIR / "chise_ids"
    if not root.is_dir():
        print("  [warn] chise_ids/ 缺失，跳过 CHISE IDS")
        return []
    out: dict[str, str] = {}
    for path in sorted(root.glob("IDS-UCS*.txt")):
        with path.open(encoding="utf-8", errors="replace") as f:
            for raw in f:
                line = raw.rstrip("\n")
                if not line or line.startswith(";;"):
                    continue
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                _code, ch, ids = parts[:3]
                if len(ch) == 1 and is_han(ch):
                    out.setdefault(ch, ids)
    return list(out.items())


def main() -> None:
    print("RAW_DIR:", RAW_DIR)
    cedict = build_cedict()
    unihan_simp, unihan_trad = build_unihan()
    chise = build_chise()
    print(
        f"  cedict={len(cedict)}  unihan_simp={len(unihan_simp)}  "
        f"unihan_trad={len(unihan_trad)}  chise={len(chise)}"
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.exists():
        OUT_PATH.unlink()
    con = sqlite3.connect(OUT_PATH)
    cur = con.cursor()
    cur.executescript(
        """
        CREATE TABLE cedict(trad TEXT PRIMARY KEY, simp TEXT NOT NULL, pinyin TEXT);
        CREATE TABLE unihan_simp(trad TEXT PRIMARY KEY, simp TEXT NOT NULL);
        CREATE TABLE unihan_trad(simp TEXT PRIMARY KEY, trad TEXT NOT NULL);
        CREATE TABLE chise(ch TEXT PRIMARY KEY, ids TEXT NOT NULL);
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        """
    )
    cur.executemany("INSERT OR REPLACE INTO cedict VALUES (?,?,?)", cedict)
    cur.executemany("INSERT OR REPLACE INTO unihan_simp VALUES (?,?)", unihan_simp)
    cur.executemany("INSERT OR REPLACE INTO unihan_trad VALUES (?,?)", unihan_trad)
    cur.executemany("INSERT OR REPLACE INTO chise VALUES (?,?)", chise)
    # longest CC-CEDICT word, used by the runtime greedy matcher as a window cap
    max_word = max((len(r[0]) for r in cedict), default=0)
    meta = {
        "schema": "1",
        "sources": "CC-CEDICT, Unihan(Variants), CHISE IDS; OpenCC at runtime",
        "cedict_words": str(len(cedict)),
        "unihan_simp": str(len(unihan_simp)),
        "unihan_trad": str(len(unihan_trad)),
        "chise": str(len(chise)),
        "max_cedict_word_len": str(max_word),
    }
    cur.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)", list(meta.items()))
    con.commit()
    con.close()

    size_mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"WROTE {OUT_PATH}  ({size_mb:.1f} MB)")
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
