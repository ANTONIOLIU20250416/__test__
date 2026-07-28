"""Compares extracted MTR values against the material spec library."""
from typing import Optional

from sqlmodel import Session, select

from .models import MaterialSpec, Verdict

WARNING_BAND = 0.05  # within 5% of a limit boundary -> WARNING instead of PASS


def find_matching_spec(session: Session, alloy_code: Optional[str], standard: Optional[str]) -> Optional[MaterialSpec]:
    if not alloy_code:
        return None
    query = select(MaterialSpec).where(MaterialSpec.alloy_code == alloy_code.upper())
    candidates = session.exec(query).all()
    if not candidates:
        return None
    if standard:
        for spec in candidates:
            if spec.standard.upper() == standard.upper():
                return spec
    return candidates[0]


def _check_value(value: Optional[float], limit: dict) -> tuple[str, Optional[float], Optional[float]]:
    if limit.get("remainder"):
        return ("INFO", None, None)
    lo, hi = limit.get("min"), limit.get("max")
    if value is None:
        return ("MISSING", lo, hi)
    if lo is not None and value < lo:
        band = lo * WARNING_BAND
        return ("FAIL" if value < lo - band else "WARNING", lo, hi)
    if hi is not None and value > hi:
        band = hi * WARNING_BAND
        return ("FAIL" if value > hi + band else "WARNING", lo, hi)
    return ("PASS", lo, hi)


def evaluate_compliance(extracted: dict, spec: Optional[MaterialSpec]) -> tuple[str, list[dict]]:
    if spec is None:
        return Verdict.UNVERIFIED, []

    results = []
    chemistry = extracted.get("chemistry", {}) or {}
    for element, limit in spec.chemistry_limits.items():
        status, lo, hi = _check_value(chemistry.get(element), limit)
        results.append({
            "group": "chemistry",
            "parameter": element,
            "value": chemistry.get(element),
            "min": lo,
            "max": hi,
            "status": status,
        })

    mechanical = extracted.get("mechanical", {}) or {}
    for prop, limit in spec.mechanical_limits.items():
        status, lo, hi = _check_value(mechanical.get(prop), limit)
        results.append({
            "group": "mechanical",
            "parameter": prop,
            "value": mechanical.get(prop),
            "min": lo,
            "max": hi,
            "status": status,
        })

    comparable = {r["status"] for r in results if r["status"] != "INFO"}
    if not comparable:
        overall = Verdict.UNVERIFIED
    elif "FAIL" in comparable:
        overall = Verdict.FAIL
    elif "MISSING" in comparable or "WARNING" in comparable:
        overall = Verdict.WARNING
    else:
        overall = Verdict.PASS
    return overall, results
