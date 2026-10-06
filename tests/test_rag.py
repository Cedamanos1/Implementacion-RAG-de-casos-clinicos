import hashlib
import json
import re
from pathlib import Path

import pytest

from rag.indexer import BuildError, RAGIndex, build_index

ROOT = Path(__file__).resolve().parents[1]
CARD_PATH = ROOT / "data" / "cases" / "CARD-001.json"
CIR_PATH = ROOT / "CIR-001.json"
SCHEMA_PATH = ROOT / "schemas" / "caso.schema.json"


class TestEncoder:
    model_name = "test-hash-encoder"
    version = "test-1"

    def encode(self, texts):
        vectors = []
        for text in texts:
            vector = [0.0] * 128
            for token in re.findall(r"[a-z0-9]+", text.casefold()):
                slot = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % len(vector)
                vector[slot] += 1.0
            norm = sum(value * value for value in vector) ** 0.5
            vectors.append([value / norm for value in vector] if norm else vector)
        return vectors


def load_case(path):
    return json.loads(path.read_text(encoding="utf-8"))


def make_index(tmp_path, *, include_statuses=("curado",), paths=None):
    return build_index(
        paths or [CARD_PATH, CIR_PATH],
        schema_path=SCHEMA_PATH,
        include_statuses=include_statuses,
        encoder=TestEncoder(),
        log_path=tmp_path / "retrieval.jsonl",
    )


def test_only_curated_cases_are_indexed_by_default(tmp_path):
    report = make_index(tmp_path)
    assert report.indexed_cases == ("CARD-001",)
    assert any("status 'borrador'" in issue["reason"] for issue in report.skipped)


def test_development_gate_can_include_real_draft_case(tmp_path):
    report = make_index(tmp_path, include_statuses=("curado", "borrador"))
    assert report.indexed_cases == ("CARD-001", "CIR-001")
    assert any(item["case_id"] == "CIR-001" for item in report.warnings)


def test_index_contains_only_allowlisted_fields_and_not_alias_or_protected(tmp_path):
    report = make_index(tmp_path, include_statuses=("curado", "borrador"))
    texts = " ".join(chunk.text.casefold() for chunk in report.index.chunks)
    assert "roberto vargas" not in texts
    assert "mateo s." not in texts
    assert "infarto agudo de miocardio" not in texts
    assert "apendicitis aguda" not in texts
    assert "apendice no compresible" in texts


@pytest.mark.parametrize(
    ("mutate", "leaked_term"),
    [
        (
            lambda case: case["public"]["chief_complaint"].update(
                text="Diagnóstico: Infarto agudo de miocardio con elevación del ST"
            ),
            "infarto agudo de miocardio con elevacion del st",
        ),
        (
            lambda case: case["on_request"][0].update(text="El paciente tiene IAMCEST."),
            "iamcest",
        ),
        (
            lambda case: case["public"]["items"][0].update(
                label="Manejo inicial de síndrome coronario agudo según protocolo institucional"
            ),
            "manejo inicial de sindrome coronario agudo segun protocolo institucional",
        ),
        (
            lambda case: case.update(title="Infarto agudo de miocardio con elevación del ST"),
            "infarto agudo de miocardio con elevacion del st",
        ),
    ],
)
def test_protected_term_leaks_abort_the_build(tmp_path, mutate, leaked_term):
    case = load_case(CARD_PATH)
    mutate(case)
    path = tmp_path / "leaking.json"
    path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(BuildError, match="Fuga detectada"):
        make_index(tmp_path, paths=[path])


def test_evidence_id_must_belong_to_case(tmp_path):
    case = load_case(CARD_PATH)
    case["on_request"][0]["evidence_id"] = "CIR-001.lab.troponina"
    path = tmp_path / "wrong-evidence.json"
    path.write_text(json.dumps(case), encoding="utf-8")
    report = make_index(tmp_path, paths=[path])
    assert not report.indexed_cases
    assert "ajeno a CARD-001" in report.skipped[0]["reason"]


def test_schema_invalid_and_non_curated_cases_are_skipped(tmp_path):
    case = load_case(CARD_PATH)
    case["specialty"] = "especialidad_inventada"
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(case), encoding="utf-8")
    report = make_index(tmp_path, paths=[invalid_path, CIR_PATH])
    assert not report.indexed_cases
    assert len(report.skipped) == 2


def test_search_requires_case_id_and_never_crosses_cases(tmp_path):
    report = make_index(tmp_path, include_statuses=("curado", "borrador"))
    with pytest.raises(ValueError, match="case_id es obligatorio"):
        report.index.search("dolor", case_id="")
    results = report.index.search("dolor abdominal", case_id="CIR-001", min_score=-1)
    assert results
    assert {result["case_id"] for result in results} == {"CIR-001"}


