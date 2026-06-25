"""Token→字符 置信度对齐（纯逻辑，无 torch 依赖，便于单测）。

PaddleOCR-VL 贪婪解码时，每个生成 token 的 softmax 概率即模型对该 token 的把握。
但 token ≠ 字：一个 token 可能产出多字、一个字也可能跨多 token（生僻字/字节回退）。
本模块把「逐 token 的概率 + top-k 备选」对齐到「逐字符的置信度 + 候选字」。

约定（由调用方在模型侧用 tokenizer 增量 decode 得到）：
- pieces[i]      : 第 i 个生成 token 相对前缀「新增」的文本（可能为 ""，表示尚未凑成字）。
- probs[i]       : 第 i 个 token 被选中的概率 ∈ [0,1]。
- topk_pieces[i] : 第 i 个 token 的若干备选 token 各自单独 decode 的字符串（已去掉被选中的那个）。

输出按「码点」（Python str 索引）对齐，与前端 Array.from 一致。
"""

from __future__ import annotations

from typing import Callable


def incremental_pieces(
    token_ids: list[int],
    decode: Callable[[list[int]], str],
) -> list[str] | None:
    """用 decode 增量还原每个 token 相对前缀「新增」的文本片段。

    decode: 把一段 token id 解码为文本（已 skip special tokens）。
    返回与 token_ids 等长的 pieces；若分词器**非前缀稳定**（解码更长前缀的结果
    不以更短前缀的结果开头，常见于带前导空格的 BPE）则返回 None —— 此时宁可不给
    置信度也不给错位的。
    """
    pieces: list[str] = []
    prev = ""
    for i in range(len(token_ids)):
        cur = decode(token_ids[: i + 1])
        if not cur.startswith(prev):
            return None
        pieces.append(cur[len(prev):])
        prev = cur
    return pieces


def assemble_char_confidence(
    pieces: list[str],
    probs: list[float],
    topk_pieces: list[list[str]] | None = None,
    *,
    alt_threshold: float = 0.95,
    top_k_emit: int = 3,
) -> tuple[str, list[float], dict[int, list[str]]]:
    """返回 (text, char_confidences, alternatives)。

    - char_confidences[k] 是 text 第 k 个码点的置信度；跨多 token 的字取各 token 概率的最小值
      （最薄弱环节，便于做「低置信」闸门）。
    - alternatives[k] 仅对「单 token 单字、且置信度 < alt_threshold」的位置给出，
      取该位置 top-k 备选里干净的单字，最多 top_k_emit 个。
    """
    if topk_pieces is None:
        topk_pieces = [[] for _ in pieces]
    if not (len(pieces) == len(probs) == len(topk_pieces)):
        raise ValueError("pieces / probs / topk_pieces 长度必须一致")

    chars: list[str] = []
    confs: list[float] = []
    alternatives: dict[int, list[str]] = {}

    pending_probs: list[float] = []  # 已消费但尚未凑成字的 token 概率

    for piece, prob, topk in zip(pieces, probs, topk_pieces):
        p = _clamp01(prob)
        if piece == "":
            pending_probs.append(p)
            continue
        for j, ch in enumerate(piece):
            used_pending = j == 0 and bool(pending_probs)
            if used_pending:
                contrib = [*pending_probs, p]
                pending_probs = []
            else:
                contrib = [p]
            conf = min(contrib)
            pos = len(chars)
            chars.append(ch)
            confs.append(conf)

            # 候选仅在「单 token 恰好产出这一个字」时可靠
            clean_single = len(piece) == 1 and not used_pending
            if clean_single and conf < alt_threshold:
                cands = _clean_alts(topk, exclude=ch, limit=top_k_emit)
                if cands:
                    alternatives[pos] = cands

    return "".join(chars), confs, alternatives


def _clean_alts(topk: list[str], *, exclude: str, limit: int) -> list[str]:
    out: list[str] = []
    seen: set[str] = {exclude}
    for raw in topk:
        ch = (raw or "").strip()
        if len(ch) == 1 and ch not in seen:
            out.append(ch)
            seen.add(ch)
        if len(out) >= limit:
            break
    return out


def _clamp01(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number < 0.0:
        return 0.0
    if number > 1.0:
        return 1.0
    return number
