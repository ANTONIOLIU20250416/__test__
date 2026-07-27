"""Turns a raw Material Test Report (text or PDF) into structured data.

Two extraction paths:
  1. AI path (Claude) — used when ANTHROPIC_API_KEY is set. Robust to
     free-form layouts, multi-language certs, and odd table formats.
  2. Heuristic regex fallback — used when no API key is configured, so the
     platform is still usable end-to-end for a demo/offline environment.
"""
import io
import json
import os
import re
from typing import Optional

from pypdf import PdfReader

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

EXTRACTION_TOOL = {
    "name": "record_mtr_data",
    "description": "Record structured data extracted from a material test report / mill certificate.",
    "input_schema": {
        "type": "object",
        "properties": {
            "heat_number": {"type": ["string", "null"]},
            "alloy_code": {"type": ["string", "null"], "description": "e.g. C46400, C3604"},
            "standard": {"type": ["string", "null"], "description": "e.g. ASTM B124, JIS H3250"},
            "part_number": {"type": ["string", "null"]},
            "chemistry": {
                "type": "object",
                "description": "Element symbol -> weight percent, e.g. {\"Cu\": 60.5, \"Pb\": 0.15}",
                "additionalProperties": {"type": "number"},
            },
            "mechanical": {
                "type": "object",
                "description": (
                    "Property -> value in SI units. Keys limited to: "
                    "tensile_strength_mpa, yield_strength_mpa, elongation_pct, hardness_hb"
                ),
                "additionalProperties": {"type": "number"},
            },
        },
        "required": ["chemistry", "mechanical"],
    },
}

KSI_TO_MPA = 6.89476

ELEMENT_SYMBOLS = ["Cu", "Zn", "Pb", "Sn", "Fe", "Ni", "Mn", "Al", "Si", "P", "S", "C", "Cr", "Mo"]


def pdf_bytes_to_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_mtr_data(text: str) -> tuple[dict, str]:
    """Returns (extracted_dict, method) where method is 'ai' or 'heuristic'."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            return _extract_with_ai(text), "ai"
        except Exception as exc:  # network/SDK issues fall back gracefully
            data = _extract_heuristic(text)
            data["_ai_error"] = str(exc)
            return data, "heuristic"
    return _extract_heuristic(text), "heuristic"


def _extract_with_ai(text: str) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_mtr_data"},
        messages=[
            {
                "role": "user",
                "content": (
                    "Extract structured data from this Material Test Report / mill "
                    "certificate for a copper alloy or cast/ductile iron plumbing "
                    "component. Chemistry values are weight percent. Convert any "
                    "imperial mechanical units (ksi) to MPa. Only include elements "
                    "and properties actually present in the document.\n\n"
                    f"--- DOCUMENT TEXT ---\n{text[:12000]}"
                ),
            }
        ],
    )
    for block in message.content:
        if block.type == "tool_use" and block.name == "record_mtr_data":
            return block.input
    raise RuntimeError("Model did not return structured tool output")


def _extract_heuristic(text: str) -> dict:
    chemistry: dict[str, float] = {}
    for el in ELEMENT_SYMBOLS:
        m = re.search(rf"\b{el}\b[\s:.]{{0,5}}([0-9]+\.?[0-9]*)\s*%?", text)
        if m:
            chemistry[el] = float(m.group(1))

    mechanical: dict[str, float] = {}
    mechanical.update(_find_mechanical(text, r"tensile\s*strength", "tensile_strength_mpa"))
    mechanical.update(_find_mechanical(text, r"yield\s*strength", "yield_strength_mpa"))
    elong = re.search(r"elongation[\s:.]{0,10}([0-9]+\.?[0-9]*)\s*%", text, re.I)
    if elong:
        mechanical["elongation_pct"] = float(elong.group(1))
    hardness = re.search(r"hardness[\s:.]{0,10}([0-9]+\.?[0-9]*)\s*HB", text, re.I)
    if hardness:
        mechanical["hardness_hb"] = float(hardness.group(1))

    heat = re.search(r"heat\s*(?:/\s*lot)?\s*(?:no\.?|number)?[\s:.]{0,5}([A-Za-z0-9\-]+)", text, re.I)
    alloy = re.search(r"\b(?:UNS\s*)?(C\d{3,5}|C\d{2}00)\b", text)
    standard = re.search(r"\b(ASTM\s*[A-Z]\d+|JIS\s*[A-Z]\d+|CNS\s*\d+)\b", text, re.I)
    part = re.search(r"part\s*(?:no\.?|number)[\s:.]{0,5}([A-Za-z0-9\-]+)", text, re.I)

    return {
        "heat_number": heat.group(1) if heat else None,
        "alloy_code": alloy.group(1).upper() if alloy else None,
        "standard": standard.group(1).upper() if standard else None,
        "part_number": part.group(1) if part else None,
        "chemistry": chemistry,
        "mechanical": mechanical,
    }


def _find_mechanical(text: str, label_pattern: str, key: str) -> dict:
    m = re.search(label_pattern + r"[\s:.]{0,10}([0-9]+\.?[0-9]*)\s*(mpa|ksi)?", text, re.I)
    if not m:
        return {}
    value = float(m.group(1))
    unit = (m.group(2) or "mpa").lower()
    if unit == "ksi":
        value *= KSI_TO_MPA
    return {key: round(value, 1)}
