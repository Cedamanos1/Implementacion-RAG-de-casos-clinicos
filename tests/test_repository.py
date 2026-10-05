import random
from pathlib import Path
from app.repository import CaseRepository
from app.validator import CaseSchemaValidator
ROOT = Path(__file__).resolve().parents[1]

def make_repo(): return CaseRepository(ROOT/"data"/"cases", CaseSchemaValidator(ROOT/"schemas"/"caso.schema.json"))

def test_only_curated_cases_are_loaded():
    r=make_repo(); assert r.count()==1; assert r.ignored_non_curated_count()==1

def test_specialties_returns_only_loaded_cases():
    assert make_repo().specialties()==[{"specialty":"emergencias","count":1}]

def test_select_random_returns_safe_payload_without_protected():
    x=make_repo().select_random("emergencias", rng=random.Random(1)); assert x["case_id"]=="CARD-001"; assert "protected" not in x; assert "on_request" not in x

def test_public_case_does_not_expose_protected():
    x=make_repo().get_public("CARD-001"); assert "protected" not in x; assert "on_request" not in x

def test_on_request_index_exposes_policy_but_not_clinical_values():
    xs=make_repo().get_on_request_index("CARD-001"); assert len(xs)==2
    for x in xs: assert "value" not in x and "text" not in x and "owner" in x and "requires" in x

def test_internal_case_contains_protected_for_trusted_backend_components():
    assert "protected" in make_repo().get_internal_case("CARD-001")
