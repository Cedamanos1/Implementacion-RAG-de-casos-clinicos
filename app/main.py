from fastapi import Depends, FastAPI, HTTPException, Query, status
from app.config import API_PREFIX
from app.dependencies import get_repository
from app.repository import CaseNotFoundError, CaseRepository, NoCasesAvailableError
from app.schemas import HealthResponse, OnRequestIndexItem, PublicCaseResponse, RepositoryStatusResponse, SelectCaseRequest, SelectedCaseResponse, SpecialtyCount

app = FastAPI(title="Paciente Virtual Adaptativo - EN-002 Repositorio de Casos", version="1.0.0", description="API segura para consultar casos clínicos curados. No expone protected al frontend.")

@app.get("/health", response_model=HealthResponse, tags=["system"])
def health(repo: CaseRepository = Depends(get_repository)):
    return HealthResponse(curated_cases=repo.count())

@app.get(f"{API_PREFIX}/repository/status", response_model=RepositoryStatusResponse, tags=["repository"])
def repository_status(repo: CaseRepository = Depends(get_repository)):
    return {"loaded_curated_cases": repo.count(), "ignored_non_curated_cases": repo.ignored_non_curated_count(), "invalid_cases": len(repo.issues()), "issues": repo.issues()}

@app.post(f"{API_PREFIX}/repository/reload", tags=["repository"])
def reload_repository(repo: CaseRepository = Depends(get_repository)):
    repo.reload()
    return {"message": "Repositorio recargado.", "loaded_curated_cases": repo.count(), "invalid_cases": len(repo.issues())}

@app.get(f"{API_PREFIX}/specialties", response_model=list[SpecialtyCount], tags=["cases"])
def specialties(repo: CaseRepository = Depends(get_repository)):
    return repo.specialties()

@app.get(f"{API_PREFIX}/cases", tags=["cases"])
def list_cases(specialty: str | None = Query(default=None), repo: CaseRepository = Depends(get_repository)):
    return repo.list_case_metadata(specialty=specialty)

@app.post(f"{API_PREFIX}/cases/select", response_model=SelectedCaseResponse, tags=["cases"])
def select_case(payload: SelectCaseRequest, repo: CaseRepository = Depends(get_repository)):
    try: return repo.select_random(payload.specialty)
    except NoCasesAvailableError as exc: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

@app.get(f"{API_PREFIX}/cases/{{case_id}}/public", response_model=PublicCaseResponse, tags=["cases"])
def public_case(case_id: str, repo: CaseRepository = Depends(get_repository)):
    try: return repo.get_public(case_id)
    except CaseNotFoundError as exc: raise HTTPException(status_code=404, detail="Caso no encontrado o no disponible para estudiantes.") from exc

@app.get(f"{API_PREFIX}/cases/{{case_id}}/on-request-index", response_model=list[OnRequestIndexItem], tags=["cases"])
def on_request_index(case_id: str, repo: CaseRepository = Depends(get_repository)):
    try: return repo.get_on_request_index(case_id)
    except CaseNotFoundError as exc: raise HTTPException(status_code=404, detail="Caso no encontrado o no disponible para estudiantes.") from exc
