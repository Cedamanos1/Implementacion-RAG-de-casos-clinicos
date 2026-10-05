from typing import Literal
from pydantic import BaseModel, Field

Specialty = Literal[
    "medicina_interna",
    "pediatria",
    "ginecologia_obstetricia",
    "cirugia_general",
    "emergencias",
]

class HealthResponse(BaseModel):
    status: str = "ok"
    curated_cases: int

class SpecialtyCount(BaseModel):
    specialty: Specialty
    count: int = Field(ge=0)

class SelectCaseRequest(BaseModel):
    specialty: Specialty

class SelectedCaseResponse(BaseModel):
    case_id: str
    title: str
    specialty: Specialty
    public: dict

class PublicCaseResponse(BaseModel):
    case_id: str
    title: str
    specialty: Specialty
    public: dict

class OnRequestIndexItem(BaseModel):
    evidence_id: str
    category: str
    label: str
    owner: str
    mode: str
    requires: list[str]

class RepositoryIssue(BaseModel):
    file: str
    reason: str

class RepositoryStatusResponse(BaseModel):
    loaded_curated_cases: int
    ignored_non_curated_cases: int
    invalid_cases: int
    issues: list[RepositoryIssue]
