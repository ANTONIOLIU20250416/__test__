"""Turns a raw Material Test Report (text or PDF) into structured data.

Two extraction paths:
  1. AI path (Claude) — used when ANTHROPIC_API_KEY is set. Robust to
     free-form layouts, multi-language certs, and odd table formats.
  2. Heuristic regex fallback — used when no API key is configured, so the
     platform is still usable end-to-end for a demo/offline environment.
"""
import base64
import io
import os
import re
from typing import Optional

from pypdf import PdfReader

MAX_VISION_PAGES = 5  # cap per-request image count to bound cost on multi-page scans

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

# Recognized element/impurity symbols for table-header detection - a superset of
# ELEMENT_SYMBOLS since certs in the wild (stainless, cast iron, carbon steel)
# use more than the copper-alloy-focused list above.
KNOWN_TABLE_ELEMENTS = {
    "Cu", "Zn", "Pb", "Sn", "Fe", "Ni", "Mn", "Al", "Si", "P", "S", "C", "Cr", "Mo",
    "As", "Bi", "Cd", "Hg", "Sb", "Zr", "V", "Nb", "Ti", "W", "Co", "N", "Ca", "Mg", "Imp.",
}
MECHANICAL_UNIT_KEYS = {"mpa": "tensile_strength_mpa", "%": "elongation_pct",
                         "hrb": "hardness_hb", "hb": "hardness_hb", "hrc": "hardness_hb", "hv": "hardness_hb"}


def pdf_bytes_to_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def docx_bytes_to_text(data: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(data))
    lines = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            lines.append(" ".join(cell.text for cell in row.cells))
    return "\n".join(lines)


def extract_mtr_data(text: str, allow_ai: bool = False) -> tuple[dict, str]:
    """Returns (extracted_dict, method) where method is 'ai' or 'heuristic'.

    `allow_ai` is opt-in and False by default: structuring the already-local
    (native-text or OCR'd) document text is done by the free regex parser
    unless the caller explicitly asks to spend API tokens on the Claude path.
    """
    if allow_ai and os.environ.get("ANTHROPIC_API_KEY"):
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


def extract_mtr_data_from_images(images: list) -> dict:
    """Sends page image(s) straight to Claude's vision — for scans/photos where
    local OCR text came out wrong or unusable. Requires ANTHROPIC_API_KEY and
    is opt-in only: this spends more tokens than the text-based AI path since
    images cost more than the text OCR would have produced."""
    import anthropic

    client = anthropic.Anthropic()
    content = []
    for image in images[:MAX_VISION_PAGES]:
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="PNG")
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": base64.b64encode(buf.getvalue()).decode()},
        })
    content.append({
        "type": "text",
        "text": (
            "Extract structured data from this Material Test Report / mill "
            "certificate image for a copper alloy or cast/ductile iron plumbing "
            "component. Chemistry values are weight percent. Convert any "
            "imperial mechanical units (ksi) to MPa. Only include elements and "
            "properties actually visible in the document."
        ),
    })
    message = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "record_mtr_data"},
        messages=[{"role": "user", "content": content}],
    )
    for block in message.content:
        if block.type == "tool_use" and block.name == "record_mtr_data":
            return block.input
    raise RuntimeError("Model did not return structured tool output")


def _is_number(token: str) -> bool:
    try:
        float(token.strip("”\"'"))
        return True
    except ValueError:
        return False


def _extract_table_chemistry(lines: list[list[str]]) -> tuple[dict, Optional[str]]:
    """Real-world MTRs (e.g. Legend's own PO/commodity template) lay out
    chemistry as a table: an element-symbol header row, a '%' unit row, a
    limits row (≤/≥/range), then one or more data rows. Linear PDF text
    extraction keeps each row on its own line but destroys the visual column
    alignment, so element name and value are far apart - a per-element regex
    can't find them. This scans for that structure positionally instead."""
    for i, tokens in enumerate(lines):
        # Header row may be prefixed with non-element columns on the same line
        # (docx tables keep "Size Heat No. Qty" and the element symbols on one
        # row; PDF text extraction usually splits them onto separate lines) -
        # so look at the trailing run of tokens that are all known elements.
        run_start = len(tokens)
        while run_start > 0 and tokens[run_start - 1] in KNOWN_TABLE_ELEMENTS:
            run_start -= 1
        headers = tokens[run_start:]
        if len(headers) >= 2:
            for row in lines[i + 1: i + 8]:
                if len(row) >= len(headers):
                    tail = row[-len(headers):]
                    if all(_is_number(t) for t in tail):
                        chemistry = {h: float(v) for h, v in zip(headers, tail)}
                        heat_number = row[-len(headers) - 2] if len(row) >= len(headers) + 2 else None
                        return chemistry, heat_number
    return {}, None


