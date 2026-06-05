PROMPTS = {
    "free_ocr": "<image>\nFree OCR.",
    "markdown": "<image>\n<|grounding|>Convert the document to markdown.",
    "single_char": "<image>\nRecognize the single Chinese character. Return only the character.",
    "line_ocr": "<image>\nRecognize this text line. Return only the text.",
}


def get_prompt(name: str) -> str:
    try:
        return PROMPTS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown prompt: {name}") from exc

