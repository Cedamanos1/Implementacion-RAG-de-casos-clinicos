"""Fail-closed allowlist for content that may be embedded."""

PUBLIC_PATHS = (
    "title (catalog only)",
    "public.patient.age_years",
    "public.patient.sex",
    "public.chief_complaint.label",
    "public.chief_complaint.text/value/unit",
    "public.items[*].label",
    "public.items[*].text/value/unit",
    "public.allergies (only when allergies_recorded is true)",
)

ON_REQUEST_PATHS = (
    "on_request[*].label",
    "on_request[*].text/value/unit",
    "on_request[*].reference_range",
    "on_request[*].interpretation",
)

METADATA_ONLY_PATHS = (
    "case_id",
    "specialty",
    "status",
    "schema_version",
    "public.chief_complaint.evidence_id",
    "public.items[*].evidence_id/category/code",
    "on_request[*].evidence_id/category/code/reveal_policy",
    "source",
    "provenance",
)

NEVER_INDEX_PATHS = (
    "public.patient.alias",
    "on_request[*].asset",
    "public.items[*].asset",
    "protected.*",
    "unknown fields",
)

INTERPRETATIONS = {
    "N": "normal",
    "H": "alto",
    "L": "bajo",
    "A": "anormal",
}