def test_on_request_evidence_is_hidden_until_engine_allows_it(tmp_path):
    report = make_index(tmp_path)
    hidden_id = "CARD-001.lab.troponina_t"
    locked = report.index.search("troponina elevada", case_id="CARD-001", top_k=20)
    unlocked = report.index.search(
        "troponina elevada",
        case_id="CARD-001",
        allowed_evidence_ids=[hidden_id],
        top_k=20,
        min_score=-1,
    )
    assert hidden_id not in {item["evidence_id"] for item in locked}
    assert hidden_id in {item["evidence_id"] for item in unlocked}
    with pytest.raises(ValueError, match="inexistentes o ajenos"):
        report.index.search(
            "troponina",
            case_id="CARD-001",
            allowed_evidence_ids=["CIR-001.lab.inexistente"],
        )


def test_owner_category_and_specialty_filters_are_validated_and_applied(tmp_path):
    report = make_index(tmp_path, include_statuses=("curado", "borrador"))
    index = report.index
    allowed = ["CARD-001.lab.troponina_t", "CARD-001.estudio.ecg"]
    results = index.search(
        "troponina",
        case_id="CARD-001",
        allowed_evidence_ids=allowed,
        owner="laboratorio",
        category="laboratorio",
        min_score=-1,
    )
    assert results
    assert all(result["owner"] == "laboratorio" for result in results)
    assert all(result["category"] == "laboratorio" for result in results)
    with pytest.raises(ValueError, match="owner inválido"):
        index.search("dolor", case_id="CARD-001", owner="desconocido")
    with pytest.raises(ValueError, match="category inválida"):
        index.search("dolor", case_id="CARD-001", category="diagnostico")
    with pytest.raises(ValueError, match="specialty inválida"):
        index.search_cases("dolor", specialty="cardiologia")
    catalog = index.search_cases("dolor", specialty="emergencias", min_score=-1)
    assert catalog
    assert {item["case_id"] for item in catalog} == {"CARD-001"}


def test_allergies_are_never_inferred_from_false_recorded_flag(tmp_path):
    report = make_index(tmp_path)
    allergy_ids = {
        chunk.evidence_id
        for chunk in report.index.chunks
        if "alerg" in chunk.text.casefold()
    }
    assert not allergy_ids
    results = report.index.search(
        "alergia",
        case_id="CARD-001",
        allowed_evidence_ids=[],
        top_k=20,
        min_score=-1,
    )
    assert all("alerg" not in result["text"].casefold() for result in results)


def test_explicitly_recorded_public_allergies_are_indexed(tmp_path):
    case = load_case(CARD_PATH)
    case["public"]["allergies_recorded"] = True
    case["public"]["allergies"] = ["Látex"]
    path = tmp_path / "allergies.json"
    path.write_text(json.dumps(case, ensure_ascii=False), encoding="utf-8")
    report = make_index(tmp_path, paths=[path])
    allergy_chunks = [chunk for chunk in report.index.chunks if "látex" in chunk.text.casefold()]
    assert len(allergy_chunks) == 1
    assert allergy_chunks[0].evidence_id == ""


def test_retrieval_order_and_scores_are_deterministic_and_logged(tmp_path):
    report = make_index(tmp_path)
    first = report.index.search("dificultad respiratoria", case_id="CARD-001", min_score=-1)
    second = report.index.search("dificultad respiratoria", case_id="CARD-001", min_score=-1)
    assert [(row["evidence_id"], row["score"]) for row in first] == [
        (row["evidence_id"], row["score"]) for row in second
    ]
    report.index.search_cases("dolor torácico", specialty="emergencias", min_score=-1)
    lines = (tmp_path / "retrieval.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    record = json.loads(lines[0])
    assert record["index_hash"] == report.index.index_hash
    assert record["results"][0]["rank"] == 1
    assert record["model_version"] == "test-1"
    catalog_record = json.loads(lines[2])
    assert catalog_record["filters"]["specialty"] == "emergencias"


def test_saved_index_integrity_and_reload(tmp_path):
    report = make_index(tmp_path)
    path = tmp_path / "index.json"
    report.index.save(path)
    loaded = RAGIndex.load(path, encoder=TestEncoder(), log_path=tmp_path / "loaded.jsonl")
    assert loaded.index_hash == report.index.index_hash
    assert loaded.search("disnea", case_id="CARD-001", min_score=-1)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["chunks"][0]["text"] = "alterado"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="corrupto"):
        RAGIndex.load(path, encoder=TestEncoder())
