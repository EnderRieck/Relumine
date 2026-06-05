from __future__ import annotations

import os
import threading
from functools import lru_cache
from pathlib import Path

import opencc

from ocrforge_web.schemas import Collision


_LOCK = threading.Lock()
_ST_MAP: dict[str, list[str]] | None = None


def _opencc_dict_dir() -> Path:
    return Path(opencc.__file__).resolve().parent / "dictionary"


def _load_st_map() -> dict[str, list[str]]:
    """Read STCharacters.txt and return {simplified: [traditional candidates]}.

    Lines look like: '后\t後 后' — i.e. one simplified char on the left, a
    space-separated list of traditional candidates on the right. Multi-candidate
    rows are exactly the multi-to-one merge collisions we want to surface.
    """
    path = _opencc_dict_dir() / "STCharacters.txt"
    table: dict[str, list[str]] = {}
    with path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line or "\t" not in line:
                continue
            simp, rhs = line.split("\t", 1)
            candidates = [c for c in rhs.split(" ") if c]
            if simp and candidates:
                table[simp] = candidates
    return table


def _get_st_map() -> dict[str, list[str]]:
    global _ST_MAP
    if _ST_MAP is None:
        with _LOCK:
            if _ST_MAP is None:
                _ST_MAP = _load_st_map()
    return _ST_MAP


@lru_cache(maxsize=2)
def _converter(profile: str) -> opencc.OpenCC:
    return opencc.OpenCC(profile)


def t2s(text: str) -> str:
    return _converter("t2s").convert(text)


def s2t(text: str) -> str:
    return _converter("s2t").convert(text)


def detect_collisions(simplified_text: str) -> list[Collision]:
    """Flag every simplified char with >1 traditional sources.

    Position is the index in `simplified_text`, so the caller can highlight in
    whichever side (input for s2t, output for t2s) is the simplified one.
    """
    table = _get_st_map()
    out: list[Collision] = []
    for i, ch in enumerate(simplified_text):
        sources = table.get(ch)
        if sources and len(sources) > 1:
            out.append(Collision(position=i, simplified=ch, source_traditionals=sources))
    return out


def warm() -> None:
    _converter("t2s")
    _converter("s2t")
    _get_st_map()
