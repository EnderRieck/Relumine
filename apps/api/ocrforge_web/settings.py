from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_THIS = Path(__file__).resolve()
# settings.py → ocrforge_web → api → apps → CultureCourse → <project_root>
_PROJECT_ROOT = _THIS.parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="OCRFORGE_WEB_", env_file=None)

    project_root: Path = _PROJECT_ROOT
    paddle_ckpt: Path = (
        _PROJECT_ROOT
        / "CultureCourse/runs/train/20260429-152932_train_paddle/checkpoints/step_000200"
    )
    paddle_dtype: str = "bfloat16"
    paddle_device: str = "cuda:0"
    paddle_attn: str = "flash_attention_2"
    paddle_task: str = "ocr"
    paddle_max_pixels: int = 1003520
    paddle_max_new_tokens: int = 1024
    ocr_backend: str = "auto"
    remote_ocr_url: str | None = None
    remote_ocr_timeout: float = 120.0

    opencc_profile: str = "t2s"

    evolution_backend: str = "json"
    evolution_path: Path = Path(__file__).parent / "data" / "relumine_char_db.v1.json"

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    ocr_warmup: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
