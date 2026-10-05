import copy
import json
import random
from collections import Counter
from pathlib import Path
from app.validator import CaseSchemaValidator

class CaseNotFoundError(KeyError):
    pass

class NoCasesAvailableError(LookupError):
    pass

class CaseRepository:
    """Repositorio seguro de casos clínicos válidos y curados."""
    def __init__(self, cases_dir: Path, validator: CaseSchemaValidator):
        self.cases_dir = cases_dir
        self.validator = validator
        self._cases: dict[str, dict] = {}
        self._issues: list[dict] = []
        self._ignored_non_curated = 0
        self.reload()

    def reload(self) -> None:
        self._cases.clear(); self._issues.clear(); self._ignored_non_curated = 0
        self.cases_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(self.cases_dir.glob("*.json")):
            try:
                case = json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                self._issues.append({"file": path.name, "reason": f"JSON inválido: {exc}"})
                continue
            errors = self.validator.validate(case)
            if errors:
                self._issues.append({"file": path.name, "reason": " | ".join(errors)})
                continue
            if case["status"] != "curado":
                self._ignored_non_curated += 1
                continue
            case_id = case["case_id"]
            if case_id in self._cases:
                self._issues.append({"file": path.name, "reason": f"case_id duplicado: {case_id}"})
                continue
            self._cases[case_id] = case

    def count(self): return len(self._cases)
    def issues(self): return copy.deepcopy(self._issues)
    def ignored_non_curated_count(self): return self._ignored_non_curated

    def specialties(self):
        counts = Counter(c["specialty"] for c in self._cases.values())
        return [{"specialty": s, "count": counts[s]} for s in sorted(counts)]

    def list_case_metadata(self, specialty: str | None = None):
        cases = list(self._cases.values())
        if specialty:
            cases = [c for c in cases if c["specialty"] == specialty]
        return [{"case_id": c["case_id"], "title": c["title"], "specialty": c["specialty"], "status": c["status"]}
                for c in sorted(cases, key=lambda x: x["case_id"])]

    def select_random(self, specialty: str, rng: random.Random | None = None):
        available = [c for c in self._cases.values() if c["specialty"] == specialty]
        if not available:
            raise NoCasesAvailableError(f"No hay casos curados disponibles para la especialidad '{specialty}'.")
        chooser = rng or random.SystemRandom()
        return self._safe_selected_case(chooser.choice(available))

    def get_public(self, case_id: str):
        c = self._get_case(case_id)
        return {"case_id": c["case_id"], "title": c["title"], "specialty": c["specialty"], "public": copy.deepcopy(c["public"])}

    def get_on_request_index(self, case_id: str):
        c = self._get_case(case_id)
        result = []
        for item in c["on_request"]:
            p = item["reveal_policy"]
            result.append({
                "evidence_id": item["evidence_id"], "category": item["category"], "label": item["label"],
                "owner": p["owner"], "mode": p["mode"], "requires": copy.deepcopy(p["requires"])
            })
        return result

    def get_internal_case(self, case_id: str):
        return copy.deepcopy(self._get_case(case_id))

    def _get_case(self, case_id: str):
        try: return self._cases[case_id]
        except KeyError as exc: raise CaseNotFoundError(case_id) from exc

    @staticmethod
    def _safe_selected_case(c):
        return {"case_id": c["case_id"], "title": c["title"], "specialty": c["specialty"], "public": copy.deepcopy(c["public"])}
