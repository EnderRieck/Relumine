from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ocrforge_web import __version__
from ocrforge_web.schemas import HealthResponse
from ocrforge_web.settings import get_settings

logger = logging.getLogger("ocrforge_web")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("starting ocrforge-web v%s | project_root=%s", __version__, settings.project_root)

    try:
        from ocrforge_web.services import ocr_service  # type: ignore
    except Exception:
        ocr_service = None  # noqa: F841

    if ocr_service is not None and getattr(ocr_service, "startup", None):
        try:
            await ocr_service.startup(settings)
        except Exception as e:
            logger.warning("OCR backend unavailable, OCR tab disabled: %s", e)

    yield

    if ocr_service is not None and getattr(ocr_service, "shutdown", None):
        await ocr_service.shutdown()


app = FastAPI(title="古籍重光 API", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    try:
        from ocrforge_web.services import ocr_service  # type: ignore
        model_loaded = bool(getattr(ocr_service, "is_loaded", lambda: False)())
    except Exception:
        model_loaded = False
    return HealthResponse(ok=True, model_loaded=model_loaded, version=__version__)


def _include_routers() -> None:
    from importlib import import_module

    for mod_name in ("convert", "evolution", "ocr"):
        try:
            mod = import_module(f"ocrforge_web.routers.{mod_name}")
        except ModuleNotFoundError:
            logger.info("router %s not present yet, skipping", mod_name)
            continue
        router = getattr(mod, "router", None)
        if router is not None:
            app.include_router(router, prefix="/api")
            logger.info("mounted router %s", mod_name)


_include_routers()
