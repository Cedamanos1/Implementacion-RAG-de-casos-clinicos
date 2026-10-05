from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)

def test_health():
    r=client.get("/health"); assert r.status_code==200; assert r.json()["curated_cases"]==1

def test_specialties():
    r=client.get("/api/v1/specialties"); assert r.status_code==200; assert r.json()==[{"specialty":"emergencias","count":1}]

def test_select_case():
    r=client.post("/api/v1/cases/select",json={"specialty":"emergencias"}); assert r.status_code==200; assert r.json()["case_id"]=="CARD-001"; assert "protected" not in r.json()

def test_public_endpoint_never_returns_protected():
    r=client.get("/api/v1/cases/CARD-001/public"); assert r.status_code==200; assert "protected" not in r.json(); assert "on_request" not in r.json()

def test_non_curated_case_is_not_accessible():
    assert client.get("/api/v1/cases/CARD-002/public").status_code==404
