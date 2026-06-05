from __future__ import annotations


def normalize_text(text: str, keep_ascii: bool = False) -> str:
    text = text.replace("<｜end▁of▁sentence｜>", "")
    if keep_ascii:
        return "".join(ch for ch in text if not ch.isspace())
    return "".join(ch for ch in text if "\u3400" <= ch <= "\u9fff" or "\U00020000" <= ch <= "\U0002ebef")


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]


def text_metrics(prediction: str, target: str, keep_ascii: bool = False) -> dict:
    pred = normalize_text(prediction, keep_ascii=keep_ascii)
    gold = normalize_text(target, keep_ascii=keep_ascii)
    distance = levenshtein(pred, gold)
    cer = distance / len(gold) if gold else 0.0
    return {
        "gt_chars": len(gold),
        "pred_chars": len(pred),
        "edit_distance": distance,
        "cer": cer,
        "char_accuracy": max(0.0, 1.0 - cer),
        "exact_match": pred == gold,
        "normalized_similarity": max(0.0, 1.0 - distance / max(len(pred), len(gold), 1)),
    }


def aggregate_metrics(items: list[dict]) -> dict:
    if not items:
        return {"evaluated": 0}
    totals = {
        "evaluated": len(items),
        "gt_chars": sum(item["gt_chars"] for item in items),
        "pred_chars": sum(item["pred_chars"] for item in items),
        "edit_distance": sum(item["edit_distance"] for item in items),
        "exact_match": sum(1 for item in items if item["exact_match"]),
    }
    cer = totals["edit_distance"] / totals["gt_chars"] if totals["gt_chars"] else 0.0
    totals.update(
        {
            "cer": cer,
            "char_accuracy": max(0.0, 1.0 - cer),
            "exact_match_rate": totals["exact_match"] / len(items),
            "mean_image_cer": sum(item["cer"] for item in items) / len(items),
            "mean_normalized_similarity": sum(item["normalized_similarity"] for item in items) / len(items),
        }
    )
    return totals

