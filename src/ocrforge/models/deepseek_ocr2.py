from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import torch
from omegaconf import DictConfig, OmegaConf
from transformers import AutoModel, AutoTokenizer

from ocrforge.parallel.dispatch import build_model_device_map, build_pipeline_device_map, dispatch_with_device_map
from ocrforge.processing import DeepSeekOCRProcessor
from ocrforge.utils.paths import resolve_path

TORCH_DTYPES = {
    "bfloat16": torch.bfloat16,
    "float16": torch.float16,
    "float32": torch.float32,
}

MODEL_CODE_FILES = [
    "configuration_deepseek_v2.py",
    "conversation.py",
    "deepencoderv2.py",
    "modeling_deepseekocr2.py",
    "modeling_deepseekv2.py",
    "processor_config.json",
]


class DeepSeekOCR2Module:
    def __init__(self, cfg: DictConfig, project_root: Path):
        self.cfg = cfg
        self.project_root = project_root
        self.model_path = resolve_path(cfg.path, project_root)
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.model_path),
            trust_remote_code=bool(cfg.trust_remote_code),
            local_files_only=bool(cfg.local_files_only),
        )
        torch_dtype = TORCH_DTYPES[str(cfg.torch_dtype)]
        self.model = AutoModel.from_pretrained(
            str(self.model_path),
            _attn_implementation=str(cfg.attn_implementation),
            trust_remote_code=bool(cfg.trust_remote_code),
            use_safetensors=True,
            torch_dtype=torch_dtype,
            local_files_only=bool(cfg.local_files_only),
        )
        self.processor = DeepSeekOCRProcessor(
            self.tokenizer,
            base_size=int(cfg.base_size),
            image_size=int(cfg.image_size),
            crop_mode=bool(cfg.crop_mode),
        )
        self.parallel_mode = "data"
        self.input_device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    def apply_parallel(self, parallel_cfg: DictConfig, task: str, default_device: str | torch.device | None = None) -> "DeepSeekOCR2Module":
        mode = str(parallel_cfg.mode)
        self.parallel_mode = mode
        if mode == "data":
            return self.to_device(default_device or self.cfg.device)
        if mode == "model":
            device_map = build_model_device_map(self.model, OmegaConf.create({"parallel": parallel_cfg}))
            self.model = dispatch_with_device_map(self.model, device_map)
            self._move_view_separator(device_map["model.projector"])
            self.input_device = torch.device(device_map.get("model.embed_tokens", "cuda:0"))
            return self
        if mode == "pipeline":
            device_map = build_pipeline_device_map(self.model, OmegaConf.create({"parallel": parallel_cfg}))
            self.model = dispatch_with_device_map(self.model, device_map)
            self._move_view_separator(device_map["model.projector"])
            self.input_device = torch.device(device_map.get("model.embed_tokens", "cuda:0"))
            return self
        if mode == "tensor":
            if task != "evaluate":
                raise RuntimeError("Tensor parallel mode is currently supported only for evaluation.")
            import deepspeed

            dtype = TORCH_DTYPES[str(self.cfg.torch_dtype)]
            self.model = deepspeed.init_inference(
                self.model,
                mp_size=int(parallel_cfg.tensor_parallel_size),
                dtype=dtype,
                replace_with_kernel_inject=False,
            )
            self.input_device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
            return self
        raise ValueError(f"Unknown parallel mode: {mode}")

    def to_device(self, device: str | torch.device | None = None) -> "DeepSeekOCR2Module":
        target = device or str(self.cfg.device)
        if str(target).startswith("cuda") and torch.cuda.is_available():
            self.model = self.model.cuda()
            self.input_device = torch.device("cuda:0")
        else:
            self.model = self.model.to(target)
            self.input_device = torch.device(target)
        return self

    def train(self) -> None:
        target = self._target_model()
        target.train()

    def eval(self) -> None:
        target = self._target_model()
        target.eval()

    def _target_model(self):
        return self.model.module if hasattr(self.model, "module") else self.model

    def save_pretrained(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        target = self._target_model()
        target.save_pretrained(str(output_dir), safe_serialization=True)
        self.tokenizer.save_pretrained(str(output_dir))
        self._copy_remote_code_files(output_dir)

    def _copy_remote_code_files(self, output_dir: Path) -> None:
        for name in MODEL_CODE_FILES:
            source = self.model_path / name
            if source.exists():
                shutil.copy2(source, output_dir / name)

    def _move_view_separator(self, device: str) -> None:
        target = self._target_model()
        if hasattr(target, "model") and hasattr(target.model, "view_seperator"):
            target.model.view_seperator.data = target.model.view_seperator.data.to(device)

    def generate_page(self, image_path: Path, prompt: str, output_path: Path | None = None, save_results: bool = False) -> str:
        self.eval()
        if output_path is not None:
            output_path.mkdir(parents=True, exist_ok=True)
        target = self._target_model()
        with torch.no_grad():
            response = target.infer(
                self.tokenizer,
                prompt=prompt,
                image_file=str(image_path),
                output_path="" if output_path is None else str(output_path),
                base_size=int(self.cfg.base_size),
                image_size=int(self.cfg.image_size),
                crop_mode=bool(self.cfg.crop_mode),
                save_results=save_results,
                eval_mode=True,
            )
        return "" if response is None else str(response)

    def build_training_batch(self, image_path: Path, prompt: str, target_text: str) -> dict[str, Any]:
        return self.processor.build_inputs(image_path=image_path, prompt=prompt, target_text=target_text)

    def move_batch_to_device(self, batch: dict[str, Any], device: torch.device) -> dict[str, Any]:
        if self.parallel_mode in {"model", "pipeline", "tensor"}:
            device = self.input_device
        moved = {}
        for key, value in batch.items():
            if key == "images":
                moved[key] = [(crop.to(device), ori.to(device)) for crop, ori in value]
            elif hasattr(value, "to"):
                moved[key] = value.to(device)
            else:
                moved[key] = value
        return moved
