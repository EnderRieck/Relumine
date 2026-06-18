"""Multi-source 繁→简 conversion for proper nouns (CBDB / CHGIS names).

Strategy (per the project's four 文字数据库):
  1. WORD level — greedy longest-match against CC-CEDICT traditional words.
     Whole names / place names that are dictionary entries convert as a unit,
     which fixes char-level mistakes (e.g. 錢鍾書 → 钱钟书, not 钱锺书).
  2. CHAR fallback — OpenCC t2s as the primary per-character result, validated
     against Unihan kSimplifiedVariant. Agreement raises confidence; a clash is
     flagged and the Unihan candidate(s) are offered as alternatives.
  3. CHISE IDS is attached as structural evidence to help a human disambiguate
     visually similar variants; it never changes the result.

The compact index lives at ``settings.hanzi_convert_path`` and is built offline
by ``analysis/hanzi_databases/scripts/build_convert_index.py``. If it is absent
the service still works in OpenCC-only mode (lower confidence, no evidence).
"""

from __future__ import annotations

import re
import sqlite3
import threading
from pathlib import Path

from ocrforge_web.schemas import (
    ConvertEvidence,
    ConvertSegment,
    NameConversion,
)
from ocrforge_web.services import opencc_service
from ocrforge_web.settings import get_settings

_HAN_RE = re.compile(
    "[㐀-䶿一-鿿豈-﫿"
    "\U00020000-\U0002ebef\U00030000-\U000323af]"
)


def _is_han(ch: str) -> bool:
    return bool(ch and _HAN_RE.fullmatch(ch))


class _Index:
    """Lazily-loaded in-memory snapshot of the conversion index."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._loaded = False
        self.cedict: dict[str, tuple[str, str]] = {}   # trad word -> (simp, pinyin)
        self.unihan_simp: dict[str, list[str]] = {}     # trad char -> [simp variants]
        self.chise: dict[str, str] = {}                 # char -> IDS
        self.max_word = 1
        self.meta: dict[str, str] = {}

    @property
    def file_present(self) -> bool:
        return self._path.is_file()

    def ensure(self) -> None:
        if self._loaded:
            return
        with self._lock:
            if self._loaded:
                return
            if self._path.is_file():
                con = sqlite3.connect(str(self._path))
                try:
                    cur = con.cursor()
                    self.cedict = {
                        t: (s, p or "")
                        for t, s, p in cur.execute(
                            "SELECT trad, simp, pinyin FROM cedict"
                        )
                    }
                    self.unihan_simp = {
                        t: s.split()
                        for t, s in cur.execute("SELECT trad, simp FROM unihan_simp")
                    }
                    self.chise = {
                        c: i for c, i in cur.execute("SELECT ch, ids FROM chise")
                    }
                    self.meta = {
                        k: v for k, v in cur.execute("SELECT key, value FROM meta")
                    }
                finally:
                    con.close()
                self.max_word = max(
                    (len(w) for w in self.cedict), default=1
                )
            self._loaded = True

    def info(self) -> dict:
        self.ensure()
        return {
            "index_present": self.file_present,
            "cedict_words": len(self.cedict),
            "unihan_variants": len(self.unihan_simp),
            "chise_ids": len(self.chise),
        }


_INDEX: _Index | None = None
_INDEX_LOCK = threading.Lock()


def _index() -> _Index:
    global _INDEX
    if _INDEX is None:
        with _INDEX_LOCK:
            if _INDEX is None:
                _INDEX = _Index(get_settings().hanzi_convert_path)
    _INDEX.ensure()
    return _INDEX


def _chise_evidence(idx: _Index, *chars: str) -> list[ConvertEvidence]:
    out: list[ConvertEvidence] = []
    for ch in chars:
        ids = idx.chise.get(ch)
        if ids and ids != ch:
            out.append(ConvertEvidence(source="chise", value=ids, note=f"{ch} 部件分解"))
    return out


def _convert_char(idx: _Index, ch: str) -> ConvertSegment:
    if not _is_han(ch):
        return ConvertSegment(
            traditional=ch, simplified=ch, method="identity", confidence=1.0
        )

    occ = opencc_service.t2s(ch)
    uni = idx.unihan_simp.get(ch)

    # Unchanged by OpenCC and not a known traditional char with a simplified
    # variant → it is already simplified / shared between 繁简.
    if occ == ch and not uni:
        return ConvertSegment(
            traditional=ch,
            simplified=ch,
            method="identity",
            confidence=1.0,
            sources=["opencc"],
        )

    simplified = occ
    sources = ["opencc"]
    conflict = False
    alternatives: list[str] = []
    evidence = [ConvertEvidence(source="opencc", value=occ)]
    if uni:
        evidence.append(ConvertEvidence(source="unihan", value=" ".join(uni)))
        if occ in uni:
            sources.append("unihan")
            alternatives = [c for c in uni if c != occ]
            confidence = 0.98
        else:
            conflict = True
            alternatives = uni
            confidence = 0.8
    else:
        confidence = 0.9
    evidence.extend(_chise_evidence(idx, ch))
    return ConvertSegment(
        traditional=ch,
        simplified=simplified,
        method="char",
        confidence=confidence,
        sources=sources,
        conflict=conflict,
        alternatives=alternatives,
        evidence=evidence,
    )


def _convert_word(idx: _Index, trad: str, simp: str, pinyin: str) -> ConvertSegment:
    occ = opencc_service.t2s(trad)
    agree = occ == simp
    sources = ["cc-cedict"] + (["opencc"] if agree else [])
    evidence = [
        ConvertEvidence(source="cc-cedict", value=simp, note=pinyin or None),
        ConvertEvidence(source="opencc", value=occ),
    ]
    evidence.extend(_chise_evidence(idx, *trad))
    return ConvertSegment(
        traditional=trad,
        simplified=simp,
        method="word",
        confidence=0.97 if agree else 0.9,
        sources=sources,
        conflict=not agree,
        alternatives=[] if agree else [occ],
        evidence=evidence,
    )


def convert(text: str) -> NameConversion:
    """Convert a (traditional) proper noun to simplified with source evidence."""
    idx = _index()
    text = (text or "").strip()
    if not text:
        return NameConversion(
            traditional=text, simplified=text, confidence=1.0, method="identity"
        )

    segments: list[ConvertSegment] = []
    i = 0
    n = len(text)
    while i < n:
        matched: tuple[str, str, str] | None = None
        hi = min(i + idx.max_word, n)
        # greedy longest CC-CEDICT word (len >= 2) starting at i
        for j in range(hi, i + 1, -1):
            sub = text[i:j]
            hit = idx.cedict.get(sub)
            if hit is not None:
                matched = (sub, hit[0], hit[1])
                break
        if matched is not None:
            trad_word, simp_word, pinyin = matched
            segments.append(_convert_word(idx, trad_word, simp_word, pinyin))
            i += len(trad_word)
        else:
            segments.append(_convert_char(idx, text[i]))
            i += 1

    simplified = "".join(s.simplified for s in segments)
    methods = {s.method for s in segments}
    non_identity = methods - {"identity"}
    if not non_identity:
        method = "identity"
    elif len(non_identity) == 1:
        method = next(iter(non_identity))
    else:
        method = "mixed"
    confidence = min((s.confidence for s in segments), default=1.0)
    note = None
    if not idx.file_present:
        note = "转换索引未构建，已退化为纯 OpenCC 字级转换。"
    return NameConversion(
        traditional=text,
        simplified=simplified,
        confidence=round(confidence, 3),
        method=method,
        segments=segments,
        note=note,
    )


def info() -> dict:
    return _index().info()
