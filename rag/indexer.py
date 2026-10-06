import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Sequence

from app.validator import CaseSchemaValidator
from rag.chunker import Chunk, chunk_case
from rag.config import (
    ALLOWED_STATUSES,
    DEFAULT_INCLUDE_STATUSES,
    DEFAULT_INDEX_PATH,
    DEFAULT_LOG_PATH,
)
from rag.embeddings import SentenceTransformerEncoder
from rag.leak_guard import exact_leaks, protected_terms, shared_roots
from rag.retrieval_log import RetrievalLogger

CASE_ID_PATTERN = re.compile(r"^[A-Z]{3,5}-\d{3}$")
EVIDENCE_ID_PATTERN = re.compile(r"^[A-Z]{3,5}-\d{3}\.[a-z]+\.[a-z0-9_]+$")


class Encoder(Protocol):
    model_name: str
    version: str

    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


class BuildError(ValueError):
    """Raised when a case could leak protected data into the index."""


@dataclass(frozen=True)
class BuildReport:
    index: "RAGIndex"
    indexed_cases: tuple[str, ...]
    indexed_chunks: int
    skipped: tuple[dict[str, str], ...]
    warnings: tuple[dict[str, str], ...]


def _case_evidence_ids(case: dict) -> list[str]:
    public = case.get("public", {})
    items = [public.get("chief_complaint", {}), *public.get("items", [])]
    allergies = public.get("allergies")
    if isinstance(allergies, dict):
        items.append(allergies)
    items.extend(case.get("on_request", []))
    return [
        item["evidence_id"]
        for item in items
        if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)
    ]


