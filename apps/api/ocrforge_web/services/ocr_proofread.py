from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from functools import lru_cache
from pathlib import Path
from typing import Any

from ocrforge_web.schemas import (
    ProofreadCandidate,
    ProofreadResult,
    ProofreadRisk,
)
from ocrforge_web.settings import Settings

logger = logging.getLogger("ocrforge_web.ocr_proofread")

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
_INDEX_PATH = _DATA_DIR / "confusable_index.v1.json"
_CL_ANALYSIS_PATH = _DATA_DIR / "cl_analysis.v1.json"  # 回退（旧 top_pairs）

_SNIPPET_RADIUS = 6        # 片段上下文半径（码点）
_MAX_CANDIDATES = 8        # 每个风险字最多附几个候选
_DEFAULT_THRESHOLD = 0.90  # OCR 置信度低于此 → 选为待校对
_MAX_RISKS = 60            # 单页最多标多少个待校对字（取置信度最低的）


@lru_cache(maxsize=1)
def _confusable_index() -> dict[str, list[str]]:
    """加载「字 → 形近字 top-N」全量索引（confusable_index.v1.json）。

    索引按繁体字形建（古籍 OCR 即繁体），由
    analysis/hanzi_databases/scripts/build_confusable_index.py 离线构建。
    缺失时回退到 cl_analysis 的 top_pairs（仅百余字）。
    """
    if _INDEX_PATH.exists():
        try:
            payload = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
            idx = payload.get("index")
            if isinstance(idx, dict):
                return {
                    ch: [c for c in cands if isinstance(c, str) and len(c) == 1]
                    for ch, cands in idx.items()
                    if isinstance(cands, list)
                }
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("读取形近字索引失败，回退 top_pairs: %s", exc)

    # 回退：cl_analysis.v1.json 的 ocr_confusion.top_pairs
    if not _CL_ANALYSIS_PATH.exists():
        logger.warning("形近字索引与 cl_analysis 均缺失，形近候选为空")
        return {}
    try:
        payload = json.loads(_CL_ANALYSIS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    pairs = (payload.get("ocr_confusion") or {}).get("top_pairs") or []
    index: dict[str, dict[str, None]] = {}

    def _link(x: str | None, y: str | None) -> None:
        if not x or not y or x == y or len(x) != 1 or len(y) != 1:
            return
        index.setdefault(x, {}).setdefault(y, None)
        index.setdefault(y, {}).setdefault(x, None)

    for pair in pairs:
        if isinstance(pair, dict):
            _link(pair.get("a"), pair.get("b"))
    return {ch: list(v.keys()) for ch, v in index.items()}


def confusable_twins(ch: str) -> list[str]:
    return _confusable_index().get(ch, [])


def index_info() -> dict[str, Any]:
    idx = _confusable_index()
    source = _INDEX_PATH.name if _INDEX_PATH.exists() else _CL_ANALYSIS_PATH.name
    return {"confusable_chars": len(idx), "source": source}


_RANK_SYSTEM_PROMPT = """你是资深古籍 OCR 校对助手。下面给你一段 OCR 识别文本，以及若干「OCR 把握不高的字」——
每一项含：该字、它所在的原文片段、一组候选字（来自 OCR 次优读法与部件形近字）。

你的唯一任务：对**每一项的候选字**，按它放回该上下文是否通顺合理，从高到低**重新排序**。
- 只能对给定候选排序，可以剔除明显不合的；**不得新增候选，不得新增或删除待校对的字**。
- 判断结合文义、固定搭配、人名地名书名；拿不准就保留原顺序。

只输出一个 JSON 对象，不要 Markdown，不要解释：
{"rankings":[{"id":<项目id整数>,"ranked":["最可能的字","次之","..."]}]}
ranked 里的字必须来自该项给定的候选；可只保留你认为靠谱的几个。"""


class OcrProofreadClient:
    """OCR 上下文校对：选字纯靠 OCR 逐字置信度，候选来自形近字库 + OCR 次优读法，
    DeepSeek（若配置）仅用来按上下文给候选排序——不参与选字、不新增候选。
    """

    def __init__(self, settings: Settings):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout
        self.max_tokens = settings.llm_max_tokens
        self.threshold = float(
            getattr(settings, "proofread_conf_threshold", _DEFAULT_THRESHOLD)
        )

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def proofread(
        self,
        text: str,
        char_confidences: list[float] | None = None,
        ocr_candidates: dict[str, list[str]] | None = None,
    ) -> ProofreadResult:
        text = text.replace("\r\n", "\n")
        chars = list(text)
        # 置信度必须与码点逐一对齐，长度不符则视为不可用。
        confs = char_confidences if (
            char_confidences and len(char_confidences) == len(chars)
        ) else None
        ocr_cands = _normalize_ocr_candidates(ocr_candidates, len(chars))

        if confs is None:
            return ProofreadResult(
                text=text,
                risks=[],
                model=self.model,
                note="本后端未提供逐字置信度，无法按置信度校对；请用本地 PaddleOCR-VL 识读后再校对。",
            )

        # 选字：OCR 置信度 < 阈值的字（取最低的若干个，防止整页刷屏）
        flagged = _select_positions(confs, self.threshold, _MAX_RISKS)

        items: list[dict[str, Any]] = []
        for pos in flagged:
            ch = chars[pos]
            items.append({
                "pos": pos,
                "char": ch,
                "snippet": _window(chars, pos),
                "candidates": _candidates_for(ch, ocr_cands.get(pos)),
            })

        # DeepSeek 排候选（可选；失败/未配置则保留 OCR+形近 原序）
        if self.configured and items:
            ranking = self._rank(text, items)
            if ranking:
                for it in items:
                    order = ranking.get(it["pos"])
                    if order:
                        it["candidates"] = _reorder(it["candidates"], order)

        risks = [
            ProofreadRisk(
                position=it["pos"],
                original=it["char"],
                snippet=it["snippet"],
                candidates=it["candidates"],
                confidence=round(1.0 - confs[it["pos"]], 2),
                ocr_confidence=confs[it["pos"]],
                reason="OCR 模型对此字把握较低（%.0f%%），结合形近字给出候选供核对。"
                % (confs[it["pos"]] * 100),
                category="低置信",
            )
            for it in items
        ]
        return ProofreadResult(text=text, risks=risks, model=self.model, note=None)

    def _rank(self, text: str, items: list[dict[str, Any]]) -> dict[int, list[str]] | None:
        payload_items = [
            {
                "id": it["pos"],
                "snippet": it["snippet"],
                "char": it["char"],
                "candidates": [c.char for c in it["candidates"]],
            }
            for it in items
            if it["candidates"]
        ]
        if not payload_items:
            return None
        user = (
            "原文：\n" + text + "\n\n待排序项（JSON 数组）：\n"
            + json.dumps(payload_items, ensure_ascii=False)
        )
        try:
            parsed = self._chat_json(_RANK_SYSTEM_PROMPT, user)
        except RuntimeError as exc:
            logger.warning("DeepSeek 候选排序失败，保留原顺序: %s", exc)
            return None

        out: dict[int, list[str]] = {}
        rankings = parsed.get("rankings") if isinstance(parsed, dict) else None
        for r in rankings or []:
            if not isinstance(r, dict):
                continue
            try:
                pid = int(r.get("id"))
            except (TypeError, ValueError):
                continue
            ranked = [str(c).strip() for c in (r.get("ranked") or []) if str(c).strip()]
            if ranked:
                out[pid] = ranked
        return out or None

    def _chat_json(self, system: str, user: str) -> Any:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.0,
            "max_tokens": self.max_tokens,
            "stream": False,
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        for attempt in range(2):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    raw: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                logger.warning("DeepSeek HTTP %s: %s", exc.code, detail[:500])
                raise RuntimeError(f"DeepSeek API returned HTTP {exc.code}") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"cannot reach DeepSeek API: {exc.reason}") from exc
            try:
                content = raw["choices"][0]["message"]["content"] or ""
                return json.loads(_strip_code_fence(content))
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                finish_reason, content_length = _choice_diagnostics(raw)
                logger.warning(
                    "DeepSeek 排序返回无法解析: %s (finish_reason=%s, content_length=%s, attempt=%s)",
                    exc, finish_reason, content_length, attempt + 1,
                )
                if attempt == 0:
                    continue
                raise RuntimeError("DeepSeek returned an invalid structured response") from exc


