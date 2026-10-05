from functools import lru_cache
from app.config import CASES_DIR, SCHEMA_PATH
from app.repository import CaseRepository
from app.validator import CaseSchemaValidator

@lru_cache
def get_validator(): return CaseSchemaValidator(SCHEMA_PATH)

@lru_cache
def get_repository(): return CaseRepository(CASES_DIR, get_validator())
