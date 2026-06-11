from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ocrforge_web.schemas import CharRecord, CharSummary
from ocrforge_web.services.evolution_repo import EvolutionRepository, get_repo

router = APIRouter(tags=["evolution"])


@router.get("/evolution", response_model=list[CharSummary])
def list_evolution(
    type: str | None = Query(default=None, pattern="^(merge|one_to_one)$"),
    tier: str | None = Query(default=None, pattern="^(grid|archive)$"),
    repo: EvolutionRepository = Depends(get_repo),
) -> list[CharSummary]:
    return repo.list_characters(record_type=type, tier=tier)


@router.get("/evolution/stats")
def evolution_stats(repo: EvolutionRepository = Depends(get_repo)) -> dict:
    return repo.stats()


@router.get("/evolution/cl-analysis")
def evolution_cl_analysis() -> dict:
    import json
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "data" / "cl_analysis.v1.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="CL analysis not generated yet")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/evolution/{char}", response_model=CharRecord)
def get_evolution(char: str, repo: EvolutionRepository = Depends(get_repo)) -> CharRecord:
    record = repo.get(char)
    if record is None:
        raise HTTPException(status_code=404, detail=f"character {char!r} not found")
    return record