def _select_positions(confs: list[float], threshold: float, cap: int) -> list[int]:
    """选出置信度 < 阈值的位置；超过 cap 时取置信度最低的若干个，最终按位置排序。"""
    flagged = [(i, c) for i, c in enumerate(confs) if c < threshold]
    if len(flagged) > cap:
        flagged.sort(key=lambda ic: ic[1])  # 置信度升序，取最低的
        flagged = flagged[:cap]
    return sorted(i for i, _ in flagged)


def _candidates_for(ch: str, ocr_cands: list[str] | None) -> list[ProofreadCandidate]:
    """候选 = OCR 次优读法（强证据，靠前）+ 形近字库 top-N，去重去自身，封顶。"""
    twins = confusable_twins(ch)
    ocr_set = set(ocr_cands or [])
    ordered: list[str] = []
    seen: set[str] = set()

    def _push(c: str) -> None:
        c = (c or "").strip()
        if len(c) == 1 and c != ch and c != "�" and c not in seen:
            ordered.append(c)
            seen.add(c)

    for c in ocr_cands or []:
        _push(c)
    for c in twins:
        _push(c)

    ordered = ordered[:_MAX_CANDIDATES]
    return [
        ProofreadCandidate(char=c, source="ocr" if c in ocr_set else "confusable")
        for c in ordered
    ]


