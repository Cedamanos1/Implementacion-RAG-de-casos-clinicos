from app.main import app


def test_rag_routes_registered():
    paths = {route.path for route in app.routes}
    assert "/api/v1/rag/health" in paths
    assert "/api/v1/rag/cases/search" in paths
    assert "/api/v1/rag/evidence/search" in paths
    assert "/api/v1/rag/reload" in paths