def _extract_table_mechanical(lines: list[list[str]]) -> dict:
    """Same idea as _extract_table_chemistry but for the Tensile/Yield/
    Elongation/Hardness/Heat-Treatment table. Column meaning is read off the
    units row (MPa, MPa, %, HRB, °C, ...) rather than the wrapped multi-line
    headers, since PDF text extraction wraps those inconsistently."""
    for i, tokens in enumerate(lines):
        lowered = [t.lower().lstrip("≤≥") for t in tokens]
        if lowered.count("mpa") >= 1 and any(u in lowered for u in MECHANICAL_UNIT_KEYS if u != "mpa"):
            keys = []
            mpa_seen = 0
            for u in lowered:
                if u == "mpa":
                    mpa_seen += 1
                    keys.append("tensile_strength_mpa" if mpa_seen == 1 else "yield_strength_mpa")
                else:
                    keys.append(MECHANICAL_UNIT_KEYS.get(u))
            for row in lines[i + 1: i + 6]:
                if len(row) >= len(keys):
                    tail = row[-len(keys):]
                    if all(_is_number(t) for t in tail):
                        return {k: float(v) for k, v in zip(keys, tail) if k}
    return {}


def _extract_heuristic(text: str) -> dict:
    lines = [line.split() for line in text.splitlines()]

    chemistry, table_heat_number = _extract_table_chemistry(lines)
    mechanical = _extract_table_mechanical(lines)

    if not chemistry:
        # Fall back to the simple "label directly followed by a number" style
        # (e.g. "Cu 60.5") used by hand-typed or non-tabular certificates.
        for el in ELEMENT_SYMBOLS:
            m = re.search(rf"\b{el}\b[\s:.]{{0,5}}([0-9]+\.?[0-9]*)\s*%?", text)
            if m:
                chemistry[el] = float(m.group(1))

    if not mechanical:
        mechanical.update(_find_mechanical(text, r"tensile\s*strength", "tensile_strength_mpa"))
        mechanical.update(_find_mechanical(text, r"yield\s*strength", "yield_strength_mpa"))
        elong = re.search(r"elongation[\s:.]{0,10}([0-9]+\.?[0-9]*)\s*%", text, re.I)
        if elong:
            mechanical["elongation_pct"] = float(elong.group(1))
        hardness = re.search(r"hardness[\s:.]{0,10}([0-9]+\.?[0-9]*)\s*HB", text, re.I)
        if hardness:
            mechanical["hardness_hb"] = float(hardness.group(1))

    # Label-based metadata: "Material : CF8M", "Commodity : T-758 ...", "PO#: 29204"
    material = re.search(r"material\s*:\s*([A-Za-z0-9\-]+)", text, re.I)
    commodity = re.search(r"commodity\s*:\s*([A-Za-z0-9\-]+)", text, re.I)
    po = re.search(r"\bPO\s*#?\s*:?\s*([A-Za-z0-9\-]+)", text, re.I)
    heat = re.search(r"heat\s*(?:/\s*lot)?\s*(?:no\.?|number)?[\s:.]{0,5}([A-Za-z0-9\-]+)", text, re.I)
    alloy = material or re.search(r"\b(?:UNS\s*)?(C\d{3,5}|C\d{2}00)\b", text)
    standard = re.search(r"\b(ASTM\s*[A-Z]\d+(?:/[A-Z0-9]+)?|JIS\s*[A-Z]\d+|CNS\s*\d+|EN\s*\d+|GB/?T?\s*\d+)\b", text, re.I)
    part = commodity or re.search(r"part\s*(?:no\.?|number)[\s:.]{0,5}([A-Za-z0-9\-]+)", text, re.I)

    # A table row's heat number (e.g. "U115") is more reliable than a bare
    # "Heat No." label match, which can accidentally capture the next column
    # header ("Qty") when the label and value aren't adjacent in the text.
    heat_number = table_heat_number or (heat.group(1) if heat else None)

    return {
        "heat_number": heat_number,
        "alloy_code": alloy.group(1).upper() if alloy else None,
        "standard": re.sub(r"\s+", " ", standard.group(1)).upper() if standard else None,
        "part_number": part.group(1) if part else None,
        "po_reference": po.group(1) if po else None,
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
