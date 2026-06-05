from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from ocrforge_web.schemas import CharRecord, CharSummary
from ocrforge_web.services.evolution_repo import EvolutionRepository, get_repo

router = APIRouter(tags=["evolution"])


@router.get("/evolution", response_model=list[CharSummary])
def list_evolution(repo: EvolutionRepository = Depends(get_repo)) -> list[CharSummary]:
    return repo.list_characters()


@router.get("/evolution/{char}", response_model=CharRecord)
def get_evolution(char: str, repo: EvolutionRepository = Depends(get_repo)) -> CharRecord:
    record = repo.get(char)
    if record is None:
        raise HTTPException(status_code=404, detail=f"character {char!r} not found")
    return record