def _reorder(
    candidates: list[ProofreadCandidate], order: list[str]
) -> list[ProofreadCandidate]:
    """按 DeepSeek 给的 order 重排候选；order 里没提到的接在后面（不丢候选）。"""
    by_char = {c.char: c for c in candidates}
    ranked = [by_char[c] for c in order if c in by_char]
    used = {c for c in order if c in by_char}
    rest = [c for c in candidates if c.char not in used]
    return ranked + rest


def _window(chars: list[str], pos: int) -> str:
    return "".join(chars[max(0, pos - _SNIPPET_RADIUS): pos + _SNIPPET_RADIUS + 1])


def _normalize_ocr_candidates(
    ocr_candidates: dict[str, list[str]] | None, n: int
) -> dict[int, list[str]]:
    """{位置字符串: [候选…]} → {int 位置: [干净单字…]}，越界/非法的丢弃。"""
    out: dict[int, list[str]] = {}
    if not isinstance(ocr_candidates, dict):
        return out
    for key, value in ocr_candidates.items():
        try:
            pos = int(key)
        except (TypeError, ValueError):
            continue
        if not (0 <= pos < n) or not isinstance(value, list):
            continue
        cands = [str(c).strip() for c in value if len(str(c).strip()) == 1]
        if cands:
            out[pos] = cands
    return out


def _strip_code_fence(content: str) -> str:
    value = content.strip()
    if value.startswith("```"):
        lines = value.splitlines()
        value = "\n".join(lines[1:-1])
    return value.strip()


def _choice_diagnostics(raw: dict[str, Any]) -> tuple[str | None, int | None]:
    try:
        choice = raw["choices"][0]
        content = choice.get("message", {}).get("content") or ""
        return choice.get("finish_reason"), len(content)
    except Exception:  # noqa: BLE001 - diagnostics must never mask root cause
        return None, None
