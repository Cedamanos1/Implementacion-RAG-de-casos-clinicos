from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from rag.config import (
    DEFAULT_INDEX_PATH,
    DEFAULT_MIN_SCORE,
    DEFAULT_TOP_K,
    SPECIALTIES,
)
from rag.indexer import RAGIndex

router = APIRouter(prefix="/api/v1/rag", tags=["rag"])


class SearchCasesRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    specialty: str
    top_k: int = Field(default=5, ge=1, le=20)
    min_score: float = Field(default=DEFAULT_MIN_SCORE, ge=-1.0, le=1.0)


class SearchEvidenceRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    case_id: str
    allowed_evidence_ids: list[str] | None = None
    owner: str | None = None
    category: str | None = None
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=20)
    min_score: float = Field(default=DEFAULT_MIN_SCORE, ge=-1.0, le=1.0)


@lru_cache
def get_rag_index() -> RAGIndex:
    if not DEFAULT_INDEX_PATH.exists():
        raise FileNotFoundError(
            f"No existe el índice RAG en {DEFAULT_INDEX_PATH}. "
            "Ejecuta primero: python -m rag.build"
        )
    return RAGIndex.load(DEFAULT_INDEX_PATH)


def _safe_case_candidate(item: dict) -> dict:
    return {
        "case_id": item["case_id"],
        "specialty": item["specialty"],
        "chunk_id": item["chunk_id"],
        "source": item["source"],
        "category": item["category"],
        "text": item["text"],
        "score": item["score"],
    }


@router.get("/health")
def rag_health():
    try:
        index = get_rag_index()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "status": "ok",
        "indexed_cases": len(index.case_ids),
        "indexed_chunks": len(index.chunks),
        "model": index.encoder.model_name,
        "model_version": index.encoder.version,
        "schema_version": index.schema_version,
        "index_hash": index.index_hash,
    }


@router.post("/cases/search")
def search_cases(payload: SearchCasesRequest):
    if payload.specialty not in SPECIALTIES:
        raise HTTPException(
            status_code=422,
            detail=f"Especialidad inválida: {payload.specialty!r}.",
        )

    try:
        index = get_rag_index()
        results = index.search_cases(
            payload.query,
            specialty=payload.specialty,
            top_k=max(payload.top_k * 3, payload.top_k),
            min_score=payload.min_score,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # El índice rankea chunks. Para selección de casos consolidamos por case_id
    # y conservamos el mejor fragmento de cada caso.
    best_by_case: dict[str, dict] = {}
    for item in results:
        current = best_by_case.get(item["case_id"])
        if current is None or item["score"] > current["score"]:
            best_by_case[item["case_id"]] = item

    ordered = sorted(
        best_by_case.values(),
        key=lambda item: item["score"],
        reverse=True,
    )[: payload.top_k]

    return [_safe_case_candidate(item) for item in ordered]


@router.post("/evidence/search")
def search_evidence(payload: SearchEvidenceRequest):
    try:
        index = get_rag_index()
        return index.search(
            payload.query,
            case_id=payload.case_id,
            allowed_evidence_ids=payload.allowed_evidence_ids,
            owner=payload.owner,
            category=payload.category,
            top_k=payload.top_k,
            min_score=payload.min_score,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/reload")
def reload_rag_index():
    get_rag_index.cache_clear()
    try:
        index = get_rag_index()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {
        "message": "Índice RAG recargado.",
        "indexed_cases": len(index.case_ids),
        "indexed_chunks": len(index.chunks),
        "index_hash": index.index_hash,
    }
