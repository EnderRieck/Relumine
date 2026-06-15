from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_THIS = Path(__file__).resolve()
# settings.py → ocrforge_web → api → apps → CultureCourse → <project_root>
_PROJECT_ROOT = _THIS.parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OCRFORGE_WEB_",
        env_file=_THIS.parents[1] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    evolution_backend: str = "sqlite"
    evolution_path: Path = Path(__file__).parent / "data" / "relumine_char_db.v2.sqlite"

    llm_api_key: str | None = None
    llm_base_url: str = "https://api.deepseek.com"
    llm_model: str = "deepseek-v4-flash"
    llm_timeout: float = 120.0
    culture_db_path: Path = Path(__file__).parent / "data" / "culture_graph.sqlite"

    # --- agent harness ---
    # Model used by the chat agent. Falls back to llm_model when unset; override
    # (e.g. "deepseek-chat") if the default model lacks function-calling support.
    agent_model: str | None = None
    brave_api_key: str | None = None
    brave_endpoint: str = "https://api.search.brave.com/res/v1/web/search"
    agent_enable_browser: bool = True
    agent_max_steps: int = 12
    agent_session_ttl: float = 3600.0

    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    ocr_warmup: bool = True


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
