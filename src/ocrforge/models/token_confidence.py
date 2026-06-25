"""Token→字符 置信度对齐（纯逻辑，无 torch 依赖，便于单测）。

PaddleOCR-VL 贪婪解码时，每个生成 token 的 softmax 概率即模型对该 token 的把握。
但 token ≠ 字：一个 token 可能产出多字、一个字也可能跨多 token（生僻字/字节回退）。
本模块把「逐 token 的概率 + top-k 备选」对齐到「逐字符的置信度 + 候选字」。
对齐以最终解码文本为锚（text_anchored_pieces），对生僻字/扩展区汉字的 byte fallback
稳健——半个字无论渲染成 "" 还是替换符 �，都能正确归并，不会错位。

约定（pieces 由 text_anchored_pieces 算出）：
- pieces[i]      : 第 i 个生成 token 新完成的字符（可能为 ""，表示该字节 token 尚未凑成字）。
- probs[i]       : 第 i 个 token 被选中的概率 ∈ [0,1]。
- topk_pieces[i] : 第 i 个 token 的若干备选 token 各自单独 decode 的字符串（已去掉被选中的那个）。

输出按「码点」（Python str 索引）对齐，与前端 Array.from 一致。
"""

from __future__ import annotations

from typing import Callable


def text_anchored_pieces(
    final_text: str,
    token_ids: list[int],
    decode: Callable[[list[int]], str],
) -> list[str] | None:
    """以最终文本为锚，算出每个 token「新完成」的字符片段，对 byte-fallback 稳健。

    很多分词器对生僻字 / 扩展区汉字走 byte fallback：单个字节 token 解码不出完整字，
    decode 中间前缀会产出 "" 或替换符 �（U+FFFD）。本函数不依赖「前缀稳定性」，而是
    以 final_text（整段权威解码结果）为基准，只统计「已经成为 final_text 前缀的字符」——
    无论半个字渲染成 "" 还是 �，都能正确对齐：凑不出字的字节 token 片段记为 ""，
    其概率由 assemble 累计到完成该字的那一步取最小。

    final_text: 对完整生成序列 decode(skip special) 的结果（已去 eos）。
    decode    : Callable[[list[int]], str]，对 token id 前缀解码（skip special）。
    返回与 token_ids 等长的 pieces；若解码前缀偏离 final_text（异常分词器）或末尾
    未对齐（生成被截断在半个字）则返回 None —— 宁可不给也不给错位的。
    """
    chars = list(final_text)
    pieces: list[str] = []
    covered = 0
    for i in range(len(token_ids)):
        cur = decode(token_ids[: i + 1])
        adv = _common_prefix_len(cur, chars)
        if adv < covered:
            return None  # 解码结果倒退/偏离锚文本，放弃
        pieces.append("".join(chars[covered:adv]))
        covered = adv
    if covered != len(chars):
        return None  # 末尾还有字没被任何 token 覆盖（截断在半个字）
    return pieces


def _common_prefix_len(cur: str, chars: list[str]) -> int:
    """cur 与 final_text 的最长公共前缀长度（按码点）。

    半个字渲染成 � 时，� 不等于 final_text 的下一个真实字 → 自然停在已完成处。
    """
    cur_chars = list(cur)
    k = 0
    m = min(len(cur_chars), len(chars))
    while k < m and cur_chars[k] == chars[k]:
        k += 1
    return k


def strip_aligned(
    text: str,
    confs: list[float],
    alts: dict[int, list[str]],
) -> tuple[str, list[float], dict[int, list[str]]]:
    """去掉 text 首尾空白，并**同步**裁剪 confs、移位 alts，使三者保持逐字对齐。

    模型输出常带首尾换行/空格；若只 strip 文本而不裁 confs，长度就会错位
    （前端按长度一致性判断，会因此整段丢弃置信度）。
    """
    lead = len(text) - len(text.lstrip())
    end = len(text.rstrip())  # 尾部空白起始下标
    if end < lead:  # 全是空白
        return "", [], {}
    new_text = text[lead:end]
    new_confs = confs[lead:end]
    new_alts = {k - lead: v for k, v in alts.items() if lead <= k < end}
    return new_text, new_confs, new_alts


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
    seen: set[str] = {exclude, "�"}  # 排除自身与替换符 �（byte-fallback 残字）
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
