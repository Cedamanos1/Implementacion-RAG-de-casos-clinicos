from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CASES_DIR = DATA_DIR / "cases"
SCHEMA_PATH = BASE_DIR / "schemas" / "caso.schema.json"
API_PREFIX = "/api/v1"