def _index_hash(
    chunks: Sequence[Chunk],
    vectors: Sequence[Sequence[float]],
    model_name: str,
    model_version: str,
    schema_version: str,
) -> str:
    payload = {
        "model_name": model_name,
        "model_version": model_version,
        "schema_version": schema_version,
        "chunks": [chunk.to_dict() for chunk in chunks],
        "vectors": [[float(value) for value in vector] for vector in vectors],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RAGIndex:
    def __init__(
        self,
        chunks: Sequence[Chunk],
        vectors: Sequence[Sequence[float]],
        *,
        encoder: Encoder,
        schema_version: str,
        index_hash: str | None = None,
        log_path: Path = DEFAULT_LOG_PATH,
        session_id: str | None = None,
        agent: str = "unknown",
    ):
        if len(chunks) != len(vectors):
            raise ValueError("Cada chunk debe tener exactamente un embedding.")
        if chunks and any(len(vector) != len(vectors[0]) for vector in vectors):
            raise ValueError("Los embeddings tienen dimensiones incompatibles.")
        if any(not vector or any(not math.isfinite(value) for value in vector) for vector in vectors):
            raise ValueError("Los embeddings deben ser no vacíos y contener solo valores finitos.")
        self.chunks = tuple(chunks)
        self.vectors = tuple(tuple(float(value) for value in vector) for vector in vectors)
        self.encoder = encoder
        self.schema_version = schema_version
        self.index_hash = index_hash or _index_hash(
            self.chunks,
            self.vectors,
            encoder.model_name,
            encoder.version,
            schema_version,
        )
        self.logger = RetrievalLogger(
            log_path,
            model_version=encoder.version,
            schema_version=schema_version,
            index_hash=self.index_hash,
            session_id=session_id,
            agent=agent,
        )
        self.case_ids = frozenset(chunk.case_id for chunk in self.chunks)

    def save(self, path: Path = DEFAULT_INDEX_PATH) -> None:
        payload = {
            "format_version": 1,
            "schema_version": self.schema_version,
            "model_name": self.encoder.model_name,
            "model_version": self.encoder.version,
            "index_hash": self.index_hash,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "vectors": self.vectors,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                encoding="utf-8",
            )
            temporary_path.replace(path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    @classmethod
    def load(
        cls,
        path: Path = DEFAULT_INDEX_PATH,
        *,
        encoder: Encoder | None = None,
        log_path: Path = DEFAULT_LOG_PATH,
        session_id: str | None = None,
        agent: str = "unknown",
    ) -> "RAGIndex":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("format_version") != 1:
            raise ValueError(f"Formato de índice no compatible: {payload.get('format_version')!r}.")

        active_encoder = encoder or SentenceTransformerEncoder(payload["model_name"])
        if active_encoder.model_name != payload["model_name"]:
            raise ValueError("El modelo configurado no coincide con el modelo que creó el índice.")
        if active_encoder.version != payload["model_version"]:
            raise ValueError("La versión del codificador no coincide con la que creó el índice.")
        chunks = [Chunk.from_dict(item) for item in payload["chunks"]]
        vectors = payload["vectors"]
        expected_hash = _index_hash(
            chunks,
            vectors,
            payload["model_name"],
            payload["model_version"],
            payload["schema_version"],
        )
        if expected_hash != payload["index_hash"]:
            raise ValueError("El índice está corrupto: no coincide su hash de integridad.")
        return cls(
            chunks,
            vectors,
            encoder=active_encoder,
            schema_version=payload["schema_version"],
            index_hash=expected_hash,
            log_path=log_path,
            session_id=session_id,
            agent=agent,
        )

    def search(
        self,
        query: str,
        *,
        case_id: str,
        allowed_evidence_ids: Sequence[str] | None = None,
        owner: str | None = None,
        category: str | None = None,
        top_k: int = 3,
        min_score: float = 0.35,
    ) -> list[dict[str, Any]]:
        from rag.config import CATEGORIES, OWNERS

        self._validate_query(query)
        if not isinstance(case_id, str) or not CASE_ID_PATTERN.fullmatch(case_id):
            raise ValueError("case_id es obligatorio y debe tener formato AAAA-000.")
        if case_id not in self.case_ids:
            raise ValueError(f"El caso {case_id!r} no existe en este índice.")
        if owner is not None and (not isinstance(owner, str) or owner not in OWNERS):
            raise ValueError(f"owner inválido: {owner!r}.")
        if category is not None and (not isinstance(category, str) or category not in CATEGORIES):
            raise ValueError(f"category inválida: {category!r}.")
        self._validate_search_parameters(top_k, min_score)
        if allowed_evidence_ids is not None:
            if isinstance(allowed_evidence_ids, (str, bytes)) or any(
                not isinstance(item, str) for item in allowed_evidence_ids
            ):
                raise ValueError("allowed_evidence_ids debe ser una secuencia de strings.")
            allowed = set(allowed_evidence_ids)
            case_evidence_ids = {
                chunk.evidence_id
                for chunk in self.chunks
                if chunk.case_id == case_id and chunk.evidence_id
            }
            invalid_ids = sorted(allowed - case_evidence_ids)
            if invalid_ids:
                raise ValueError(
                    f"allowed_evidence_ids contiene datos inexistentes o ajenos a {case_id}: "
                    f"{', '.join(invalid_ids)}."
                )
        else:
            allowed = None

        candidate_indices = [
            index
            for index, chunk in enumerate(self.chunks)
            if chunk.case_id == case_id
            and chunk.source == "public"
            and (owner is None or chunk.owner == owner)
            and (category is None or chunk.category == category)
        ]
        if allowed:
            candidate_indices.extend(
                index
                for index, chunk in enumerate(self.chunks)
                if chunk.case_id == case_id
                and chunk.source == "on_request"
                and chunk.evidence_id in allowed
                and (owner is None or chunk.owner == owner)
                and (category is None or chunk.category == category)
            )

        results = self._rank(query, candidate_indices, top_k, min_score)
        self.logger.record(
            query=query,
            filters={
                "case_id": case_id,
                "specialty": None,
                "owner": owner,
                "category": category,
                "allowed_evidence_ids": sorted(allowed) if allowed is not None else None,
            },
            top_k=top_k,
            results=results,
        )
        return results

    def search_cases(
        self,
        query: str,
        *,
        specialty: str,
        top_k: int = 5,
        min_score: float = 0.35,
    ) -> list[dict[str, Any]]:
        from rag.config import SPECIALTIES

        self._validate_query(query)
        if not isinstance(specialty, str) or specialty not in SPECIALTIES:
            raise ValueError(f"specialty inválida: {specialty!r}.")
        self._validate_search_parameters(top_k, min_score)
        candidate_indices = [
            index
            for index, chunk in enumerate(self.chunks)
            if chunk.specialty == specialty and chunk.source in ("public", "catalog")
        ]
        results = self._rank(query, candidate_indices, top_k, min_score)
        self.logger.record(
            query=query,
            filters={
                "case_id": None,
                "specialty": specialty,
                "owner": None,
                "category": None,
            },
            top_k=top_k,
            results=results,
        )
        return results

    def _rank(
        self,
        query: str,
        candidate_indices: Sequence[int],
        top_k: int,
        min_score: float,
    ) -> list[dict[str, Any]]:
        if not candidate_indices:
            return []
        query_vectors = self.encoder.encode([f"query: {query}"])
        if len(query_vectors) != 1:
            raise ValueError("El codificador debe producir un embedding por consulta.")
        query_vector = query_vectors[0]
        if not query_vector or any(not math.isfinite(value) for value in query_vector):
            raise ValueError("El codificador produjo un embedding vacío o no finito.")

        scored = []
        for index in candidate_indices:
            vector = self.vectors[index]
            score = _cosine_similarity(query_vector, vector)
            if score >= min_score:
                scored.append((score, self.chunks[index]))

        scored.sort(key=lambda result: (-result[0], result[1].evidence_id, result[1].chunk_id))
        return [
            {
                **chunk.to_dict(),
                "evidence_id": chunk.evidence_id or None,
                "score": score,
            }
            for score, chunk in scored[:top_k]
        ]

    @staticmethod
    def _validate_query(query: str) -> None:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("La consulta debe ser un texto no vacío.")

    @staticmethod
    def _validate_search_parameters(top_k: int, min_score: float) -> None:
        if isinstance(top_k, bool) or not isinstance(top_k, int) or top_k < 1:
            raise ValueError("top_k debe ser un entero positivo.")
        if isinstance(min_score, bool) or not isinstance(min_score, (int, float)):
            raise ValueError("min_score debe ser numérico.")
        if not math.isfinite(min_score) or not -1 <= min_score <= 1:
            raise ValueError("min_score debe estar entre -1 y 1.")


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise ValueError("El embedding de consulta no tiene la dimensión del índice.")
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return sum(a * b for a, b in zip(left, right)) / (left_norm * right_norm)


def build_index(
    case_paths: Sequence[Path],
    *,
    schema_path: Path,
    include_statuses: Sequence[str] = DEFAULT_INCLUDE_STATUSES,
    encoder: Encoder | None = None,
    log_path: Path = DEFAULT_LOG_PATH,
) -> BuildReport:
    requested_statuses = tuple(include_statuses)
    if not requested_statuses or len(set(requested_statuses)) != len(requested_statuses):
        raise ValueError("include_statuses debe contener estados únicos.")
    invalid_statuses = set(requested_statuses) - set(ALLOWED_STATUSES)
    if invalid_statuses:
        raise ValueError(f"Estados de caso inválidos: {sorted(invalid_statuses)}.")
    if "rechazado" in requested_statuses:
        raise ValueError("Los casos rechazados nunca pueden entrar al índice.")

    validator = CaseSchemaValidator(schema_path)
    chunks: list[Chunk] = []
    skipped: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    seen_case_ids: set[str] = set()
    seen_evidence_ids: set[str] = set()
    schema_version = "1.0.0"

    for case_path in sorted(Path(path) for path in case_paths):
        try:
            case = json.loads(case_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            skipped.append({"file": case_path.name, "reason": f"JSON inválido o inaccesible: {exc}"})
            continue
        if not isinstance(case, dict):
            skipped.append({"file": case_path.name, "reason": "La raíz del caso debe ser un objeto JSON."})
            continue

        validation_errors = validator.validate(case)
        if validation_errors:
            skipped.append({"file": case_path.name, "reason": " | ".join(validation_errors)})
            continue

        case_id = case["case_id"]
        if not CASE_ID_PATTERN.fullmatch(case_id):
            skipped.append({"file": case_path.name, "reason": f"case_id inválido: {case_id!r}."})
            continue
        version = case["schema_version"]
        if not re.fullmatch(r"1\.\d+\.\d+", version):
            skipped.append({"file": case_path.name, "reason": f"schema_version fuera de 1.x.x: {version!r}."})
            continue
        if case_id in seen_case_ids:
            skipped.append({"file": case_path.name, "reason": f"case_id duplicado: {case_id}."})
            continue

        evidence_ids = _case_evidence_ids(case)
        if len(evidence_ids) != len(set(evidence_ids)):
            skipped.append({"file": case_path.name, "reason": "El caso contiene evidence_id duplicados."})
            continue
        mismatched = [
            evidence_id
            for evidence_id in evidence_ids
            if not EVIDENCE_ID_PATTERN.fullmatch(evidence_id)
            or not evidence_id.startswith(f"{case_id}.")
        ]
        if mismatched:
            skipped.append(
                {
                    "file": case_path.name,
                    "reason": f"evidence_id inválido o ajeno a {case_id}: {', '.join(mismatched)}.",
                }
            )
            continue
        duplicates = sorted(set(evidence_ids) & seen_evidence_ids)
        if duplicates:
            skipped.append(
                {"file": case_path.name, "reason": f"evidence_id duplicado: {', '.join(duplicates)}."}
            )
            continue

        status_value = case["status"]
        if status_value not in requested_statuses:
            skipped.append(
                {
                    "file": case_path.name,
                    "reason": f"status {status_value!r} fuera de la compuerta {requested_statuses}.",
                }
            )
            continue

        case_chunks, titles = chunk_case(case)
        terms = protected_terms(case)
        leak_findings = []
        for title in titles:
            leak_findings.extend((f"title: {title}", term) for term in exact_leaks(title, terms))
        for chunk in case_chunks:
            leak_findings.extend(
                (f"{chunk.chunk_id}: {chunk.text}", term)
                for term in exact_leaks(chunk.text, terms)
            )
        if leak_findings:
            details = "; ".join(f"{location!r} contiene término protegido {term!r}" for location, term in leak_findings)
            raise BuildError(f"Fuga detectada en {case_id}; se abortó el build: {details}")

        for title in titles:
            for root in shared_roots(title, terms):
                warnings.append(
                    {
                        "case_id": case_id,
                        "chunk_id": f"{case_id}.catalog.title",
                        "reason": f"Raíz compartida {root!r}; requiere revisión manual.",
                    }
                )
        for chunk in case_chunks:
            for root in shared_roots(chunk.text, terms):
                warnings.append(
                    {
                        "case_id": case_id,
                        "chunk_id": chunk.chunk_id,
                        "reason": f"Raíz compartida {root!r}; requiere revisión manual.",
                    }
                )
        seen_case_ids.add(case_id)
        seen_evidence_ids.update(evidence_ids)
        chunks.extend(case_chunks)
        schema_version = version

    active_encoder = encoder or SentenceTransformerEncoder()
    embeddings = (
        active_encoder.encode([f"passage: {chunk.text}" for chunk in chunks])
        if chunks
        else []
    )
    if len(embeddings) != len(chunks):
        raise ValueError("El codificador no produjo un embedding por chunk.")
    for vector in embeddings:
        if not vector or any(not math.isfinite(value) for value in vector):
            raise ValueError("El codificador produjo un embedding vacío o no finito.")

    index = RAGIndex(
        chunks,
        embeddings,
        encoder=active_encoder,
        schema_version=schema_version,
        log_path=log_path,
    )
    return BuildReport(
        index=index,
        indexed_cases=tuple(sorted(seen_case_ids)),
        indexed_chunks=len(chunks),
        skipped=tuple(skipped),
        warnings=tuple(warnings),
    )
