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

_CL_ANALYSIS_PATH = Path(__file__).resolve().parents[1] / "data" / "cl_analysis.v1.json"

# 给 DeepSeek 的形近字提示里，最多列多少个文中出现的可混字（防止 prompt 过长）。
_MAX_HINT_CHARS = 60
# 单字最多附几个形近孪生候选。
_MAX_TWINS = 4
# OCR 逐字置信度阈值：低于此值视为「OCR 把握不足」，重点提示 DeepSeek 关注。
_CONF_HINT_GATE = 0.90
# 低于此值且 DeepSeek 未标的位置，单独兜底成「低置信」风险交专家过目。
_CONF_HARD_GATE = 0.60
# OCR 低置信提示里最多列多少个位置（防止 prompt 过长）。
_MAX_CONF_HINTS = 30


@lru_cache(maxsize=1)
def _confusable_index() -> dict[str, list[str]]:
    """从 cl_analysis 的 ocr_confusion.top_pairs 构建「字 → 形近字列表」。

    top_pairs 基于 CHISE 部件结构在繁体字形上算相似度（古籍 OCR 输出即繁体）。
    同时收录简体投影 a_simplified/b_simplified，对简体文本也给点候选；可靠度以繁体为主。
    返回的列表按相似度降序、去重。
    """
    if not _CL_ANALYSIS_PATH.exists():
        logger.warning("cl_analysis 不存在，形近字先验为空: %s", _CL_ANALYSIS_PATH)
        return {}
    try:
        payload = json.loads(_CL_ANALYSIS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("读取 cl_analysis 失败，形近字先验为空: %s", exc)
        return {}

    pairs = (payload.get("ocr_confusion") or {}).get("top_pairs") or []
    # 用 dict 保序去重；列表本身已按相似度降序，故先到先得即高相似优先。
    index: dict[str, dict[str, None]] = {}

    def _link(x: str | None, y: str | None) -> None:
        if not x or not y or x == y or len(x) != 1 or len(y) != 1:
            return
        index.setdefault(x, {}).setdefault(y, None)
        index.setdefault(y, {}).setdefault(x, None)

    for pair in pairs:
        if not isinstance(pair, dict):
            continue
        _link(pair.get("a"), pair.get("b"))
        _link(pair.get("a_simplified"), pair.get("b_simplified"))

    return {ch: list(twins.keys()) for ch, twins in index.items()}


def confusable_twins(ch: str) -> list[str]:
    return _confusable_index().get(ch, [])


def index_info() -> dict[str, Any]:
    idx = _confusable_index()
    return {"confusable_chars": len(idx), "source": str(_CL_ANALYSIS_PATH.name)}


_SYSTEM_PROMPT = """你是资深的中国古籍 OCR 校对专家。用户给你一段由 OCR 从古籍图像识别出的文本，
其中可能因字形相近、断笔、污损而出现「形近误识」，也可能有个别字与上下文文义、语法、
固定搭配、人名地名书名不合而显得可疑。

你的任务：找出文本中「可疑、可能被识别错」的单字，给出更可能的候选字，但绝不直接改写原文。
请保守：只标注确有依据可怀疑的字；通顺、无疑义之处不要标。

我会提供一份「形近字参考表」（基于部件结构计算，列出与文中部分字易被 OCR 混淆的字）。
优先从中为可疑字挑候选；若文义明确指向表外的字，也可给出。

我可能还会提供一份「OCR 低置信位」清单（OCR 模型自己对这些字把握就不高，并附其备选读法）。
请优先核查这些位置；但最终仍以文义为准——OCR 没把握不等于一定错，通顺也可不标。

只输出一个 JSON 对象，不要 Markdown，不要额外解释。结构：
{
  "issues": [
    {
      "snippet": "包含可疑字的一段原文，逐字照抄，约 6-16 字，必须是原文中的连续子串",
      "suspect": "可疑的那一个字（必须是单个字，且出现在 snippet 中）",
      "candidates": ["更可能的字", "..."],
      "confidence": 0.0,
      "reason": "为何可疑、为何这样改（结合上下文/字形/搭配，简短）",
      "category": "形近"
    }
  ],
  "note": "整体说明，可留空"
}

字段规则：
1. snippet 必须逐字来自原文、可被字符串检索定位；suspect 必须是 snippet 中的某一个字。
2. candidates 按可能性从高到低，给 1-4 个；是「供专家参考的建议」而非定论，不得编造生僻字凑数。
3. confidence 取 0-1，表示此处确为误识的把握。
4. category 取「形近 / 文义 / 缺漏 / 衍文 / 其他」之一。
5. 宁缺毋滥：无把握不要标，通顺处不要标。一段文本通常只有少数几个可疑字。
6. 只输出可疑点，不要输出对全文的改写。"""


class OcrProofreadClient:
    """复用 DeepSeek（settings.llm_*）做古籍 OCR 上下文校对。非流式、JSON 输出。"""

    def __init__(self, settings: Settings):
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url.rstrip("/")
        self.model = settings.llm_model
        self.timeout = settings.llm_timeout
        self.max_tokens = settings.llm_max_tokens

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def proofread(
        self,
        text: str,
        char_confidences: list[float] | None = None,
        ocr_candidates: dict[str, list[str]] | None = None,
    ) -> ProofreadResult:
        if not self.api_key:
            raise RuntimeError("DeepSeek API key is not configured")

        text = text.replace("\r\n", "\n")
        chars = list(text)
        # 置信度必须与码点逐一对齐，长度不符则视为不可用（宁可不用也不用错位的）。
        confs = char_confidences if (
            char_confidences and len(char_confidences) == len(chars)
        ) else None
        ocr_cands = _normalize_ocr_candidates(ocr_candidates, len(chars))

        hint = _build_confusable_hint(text)
        conf_hint = _build_conf_hint(chars, confs, ocr_cands)
        user_prompt = (
            f"形近字参考表（仅供挑候选参考，格式「字: 易混字…」）：\n"
            f"{hint or '（本段文本未匹配到表内形近字，请仅凭文义判断）'}\n\n"
            + (f"OCR 低置信位（请优先核查，格式「片段|可疑字|OCR备选」）：\n{conf_hint}\n\n" if conf_hint else "")
            + f"待校对的 OCR 文本：\n{text}"
        )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
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
                choice = raw["choices"][0]
                content = choice["message"]["content"] or ""
                parsed = json.loads(_strip_code_fence(content))
                break
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                finish_reason, content_length = _choice_diagnostics(raw)
                logger.warning(
                    "DeepSeek 校对返回无法解析: %s "
                    "(finish_reason=%s, content_length=%s, max_tokens=%s, attempt=%s)",
                    exc,
                    finish_reason,
                    content_length,
                    self.max_tokens,
                    attempt + 1,
                )
                if attempt == 0:
                    continue
                raise RuntimeError("DeepSeek returned an invalid structured response") from exc

        risks = _assemble_risks(text, parsed, confs, ocr_cands)
        # OCR 硬低置信、但大模型没标的位置，单独兜底成「低置信」风险交专家过目。
        risks = _add_low_conf_risks(text, risks, confs, ocr_cands)
        note = parsed.get("note") if isinstance(parsed, dict) else None
        return ProofreadResult(
            text=text,
            risks=risks,
            model=self.model,
            note=(str(note).strip() or None) if note else None,
        )


def _build_confusable_hint(text: str) -> str:
    index = _confusable_index()
    seen: list[str] = []
    for ch in text:
        if ch in index and ch not in seen:
            seen.append(ch)
        if len(seen) >= _MAX_HINT_CHARS:
            break
    lines = [f"{ch}: {' '.join(index[ch][:_MAX_TWINS])}" for ch in seen]
    return "\n".join(lines)


def _assemble_risks(
    text: str,
    parsed: Any,
    confs: list[float] | None,
    ocr_cands: dict[int, list[str]],
) -> list[ProofreadRisk]:
    if not isinstance(parsed, dict):
        return []
    issues = parsed.get("issues")
    if not isinstance(issues, list):
        return []

    risks: list[ProofreadRisk] = []
    used_positions: set[int] = set()
    for raw in issues:
        if not isinstance(raw, dict):
            continue
        suspect = str(raw.get("suspect") or "").strip()
        snippet = str(raw.get("snippet") or "").strip()
        if len(suspect) != 1 or not snippet:
            continue

        position = _locate(text, snippet, suspect)
        if position is None or position in used_positions:
            continue
        used_positions.add(position)

        candidates = _assemble_candidates(
            suspect, raw.get("candidates"), ocr_cands.get(position)
        )
        if not candidates:
            continue

        risks.append(
            ProofreadRisk(
                position=position,
                original=suspect,
                snippet=snippet,
                candidates=candidates,
                confidence=_clamp01(raw.get("confidence"), default=0.5),
                ocr_confidence=(confs[position] if confs else None),
                reason=str(raw.get("reason") or "").strip(),
                category=_normalize_category(raw.get("category")),
            )
        )

    risks.sort(key=lambda r: r.position)
    return risks


def _add_low_conf_risks(
    text: str,
    risks: list[ProofreadRisk],
    confs: list[float] | None,
    ocr_cands: dict[int, list[str]],
) -> list[ProofreadRisk]:
    """OCR 硬低置信、但 DeepSeek 未标的位置，兜底成「低置信」风险交专家过目。"""
    if not confs:
        return risks
    chars = list(text)
    covered = {r.position for r in risks}
    for pos, conf in enumerate(confs):
        if conf >= _CONF_HARD_GATE or pos in covered:
            continue
        suspect = chars[pos]
        candidates = _assemble_candidates(suspect, None, ocr_cands.get(pos))
        snippet = "".join(chars[max(0, pos - 5): pos + 6])
        risks.append(
            ProofreadRisk(
                position=pos,
                original=suspect,
                snippet=snippet,
                candidates=candidates,
                confidence=round(1.0 - conf, 2),
                ocr_confidence=conf,
                reason=f"OCR 模型对此字把握较低（{conf * 100:.0f}%），请对照原图核对。",
                category="低置信",
            )
        )
    risks.sort(key=lambda r: r.position)
    return risks


def _locate_window(chars: list[str], pos: int) -> str:
    return "".join(chars[max(0, pos - 5): pos + 6])


def _locate(text: str, snippet: str, suspect: str) -> int | None:
    """用片段在原文中定位可疑字的绝对下标；模型不负责数位置，由后端核验。"""
    start = text.find(snippet)
    if start < 0:
        return None
    offset = snippet.find(suspect)
    if offset < 0:
        return None
    position = start + offset
    if position >= len(text) or text[position] != suspect:
        return None
    return position


def _assemble_candidates(
    suspect: str,
    raw_candidates: Any,
    ocr_candidates: list[str] | None = None,
) -> list[ProofreadCandidate]:
    twins = set(confusable_twins(suspect))
    ocr_set = set(ocr_candidates or [])
    ordered: list[str] = []
    seen: set[str] = set()

    def _push(ch: str) -> None:
        ch = (ch or "").strip()
        if len(ch) == 1 and ch != suspect and ch not in seen:
            ordered.append(ch)
            seen.add(ch)

    if isinstance(raw_candidates, list):
        for item in raw_candidates:
            _push(str(item or ""))
    # OCR 自己的次优读法：强证据，补进候选。
    for ch in ocr_candidates or []:
        _push(ch)
    # 模型漏掉的形近孪生字补到末尾，确保形近候选不丢。
    for ch in twins:
        _push(ch)

    def _source(ch: str) -> str:
        if ch in ocr_set:
            return "ocr"
        if ch in twins:
            return "confusable"
        return "context"

    return [ProofreadCandidate(char=ch, source=_source(ch)) for ch in ordered]


def _normalize_category(value: Any) -> str:
    text = str(value or "").strip()
    allowed = {"形近", "文义", "缺漏", "衍文", "其他", "低置信"}
    return text if text in allowed else "其他"


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
        chars = [str(c).strip() for c in value if len(str(c).strip()) == 1]
        if chars:
            out[pos] = chars
    return out


def _build_conf_hint(
    chars: list[str],
    confs: list[float] | None,
    ocr_cands: dict[int, list[str]],
) -> str:
    """列出 OCR 低置信位（片段|可疑字|OCR备选）供 DeepSeek 重点核查。"""
    if not confs:
        return ""
    lines: list[str] = []
    for pos, conf in enumerate(confs):
        if conf >= _CONF_HINT_GATE:
            continue
        window = _locate_window(chars, pos)
        cands = " ".join(ocr_cands.get(pos, [])) or "-"
        lines.append(f"{window}|{chars[pos]}|{cands}")
        if len(lines) >= _MAX_CONF_HINTS:
            break
    return "\n".join(lines)


def _clamp01(value: Any, *, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return min(max(number, 0.0), 1.0)


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
