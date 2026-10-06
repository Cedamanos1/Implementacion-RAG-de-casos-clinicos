from pathlib import Path

from app.config import CASES_DIR, SCHEMA_PATH

MODEL_NAME = "intfloat/multilingual-e5-small"
MODEL_VERSION = "intfloat/multilingual-e5-small; sentence-transformers==3.3.1"
DEFAULT_INCLUDE_STATUSES = ("curado",)
ALLOWED_STATUSES = ("borrador", "validado", "curado", "rechazado")
SPECIALTIES = (
    "medicina_interna",
    "pediatria",
    "ginecologia_obstetricia",
    "cirugia_general",
    "emergencias",
)
OWNERS = ("paciente", "medico_asistente", "laboratorio", "radiologia", "especialista")
CATEGORIES = (
    "motivo",
    "sintoma",
    "antecedente",
    "medicacion",
    "signo_vital",
    "anamnesis",
    "examen_fisico",
    "laboratorio",
    "imagen",
    "estudio",
)
DEFAULT_MIN_SCORE = 0.35
DEFAULT_TOP_K = 3
DEFAULT_INDEX_PATH = Path(".rag") / "index.json"
DEFAULT_LOG_PATH = Path(".rag") / "retrieval.jsonl"
