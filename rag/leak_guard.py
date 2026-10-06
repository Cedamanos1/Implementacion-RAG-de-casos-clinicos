import re
import unicodedata
from collections.abc import Iterable


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    unaccented = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", unaccented))


def protected_terms(case: dict) -> tuple[str, ...]:
    protected = case.get("protected", {})
    terms: set[str] = set()

    diagnosis = protected.get("diagnosis", {})
    terms.add(diagnosis.get("name", ""))
    terms.update(diagnosis.get("synonyms", []))
    terms.add(diagnosis.get("code", {}).get("value", ""))

    for differential in protected.get("differentials", []):
        terms.add(differential.get("name", ""))

    treatment = protected.get("treatment_reference", {})
    terms.add(treatment.get("summary", ""))
    terms.update(treatment.get("key_actions", []))

    for contraindication in protected.get("contraindications", []):
        terms.add(contraindication.get("drug_or_class", ""))
        terms.add(contraindication.get("alternative", ""))

    return tuple(sorted({normalize(term) for term in terms if normalize(term)}))


def exact_leaks(text: str, terms: Iterable[str]) -> list[str]:
    normalized_text = f" {normalize(text)} "
    return [
        term
        for term in terms
        if f" {term} " in normalized_text
    ]


def shared_roots(text: str, terms: Iterable[str]) -> list[str]:
    content_words = set(normalize(text).split())
    roots = set()
    for term in terms:
        for protected_word in term.split():
            if len(protected_word) < 5:
                continue
            for content_word in content_words:
                common = 0
                for left, right in zip(protected_word, content_word):
                    if left != right:
                        break
                    common += 1
                if common >= 5 and protected_word != content_word:
                    roots.add(protected_word[:common])
    return sorted(roots)
