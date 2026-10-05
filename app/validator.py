import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

class CaseSchemaValidator:
    def __init__(self, schema_path: Path):
        self.schema_path = schema_path
        self.schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.validator = Draft202012Validator(self.schema, format_checker=FormatChecker())

    def validate(self, case: dict) -> list[str]:
        errors = sorted(self.validator.iter_errors(case), key=lambda e: list(e.path))
        messages = []
        for err in errors:
            path = ".".join(str(x) for x in err.absolute_path) or "$"
            messages.append(f"{path}: {err.message}")
        return messages
