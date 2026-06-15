from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query

from ocrforge_web.schemas import (
    CultureAnalysis,
    CultureAnalysisSummary,
    CultureAnalyzeRequest,
    CultureReviewRequest,
    CultureStatusResponse,
)
from ocrforge_web.services.culture_store import CultureStore
from ocrforge_web.services.deepseek_culture import DeepSeekCultureClient
from ocrforge_web.services.authority_linker import AuthorityLinker
from ocrforge_web.settings import Settings, get_settings

router = APIRouter(tags=["culture"])


def _client(settings: Settings = Depends(get_settings)) -> DeepSeekCultureClient:
    return DeepSeekCultureClient(settings)


def _store(settings: Settings = Depends(get_settings)) -> CultureStore:
    return CultureStore(settings.culture_db_path)


@router.get("/culture/status", response_model=CultureStatusResponse)
def culture_status(
    client: DeepSeekCultureClient = Depends(_client),
    settings: Settings = Depends(get_settings),
) -> CultureStatusResponse:
    linker = AuthorityLinker(settings)
    return CultureStatusResponse(
        configured=client.configured,
        model=client.model,
        cbdb_available=linker.cbdb_available,
        chgis_available=linker.chgis_available,
    )


@router.post("/culture/analyze", response_model=CultureAnalysis)
async def analyze_culture(
    request: CultureAnalyzeRequest,
    client: DeepSeekCultureClient = Depends(_client),
    store: CultureStore = Depends(_store),
    settings: Settings = Depends(get_settings),
) -> CultureAnalysis:
    if not client.configured:
        raise HTTPException(status_code=503, detail="DeepSeek API key is not configured")
    try:
        extracted = await asyncio.to_thread(
            client.analyze, request.text, request.title
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    linker = AuthorityLinker(settings)
    linked_entities = await asyncio.to_thread(
        linker.link_entities, extracted.entities
    )
    analysis = CultureAnalysis(
        id=uuid4().hex,
        title=request.title or extracted.title,
        source_text=request.text,
        summary=extracted.summary,
        modern_translation=extracted.modern_translation,
        entities=linked_entities,
        relations=extracted.relations,
        model=client.model,
        created_at=datetime.now(UTC).isoformat(),
    )
    return store.save(analysis)


@router.post(
    "/culture/analyses/{analysis_id}/link-authorities",
    response_model=CultureAnalysis,
)
async def link_analysis_authorities(
    analysis_id: str,
    store: CultureStore = Depends(_store),
    settings: Settings = Depends(get_settings),
) -> CultureAnalysis:
    analysis = store.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    linker = AuthorityLinker(settings)
    linked_entities = await asyncio.to_thread(
        linker.link_entities, analysis.entities
    )
    updated = store.replace_entities(analysis_id, linked_entities)
    if updated is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return updated


@router.get("/culture/analyses", response_model=list[CultureAnalysisSummary])
def list_analyses(
    limit: int = Query(default=20, ge=1, le=100),
    store: CultureStore = Depends(_store),
) -> list[CultureAnalysisSummary]:
    return store.list(limit)


@router.get("/culture/analyses/{analysis_id}", response_model=CultureAnalysis)
def get_analysis(
    analysis_id: str, store: CultureStore = Depends(_store)
) -> CultureAnalysis:
    analysis = store.get(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return analysis


@router.patch("/culture/analyses/{analysis_id}/review", response_model=CultureAnalysis)
def review_analysis(
    analysis_id: str,
    request: CultureReviewRequest,
    store: CultureStore = Depends(_store),
) -> CultureAnalysis:
    analysis = store.review(analysis_id, request)
    if analysis is None:
        raise HTTPException(status_code=404, detail="analysis not found")
    return analysis
