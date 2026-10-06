import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class RetrievalLogger:
    def __init__(
        self,
        path: Path,
        *,
        model_version: str,
        schema_version: str,
        index_hash: str,
        session_id: str | None = None,
        agent: str = "unknown",
    ):
        self.path = path
        self.model_version = model_version
        self.schema_version = schema_version
        self.index_hash = index_hash
        self.session_id = session_id
        self.agent = agent
        self._lock = threading.Lock()

    def record(
        self,
        *,
        query: str,
        filters: dict[str, Any],
        top_k: int,
        results: list[dict[str, Any]],
    ) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "agent": self.agent,
            "query": query,
            "filters": filters,
            "top_k": top_k,
            "results": [
                {
                    "case_id": result["case_id"],
                    "evidence_id": result["evidence_id"],
                    "score": result["score"],
                    "rank": rank,
                }
                for rank, result in enumerate(results, start=1)
            ],
            "model_version": self.model_version,
            "schema_version": self.schema_version,
            "index_hash": self.index_hash,
        }
        line = json.dumps(entry, ensure_ascii=False, sort_keys=True)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as log_file:
                log_file.write(line + "\n")
