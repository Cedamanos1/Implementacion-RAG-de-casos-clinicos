import argparse
import json
from pathlib import Path

from rag.config import (
    ALLOWED_STATUSES,
    CASES_DIR,
    DEFAULT_INDEX_PATH,
    DEFAULT_LOG_PATH,
    SCHEMA_PATH,
)
from rag.indexer import BuildError, build_index


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida y construye el índice RAG local.")
    parser.add_argument("--cases-dir", type=Path, default=CASES_DIR)
    parser.add_argument(
        "--case",
        action="append",
        default=[],
        type=Path,
        help="JSON adicional (repetible), por ejemplo CIR-001.json.",
    )
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_INDEX_PATH)
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG_PATH)
    parser.add_argument(
        "--include-status",
        action="append",
        choices=ALLOWED_STATUSES,
        default=["curado"],
        help="Estado adicional para pruebas/desarrollo; curado es el único valor por defecto.",
    )
    args = parser.parse_args()

    paths = sorted(args.cases_dir.glob("*.json"))
    paths.extend(args.case)
    report = build_index(
        paths,
        schema_path=args.schema,
        include_statuses=tuple(dict.fromkeys(args.include_status)),
        log_path=args.log,
    )
    result = {
        "index": str(args.output) if report.indexed_chunks else None,
        "index_hash": report.index.index_hash,
        "indexed_cases": report.indexed_cases,
        "indexed_chunks": report.indexed_chunks,
        "skipped": report.skipped,
        "warnings": report.warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not report.indexed_chunks:
        raise SystemExit("Build cancelado: no hay chunks indexables.")
    report.index.save(args.output)


if __name__ == "__main__":
    main()
