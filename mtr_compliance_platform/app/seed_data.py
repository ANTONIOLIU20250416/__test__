"""Seed data for the material spec library and demo suppliers.

IMPORTANT: The chemistry/mechanical limits below are representative values
compiled for demonstration purposes only. They are NOT a certified copy of
the referenced standard. Before using this platform for real purchasing or
QA decisions, replace/verify every entry against the current official
standard text (ASTM/JIS/CNS, latest revision).
"""
from sqlmodel import Session, select

from .models import MaterialSpec, Supplier

DEMO_DISCLAIMER = (
    "Representative demo values compiled for this prototype — verify against "
    "the current official standard text before real QA/purchasing use."
)

SPECS = [
    dict(
        alloy_code="C46400",
        alloy_name="Naval Brass, Uninhibited",
        standard="ASTM B124",
        category="copper_alloy",
        chemistry_limits={
            "Cu": {"min": 59.0, "max": 62.0},
            "Sn": {"min": 0.50, "max": 1.0},
            "Pb": {"max": 0.20},
            "Fe": {"max": 0.10},
            "Zn": {"remainder": True},
        },
        mechanical_limits={
            "tensile_strength_mpa": {"min": 379},
            "yield_strength_mpa": {"min": 172},
            "elongation_pct": {"min": 33},
        },
        notes=DEMO_DISCLAIMER + " (rod, M20 as-extruded temper reference)",
    ),
    dict(
        alloy_code="C46500",
        alloy_name="Naval Brass, Leaded",
        standard="ASTM B124",
        category="copper_alloy",
        chemistry_limits={
            "Cu": {"min": 59.0, "max": 62.0},
            "Sn": {"min": 0.50, "max": 1.0},
            "Pb": {"min": 0.20, "max": 0.80},
            "Fe": {"max": 0.10},
            "Zn": {"remainder": True},
        },
        mechanical_limits={
            "tensile_strength_mpa": {"min": 379},
            "yield_strength_mpa": {"min": 172},
            "elongation_pct": {"min": 30},
        },
        notes=DEMO_DISCLAIMER,
    ),
    dict(
        alloy_code="C36000",
        alloy_name="Free-Cutting Brass",
        standard="ASTM B16",
        category="copper_alloy",
        chemistry_limits={
            "Cu": {"min": 60.0, "max": 63.0},
            "Pb": {"min": 2.5, "max": 3.7},
            "Fe": {"max": 0.35},
            "Zn": {"remainder": True},
        },
        mechanical_limits={
            "tensile_strength_mpa": {"min": 340},
            "elongation_pct": {"min": 18},
        },
        notes=DEMO_DISCLAIMER + " (H02 half-hard rod reference)",
    ),
    dict(
        alloy_code="C4640",
        alloy_name="Naval Brass (JIS)",
        standard="JIS H3250",
        category="copper_alloy",
        chemistry_limits={
            "Cu": {"min": 59.0, "max": 62.0},
            "Sn": {"min": 0.50, "max": 1.0},
            "Pb": {"max": 0.20},
            "Fe": {"max": 0.10},
            "Zn": {"remainder": True},
        },
        mechanical_limits={
            "tensile_strength_mpa": {"min": 390},
            "elongation_pct": {"min": 20},
        },
        notes=DEMO_DISCLAIMER + " (BE temper reference; JIS equivalent of UNS C46400)",
    ),
    dict(
        alloy_code="C3604",
        alloy_name="Free-Cutting Brass (JIS)",
        standard="JIS H3250",
        category="copper_alloy",
        chemistry_limits={
            "Cu": {"min": 59.0, "max": 63.0},
            "Pb": {"min": 1.8, "max": 3.7},
            "Fe": {"max": 0.10},
            "Zn": {"remainder": True},
        },
        mechanical_limits={
            "tensile_strength_mpa": {"min": 360},
            "elongation_pct": {"min": 15},
        },
        notes=DEMO_DISCLAIMER + " (JIS equivalent of UNS C36000)",
    ),
    dict(
        alloy_code="65-45-12",
        alloy_name="Ductile (Nodular) Iron",
        standard="ASTM A536",
        category="iron",
        chemistry_limits={},
        mechanical_limits={
            "tensile_strength_mpa": {"min": 450},
            "yield_strength_mpa": {"min": 310},
            "elongation_pct": {"min": 12},
        },
        notes=DEMO_DISCLAIMER + " (A536 sets mechanicals only; chemistry is producer's choice)",
    ),
    dict(
        alloy_code="FCD450",
        alloy_name="Spheroidal Graphite (Ductile) Iron",
        standard="JIS G5502",
        category="iron",
        chemistry_limits={},
        mechanical_limits={
            "tensile_strength_mpa": {"min": 450},
            "elongation_pct": {"min": 10},
        },
        notes=DEMO_DISCLAIMER,
    ),
    dict(
        alloy_code="32510",
        alloy_name="Malleable Iron",
        standard="ASTM A47",
        category="iron",
        chemistry_limits={},
        mechanical_limits={
            "tensile_strength_mpa": {"min": 345},
            "yield_strength_mpa": {"min": 224},
            "elongation_pct": {"min": 10},
        },
        notes=DEMO_DISCLAIMER,
    ),
]

SUPPLIERS = [
    dict(name="Supplier A — Guangdong Brass Foundry Co.", country="China", contact="qa@example-a.com"),
    dict(name="Supplier B — Taiwan Precision Casting Works", country="Taiwan", contact="qa@example-b.com"),
    dict(name="Supplier C — Ningbo Ductile Iron Ltd.", country="China", contact="qa@example-c.com"),
]


def seed_if_empty(session: Session) -> None:
    if not session.exec(select(MaterialSpec)).first():
        for row in SPECS:
            session.add(MaterialSpec(**row))
    if not session.exec(select(Supplier)).first():
        for row in SUPPLIERS:
            session.add(Supplier(**row))
    session.commit()
