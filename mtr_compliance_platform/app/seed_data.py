"""Seed data for the material spec library and demo suppliers.

Two sources of specs:
  - SPECS: a small hand-compiled demo set (is_demo_data=True) - representative
    values only, not certified copies of any standard.
  - IMPORTED_SPECS: imported from a user-provided Excel reference file
    (MTR_Analyzer.xlsm, Standards_DB tab) - treated as the user's real data
    (is_demo_data=False / "Custom" in the UI), still not a certified copy of
    the standard text.

sync_reference_data() is idempotent and insert-only, keyed on
(alloy_code, standard): it adds any spec/supplier not already present but
never touches or overwrites an existing row, so re-running it (e.g. on every
app startup) never reverts a spec you've since edited through the UI.
"""
from sqlmodel import Session, select

from .models import MaterialSpec, Supplier

DEMO_DISCLAIMER = (
    "Representative demo values compiled for this prototype — verify against "
    "the current official standard text before real QA/purchasing use."
)

IMPORT_DISCLAIMER = (
    "Imported from user-provided MTR_Analyzer.xlsm (Standards_DB tab). "
    "Values for quick reference only — verify against the current official standard text before real use."
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

IMPORTED_SPECS = [
    dict(
        alloy_code='C46400',
        alloy_name='鍛造黃銅 Naval Brass',
        standard='ASTM B21',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 59, 'max': 62}, 'Sn': {'min': 0.5, 'max': 1}, 'Pb': {'max': 0.2}, 'Fe': {'max': 0.1}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C46500',
        alloy_name='鍛造黃銅 Naval Brass (含砷)',
        standard='ASTM B21',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 59, 'max': 62}, 'Sn': {'min': 0.5, 'max': 1}, 'Pb': {'max': 0.2}, 'Fe': {'max': 0.1}, 'As': {'min': 0.02, 'max': 0.06}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C36300',
        alloy_name='鍛造快削黃銅(DZR抗脫鋅)',
        standard='ASTM B981/B981M',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 61.5, 'max': 63.5}, 'Pb': {'max': 0.2}, 'Fe': {'max': 0.1}, 'Zn': {'remainder': True}, 'Imp.': {'max': 0.2}, 'Sn': {'max': 0.1}, 'Ni': {'max': 0.3}, 'Al': {'max': 0.05}, 'As': {'min': 0.02, 'max': 0.15}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C35200',
        alloy_name='鍛造快削黃銅(DZR抗脫鋅)',
        standard='ASTM B121/B121M',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 59.5, 'max': 64}, 'Pb': {'min': 0.5, 'max': 3.5}, 'Fe': {'max': 0.1}, 'Zn': {'remainder': True}, 'Imp.': {'max': 0.2}, 'Sn': {'max': 0.1}, 'Ni': {'max': 0.3}, 'Al': {'max': 0.05}, 'As': {'min': 0.02, 'max': 0.25}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C37700',
        alloy_name='鍛造黃銅 Forging Brass(脫鋅risk)',
        standard='ASTM B283',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 58, 'max': 61}, 'Pb': {'min': 1.5, 'max': 2.5}, 'Fe': {'max': 0.3}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C27450',
        alloy_name='鍛造低鉛黃銅',
        standard='N/A',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 60, 'max': 65}, 'Pb': {'max': 0.25}, 'Fe': {'max': 0.35}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C6806',
        alloy_name='鍛造無鉛黃銅 (鉍系)',
        standard='JIS',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 58, 'max': 61}, 'Pb': {'max': 0.06}, 'Bi': {'min': 0.5, 'max': 2}, 'Cd': {'max': 0.001}, 'Hg': {'max': 0.001}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C69300',
        alloy_name='鍛造無鉛矽黃銅 EcoBrass(DZR抗脫鋅)',
        standard='ASTM B371',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 73, 'max': 77}, 'Si': {'min': 2.7, 'max': 3.4}, 'P': {'min': 0.04, 'max': 0.15}, 'Pb': {'max': 0.09}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C12200',
        alloy_name='磷脫氧銅 DHP (銅管件)',
        standard='ASTM B75',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 99.9}, 'P': {'min': 0.015, 'max': 0.04}},
        mechanical_limits={},
        notes=('Cu 含Ag' + " — " + IMPORT_DISCLAIMER),
    ),
    dict(
        alloy_code='CW617N',
        alloy_name='歐規鍛造黃銅',
        standard='EN 12165',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 57, 'max': 59}, 'Pb': {'min': 1.6, 'max': 2.5}, 'Fe': {'max': 0.3}, 'Ni': {'max': 0.3}, 'Sn': {'max': 0.3}, 'Al': {'max': 0.05}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='CW602N',
        alloy_name='歐規 DZR 黃銅(DZR抗脫鋅)',
        standard='EN 12165',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 61, 'max': 63}, 'Pb': {'min': 1.7, 'max': 2.8}, 'As': {'min': 0.02, 'max': 0.15}, 'Fe': {'max': 0.1}, 'Ni': {'max': 0.3}, 'Sn': {'max': 0.1}, 'Al': {'max': 0.05}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='HPb59-1',
        alloy_name='中國鍛造鉛黃銅',
        standard='GB/T 5231',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 57, 'max': 60}, 'Pb': {'min': 0.8, 'max': 1.9}, 'Fe': {'max': 0.5}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C83600',
        alloy_name='鑄造錫青銅 85-5-5-5',
        standard='ASTM B62',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 84, 'max': 86}, 'Sn': {'min': 4, 'max': 6}, 'Pb': {'min': 4, 'max': 6}, 'Zn': {'min': 4, 'max': 6}, 'Fe': {'max': 0.3}, 'Ni': {'max': 1}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C84400',
        alloy_name='鑄造半紅銅',
        standard='ASTM B584',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 78, 'max': 82}, 'Sn': {'min': 2.3, 'max': 3.5}, 'Pb': {'min': 6, 'max': 8}, 'Zn': {'min': 7, 'max': 10}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C85700',
        alloy_name='鑄造黃銅',
        standard='ASTM B584',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 58, 'max': 64}, 'Sn': {'min': 0.5, 'max': 1.5}, 'Pb': {'min': 0.8, 'max': 1.5}, 'Zn': {'min': 32, 'max': 40}, 'Fe': {'max': 0.7}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C87850',
        alloy_name='鑄造無鉛矽黃銅',
        standard='ASTM B584',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 74, 'max': 78}, 'Si': {'min': 2.7, 'max': 3.4}, 'P': {'min': 0.05, 'max': 0.2}, 'Pb': {'max': 0.09}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C87860',
        alloy_name='鑄造無鉛矽黃銅',
        standard='ASTM B584',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 75, 'max': 79}, 'Si': {'min': 2.7, 'max': 3.5}, 'P': {'min': 0.05, 'max': 0.2}, 'Pb': {'max': 0.09}, 'Sn': {'max': 0.3}, 'Fe': {'max': 0.1}, 'Ni': {'max': 0.2}, 'Mn': {'max': 0.1}, 'Zr': {'min': 0.002, 'max': 0.03}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C89833',
        alloy_name='鑄造無鉛鉍青銅',
        standard='ASTM B584',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 86, 'max': 91}, 'Sn': {'min': 4, 'max': 6}, 'Bi': {'min': 1.7, 'max': 2.7}, 'Zn': {'min': 2, 'max': 6}, 'Pb': {'max': 0.09}, 'Si': {'max': 0.005}, 'Sb': {'max': 0.25}, 'S': {'max': 0.08}, 'Al': {'max': 0.005}, 'Ni': {'max': 1}, 'P': {'max': 0.05}, 'Fe': {'max': 0.3}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C89836',
        alloy_name='鑄造無鉛鉍青銅',
        standard='ASTM B584',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 87, 'max': 91}, 'Sn': {'min': 4, 'max': 7}, 'Bi': {'min': 1.5, 'max': 3.5}, 'Zn': {'min': 2, 'max': 4}, 'Pb': {'max': 0.25}, 'Si': {'max': 0.005}, 'Sb': {'max': 0.25}, 'S': {'max': 0.08}, 'Al': {'max': 0.005}, 'Ni': {'max': 0.9}, 'P': {'max': 0.06}, 'Fe': {'max': 0.35}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='C89844',
        alloy_name='鑄造無鉛鉍青銅',
        standard='ASTM B584',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 83, 'max': 86}, 'Sn': {'min': 3, 'max': 5}, 'Bi': {'min': 2, 'max': 4}, 'Zn': {'min': 7, 'max': 10}, 'Pb': {'max': 0.2}, 'Si': {'max': 0.005}, 'Sb': {'max': 0.25}, 'S': {'max': 0.08}, 'Al': {'max': 0.005}, 'Ni': {'max': 1}, 'P': {'max': 0.05}, 'Fe': {'max': 0.3}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='CAC203',
        alloy_name='日規鑄造黃銅 (YBsC3)',
        standard='JIS H5120',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 58, 'max': 64}, 'Sn': {'max': 1}, 'Pb': {'max': 3}, 'Fe': {'max': 0.8}, 'Zn': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='CAC406',
        alloy_name='日規青銅鑄物 (BC6)',
        standard='JIS H5120',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 83, 'max': 87}, 'Sn': {'min': 4, 'max': 6}, 'Pb': {'min': 4, 'max': 6}, 'Zn': {'min': 4, 'max': 6}, 'Fe': {'max': 0.3}, 'Ni': {'max': 1}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='SS304',
        alloy_name='不銹鋼 (鍛/軋)',
        standard='ASTM A276',
        category='steel',
        chemistry_limits={'C': {'max': 0.08}, 'Mn': {'max': 2}, 'Si': {'max': 0.75}, 'P': {'max': 0.045}, 'S': {'max': 0.03}, 'Cr': {'min': 18, 'max': 20}, 'Ni': {'min': 8, 'max': 10.5}, 'Fe': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='SS304L',
        alloy_name='不銹鋼低碳',
        standard='ASTM A276',
        category='steel',
        chemistry_limits={'C': {'max': 0.03}, 'Mn': {'max': 2}, 'Si': {'max': 0.75}, 'P': {'max': 0.045}, 'S': {'max': 0.03}, 'Cr': {'min': 18, 'max': 20}, 'Ni': {'min': 8, 'max': 12}, 'Fe': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='SS316',
        alloy_name='不銹鋼 (含Mo)',
        standard='ASTM A276',
        category='steel',
        chemistry_limits={'C': {'max': 0.08}, 'Mn': {'max': 2}, 'Si': {'max': 0.75}, 'P': {'max': 0.045}, 'S': {'max': 0.03}, 'Cr': {'min': 16, 'max': 18}, 'Ni': {'min': 10, 'max': 14}, 'Mo': {'min': 2, 'max': 3}, 'Fe': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='SS316L',
        alloy_name='不銹鋼低碳含Mo',
        standard='ASTM A276',
        category='steel',
        chemistry_limits={'C': {'max': 0.03}, 'Mn': {'max': 2}, 'Si': {'max': 0.75}, 'P': {'max': 0.045}, 'S': {'max': 0.03}, 'Cr': {'min': 16, 'max': 18}, 'Ni': {'min': 10, 'max': 14}, 'Mo': {'min': 2, 'max': 3}, 'Fe': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='CF8',
        alloy_name='鑄造不銹鋼 (304鑄件)',
        standard='ASTM A351',
        category='steel',
        chemistry_limits={'C': {'max': 0.08}, 'Si': {'max': 2}, 'Mn': {'max': 1.5}, 'Cr': {'min': 18, 'max': 21}, 'Ni': {'min': 8, 'max': 11}, 'Fe': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='CF8M',
        alloy_name='鑄造不銹鋼 (316鑄件)',
        standard='ASTM A351',
        category='steel',
        chemistry_limits={'C': {'max': 0.08}, 'Si': {'max': 1.5}, 'Mn': {'max': 1.5}, 'Cr': {'min': 18, 'max': 21}, 'Ni': {'min': 9, 'max': 12}, 'Mo': {'min': 2, 'max': 3}, 'Fe': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='A105',
        alloy_name='碳鋼鍛件',
        standard='ASTM A105',
        category='steel',
        chemistry_limits={'C': {'max': 0.35}, 'Mn': {'min': 0.6, 'max': 1.05}, 'Si': {'min': 0.1, 'max': 0.35}, 'P': {'max': 0.035}, 'S': {'max': 0.04}, 'Cu': {'max': 0.4}, 'Ni': {'max': 0.4}, 'Cr': {'max': 0.3}, 'Mo': {'max': 0.12}, 'Fe': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='FC200',
        alloy_name='灰口鑄鐵 Grey Iron',
        standard='JIS G5501 / GB HT200',
        category='iron',
        chemistry_limits={'C': {'min': 3.2, 'max': 3.5}, 'Si': {'min': 1.7, 'max': 2}, 'Mn': {'min': 0.6, 'max': 0.9}, 'P': {'max': 0.08}, 'S': {'max': 0.05}},
        mechanical_limits={'tensile_strength_mpa': {'min': 200}},
        notes=('Tensile(MPa) 最低抗拉 min，單位 MPa' + " — " + IMPORT_DISCLAIMER),
    ),
    dict(
        alloy_code='SAE 1008',
        alloy_name='低碳鋼 (冷鍛/沖壓)',
        standard='SAE J403',
        category='steel',
        chemistry_limits={'C': {'max': 0.1}, 'Mn': {'min': 0.3, 'max': 0.5}, 'P': {'max': 0.03}, 'S': {'max': 0.05}, 'Si': {'max': 0.1}, 'Al': {'min': 0.01}, 'Fe': {'remainder': True}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='ASTM A53 Gr.A',
        alloy_name='碳鋼管 (焊接/無縫)',
        standard='ASTM A53/A53M',
        category='steel',
        chemistry_limits={'C': {'max': 0.25}, 'Mn': {'max': 0.95}, 'P': {'max': 0.05}, 'S': {'max': 0.045}, 'Cr': {'max': 0.4}, 'Ni': {'max': 0.4}, 'Cu': {'max': 0.4}, 'Mo': {'max': 0.15}, 'V': {'max': 0.08}},
        mechanical_limits={'tensile_strength_mpa': {'min': 330}, 'yield_strength_mpa': {'min': 205}},
        notes=('C Type S-無縫鋼管/E-電阻焊管; V Cu+Ni+Cr+Mo+V 合計 ≤1.00; Tensile(MPa) 最低抗拉 min; Yield(MPa) 最低降伏 min' + " — " + IMPORT_DISCLAIMER),
    ),
    dict(
        alloy_code='C23000',
        alloy_name='Copper-Zinc Alloys (Red Brass)紅銅 85%',
        standard='ASTM B43',
        category='copper_alloy',
        chemistry_limits={'Cu': {'min': 84, 'max': 86}, 'Pb': {'max': 0.05}, 'Zn': {'remainder': True}, 'Fe': {'max': 0.05}},
        mechanical_limits={},
        notes=IMPORT_DISCLAIMER,
    ),
    dict(
        alloy_code='Q235',
        alloy_name='碳素結構鋼 Q235',
        standard='GB/T700 / GB/T3274',
        category='steel',
        chemistry_limits={'C': {'max': 0.22}, 'Mn': {'max': 1.4}, 'Si': {'max': 0.35}, 'S': {'max': 0.05}, 'P': {'max': 0.045}},
        mechanical_limits={'tensile_strength_mpa': {'min': 375, 'max': 500}, 'yield_strength_mpa': {'min': 235}},
        notes=("C max corrected from source's 22 to 0.22 (source typo, verify); C Grade B; Mn Grade B; Si Grade B; S Grade B; P Grade B; Tensile(MPa) 抗拉 375-500; Yield(MPa) 最低降伏 min (≤16mm)" + " — " + IMPORT_DISCLAIMER),
    ),
]

SUPPLIERS = [
    dict(name="Supplier A — Guangdong Brass Foundry Co.", country="China", contact="qa@example-a.com"),
    dict(name="Supplier B — Taiwan Precision Casting Works", country="Taiwan", contact="qa@example-b.com"),
    dict(name="Supplier C — Ningbo Ductile Iron Ltd.", country="China", contact="qa@example-c.com"),
]


def sync_reference_data(session: Session) -> None:
    existing_specs = {(s.alloy_code, s.standard) for s in session.exec(select(MaterialSpec)).all()}
    for row in SPECS:
        key = (row["alloy_code"], row["standard"])
        if key not in existing_specs:
            session.add(MaterialSpec(**row, is_demo_data=True))
            existing_specs.add(key)
    for row in IMPORTED_SPECS:
        key = (row["alloy_code"], row["standard"])
        if key not in existing_specs:
            session.add(MaterialSpec(**row, is_demo_data=False))
            existing_specs.add(key)

    if not session.exec(select(Supplier)).first():
        for row in SUPPLIERS:
            session.add(Supplier(**row))
    session.commit()
