from dataclasses import asdict, dataclass
from typing import Any

from rag.policy import INTERPRETATIONS


@dataclass(frozen=True)
class Chunk:
    case_id: str
    specialty: str
    chunk_id: str
    evidence_id: str
    category: str
    owner: str
    mode: str
    requires: tuple[str, ...]
    status: str
    source: str
    text: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["requires"] = list(self.requires)
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Chunk":
        result = dict(value)
        result["requires"] = tuple(result["requires"])
        return cls(**result)


def _render(item: dict) -> str:
    label = item["label"].strip()
    if "text" in item:
        rendered = f"{label}: {item['text'].strip()}"
    else:
        rendered = f"{label}: {item['value']} {item['unit']}"

    if item.get("reference_range"):
        rendered += f" (referencia: {item['reference_range']})"
    interpretation = item.get("interpretation")
    if interpretation in INTERPRETATIONS:
        rendered += f", {INTERPRETATIONS[interpretation]}"
    return rendered


def _data_chunk(case: dict, item: dict, *, source: str, owner: str, mode: str, requires: tuple[str, ...]) -> Chunk:
    evidence_id = item["evidence_id"]
    return Chunk(
        case_id=case["case_id"],
        specialty=case["specialty"],
        chunk_id=evidence_id,
        evidence_id=evidence_id,
        category=item["category"],
        owner=owner,
        mode=mode,
        requires=requires,
        status=case["status"],
        source=source,
        text=_render(item),
    )


def chunk_case(case: dict) -> tuple[list[Chunk], list[str]]:
    chunks: list[Chunk] = []
    titles: list[str] = [case["title"]]
    public = case["public"]
    patient = public["patient"]

    chunks.append(
        Chunk(
            case_id=case["case_id"],
            specialty=case["specialty"],
            chunk_id=f"{case['case_id']}.profile",
            evidence_id="",
            category="antecedente",
            owner="public",
            mode="publico",
            requires=(),
            status=case["status"],
            source="public",
            text=f"Perfil del paciente: {patient['age_years']} años, sexo {patient['sex']}.",
        )
    )
    chunks.append(
        Chunk(
            case_id=case["case_id"],
            specialty=case["specialty"],
            chunk_id=f"{case['case_id']}.catalog.title",
            evidence_id="",
            category="motivo",
            owner="public",
            mode="catalogo",
            requires=(),
            status=case["status"],
            source="catalog",
            text=case["title"],
        )
    )
    chunks.append(
        _data_chunk(
            case,
            public["chief_complaint"],
            source="public",
            owner="public",
            mode="publico",
            requires=(),
        )
    )
    for item in public.get("items", []):
        chunks.append(
            _data_chunk(case, item, source="public", owner="public", mode="publico", requires=())
        )

    if public.get("allergies_recorded") is True and public.get("allergies"):
        chunks.append(
            Chunk(
                case_id=case["case_id"],
                specialty=case["specialty"],
                chunk_id=f"{case['case_id']}.allergy.record",
                evidence_id="",
                category="antecedente",
                owner="public",
                mode="publico",
                requires=(),
                status=case["status"],
                source="public",
                text=f"Alergias registradas: {', '.join(public['allergies'])}.",
            )
        )

    for item in case.get("on_request", []):
        reveal_policy = item["reveal_policy"]
        chunks.append(
            _data_chunk(
                case,
                item,
                source="on_request",
                owner=reveal_policy["owner"],
                mode=reveal_policy["mode"],
                requires=tuple(reveal_policy["requires"]),
            )
        )
    return chunks, titles
