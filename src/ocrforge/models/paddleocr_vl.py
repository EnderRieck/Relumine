from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import torch
from omegaconf import DictConfig
from PIL import Image, ImageOps
from transformers import AutoModelForCausalLM, AutoProcessor

from ocrforge.utils.paths import resolve_path

TORCH_DTYPES = {
    "bfloat16": torch.bfloat16,
    "float16": torch.float16,
    "float32": torch.float32,
}

PROMPTS = {
    "ocr": "OCR:",
    "table": "Table Recognition:",
    "formula": "Formula Recognition:",
    "chart": "Chart Recognition:",
    "spotting": "Spotting:",
    "seal": "Seal Recognition:",
}

MODEL_CODE_FILES = [
    "configuration_paddleocr_vl.py",
    "image_processing_paddleocr_vl.py",
    "modeling_paddleocr_vl.py",
    "processing_paddleocr_vl.py",
]


class PaddleOCRVLModule:
    supports_training = True

    def __init__(self, cfg: DictConfig, project_root: Path):
        self.cfg = cfg
        self.project_root = project_root
        self.model_path = resolve_path(cfg.path, project_root)
        torch_dtype = TORCH_DTYPES[str(cfg.torch_dtype)]
        self.processor = AutoProcessor.from_pretrained(
            str(self.model_path),
            trust_remote_code=bool(cfg.trust_remote_code),
            local_files_only=bool(cfg.local_files_only),
        )
        self.model = AutoModelForCausalLM.from_pretrained(
            str(self.model_path),
            trust_remote_code=bool(cfg.trust_remote_code),
            local_files_only=bool(cfg.local_files_only),
            torch_dtype=torch_dtype,
            attn_implementation=str(cfg.get("attn_implementation", "flash_attention_2")),
        )
        use_cache = bool(cfg.get("use_cache", True))
        self.model.config.use_cache = use_cache
        if getattr(self.model, "generation_config", None) is not None:
            self.model.generation_config.use_cache = use_cache
        self.input_device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    def apply_parallel(self, parallel_cfg: DictConfig, task: str, default_device: str | torch.device | None = None) -> "PaddleOCRVLModule":
        mode = str(parallel_cfg.mode)
        if mode != "data":
            raise RuntimeError("PaddleOCR-VL backend currently supports only parallel=data in OCRForge.")
        return self.to_device(default_device or self.cfg.device)

    def to_device(self, device: str | torch.device | None = None) -> "PaddleOCRVLModule":
        target = torch.device(device or self.cfg.device)
        if target.type == "cuda" and not torch.cuda.is_available():
            target = torch.device("cpu")
        self.model = self.model.to(target)
        self.input_device = target
        return self

    def train(self) -> None:
        self._target_model().train()

    def eval(self) -> None:
        self._target_model().eval()

    def _target_model(self):
        return self.model.module if hasattr(self.model, "module") else self.model

    def save_pretrained(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        self._target_model().save_pretrained(str(output_dir), safe_serialization=True)
        self.processor.save_pretrained(str(output_dir))
        self._copy_remote_code_files(output_dir)

    def _copy_remote_code_files(self, output_dir: Path) -> None:
        for name in MODEL_CODE_FILES:
            source = self.model_path / name
            if source.exists():
                shutil.copy2(source, output_dir / name)

    def generate_page(self, image_path: Path, prompt: str | None = None, output_path: Path | None = None, save_results: bool = False) -> str:
        del output_path, save_results
        self.eval()
        image = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
        task = str(self.cfg.get("task", "ocr"))
        text_prompt = str(self.cfg.get("prompt", PROMPTS.get(task, "OCR:")))
        max_pixels = int(self.cfg.get("max_pixels", 1280 * 28 * 28))
        max_new_tokens = int(self.cfg.get("max_new_tokens", 512))
        use_cache = bool(self.cfg.get("use_cache", True))
        do_sample = bool(self.cfg.get("do_sample", False))
        num_beams = int(self.cfg.get("num_beams", 1))
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": text_prompt},
                ],
            }
        ]
        inputs = self.processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            images_kwargs={
                "size": {
                    "shortest_edge": self.processor.image_processor.min_pixels,
                    "longest_edge": max_pixels,
                }
            },
        ).to(self.input_device)
        target = self._target_model()
        with torch.inference_mode():
            outputs = target.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                use_cache=use_cache,
                do_sample=do_sample,
                num_beams=num_beams,
                eos_token_id=self.processor.tokenizer.eos_token_id,
                pad_token_id=self.processor.tokenizer.pad_token_id,
            )
        generated = outputs[0][inputs["input_ids"].shape[-1] :]
        if generated.numel() > 0 and int(generated[-1]) == self.processor.tokenizer.eos_token_id:
            generated = generated[:-1]
        return self.processor.decode(generated, skip_special_tokens=True).strip()

    def build_training_batch(self, image_path: Path, prompt: str, target_text: str) -> dict[str, Any]:
        image = ImageOps.exif_transpose(Image.open(image_path)).convert("RGB")
        text_prompt = str(self.cfg.get("prompt", prompt or PROMPTS.get(str(self.cfg.get("task", "ocr")), "OCR:")))
        max_pixels = int(self.cfg.get("max_pixels", 1280 * 28 * 28))
        user_message = {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": text_prompt},
            ],
        }
        full_inputs = self.processor.apply_chat_template(
            [
                user_message,
                {
                    "role": "assistant",
                    "content": [{"type": "text", "text": target_text}],
                },
            ],
            add_generation_prompt=False,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
            images_kwargs={
                "size": {
                    "shortest_edge": self.processor.image_processor.min_pixels,
                    "longest_edge": max_pixels,
                }
            },
        )
        labels = full_inputs["input_ids"].clone()
        response_ids = self.processor.tokenizer(
            target_text + str(self.processor.tokenizer.eos_token),
            add_special_tokens=False,
            return_tensors="pt",
        )["input_ids"][0]
        prompt_length = _suffix_start(full_inputs["input_ids"][0], response_ids)
        if prompt_length is None:
            prompt_inputs = self.processor.apply_chat_template(
                [user_message],
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt",
                images_kwargs={
                    "size": {
                        "shortest_edge": self.processor.image_processor.min_pixels,
                        "longest_edge": max_pixels,
                    }
                },
            )
            prompt_length = int(prompt_inputs["input_ids"].shape[1])
        labels[:, :prompt_length] = -100
        labels[full_inputs["attention_mask"] == 0] = -100
        full_inputs["labels"] = labels
        full_inputs["use_cache"] = False
        return dict(full_inputs)

    def collate_training_batches(self, batches: list[dict[str, Any]], pad_token_id: int) -> dict[str, Any]:
        max_length = max(int(batch["input_ids"].shape[1]) for batch in batches)
        return {
            "input_ids": torch.stack([_pad_1d(batch["input_ids"], max_length, pad_token_id) for batch in batches], dim=0),
            "attention_mask": torch.stack([_pad_1d(batch["attention_mask"], max_length, 0) for batch in batches], dim=0),
            "labels": torch.stack([_pad_1d(batch["labels"], max_length, -100) for batch in batches], dim=0),
            "pixel_values": torch.cat([batch["pixel_values"] for batch in batches], dim=0),
            "image_grid_thw": torch.cat([batch["image_grid_thw"] for batch in batches], dim=0),
            "use_cache": False,
        }

    def move_batch_to_device(self, batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
        moved = {}
        for key, value in batch.items():
            if hasattr(value, "to"):
                moved[key] = value.to(device)
            else:
                moved[key] = value
        return moved


def _pad_1d(tensor: torch.Tensor, length: int, value: int) -> torch.Tensor:
    tensor = tensor.squeeze(0)
    if tensor.numel() == length:
        return tensor
    padding = torch.full((length - tensor.numel(),), value, dtype=tensor.dtype)
    return torch.cat([tensor, padding], dim=0)


def _suffix_start(input_ids: torch.Tensor, suffix_ids: torch.Tensor) -> int | None:
    suffix_length = int(suffix_ids.numel())
    if suffix_length == 0 or suffix_length > int(input_ids.numel()):
        return None
    start = int(input_ids.numel()) - suffix_length
    if torch.equal(input_ids[start:], suffix_ids.to(input_ids.device)):
        return start
    return None
