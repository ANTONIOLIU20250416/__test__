"""Turns a DrawingAnalysis into a formatted Excel QC checklist."""

from __future__ import annotations

from datetime import date
from typing import Optional

from openpyxl import Workbook
from openpyxl.formatting.rule import CellIsRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .schema import DrawingAnalysis

_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_HEADER_FONT = Font(bold=True, color="FFFFFF")
_TITLE_FONT = Font(bold=True, size=14)
_LABEL_FONT = Font(bold=True)
_THIN_BORDER = Border(*(Side(style="thin", color="B7B7B7"),) * 4)
_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
_LEFT_WRAP = Alignment(horizontal="left", vertical="center", wrap_text=True)

_CHECKLIST_HEADERS = [
    ("項次", 6),
    ("尺寸 / 特徵說明", 28),
    ("類型", 12),
    ("標稱值", 10),
    ("上公差", 9),
    ("下公差", 9),
    ("管制上限", 10),
    ("管制下限", 10),
    ("單位", 7),
    ("關鍵尺寸", 9),
    ("建議量測工具", 16),
    ("位置參考", 12),
    ("實測值1", 10),
    ("實測值2", 10),
    ("實測值3", 10),
    ("判定結果", 10),
    ("備註", 24),
]

DIM_TYPE_LABELS = {
    "linear": "線性尺寸",
    "diameter": "直徑",
    "radius": "半徑",
    "angle": "角度",
    "thread": "螺紋",
    "gdt": "幾何公差(GD&T)",
    "surface_finish": "表面粗糙度/處理",
    "hardness": "硬度",
    "other": "其他",
}


def _style_header_row(ws: Worksheet, row: int, ncols: int) -> None:
    for col in range(1, ncols + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = _CENTER
        cell.border = _THIN_BORDER


def _build_info_sheet(
    ws: Worksheet,
    analysis: DrawingAnalysis,
    inspector: str,
    inspection_date: date,
) -> None:
    ws.title = "圖面基本資料"
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 16
    ws.column_dimensions["B"].width = 46

    ws["A1"] = "圖面判讀品保檢核表 — 基本資料"
    ws["A1"].font = _TITLE_FONT
    ws.merge_cells("A1:B1")

    info = analysis.drawing_info
    rows = [
        ("圖號", info.drawing_no),
        ("品名", info.part_name),
        ("材質", info.material),
        ("版次 Rev.", info.revision),
        ("未注公差 (General Tolerance)", info.general_tolerance),
        ("預設單位", info.default_unit),
        ("檢驗員", inspector),
        ("檢驗日期", inspection_date.isoformat()),
        ("尺寸項目數", len(analysis.dimensions)),
    ]
    r = 3
    for label, value in rows:
        ws.cell(row=r, column=1, value=label).font = _LABEL_FONT
        ws.cell(row=r, column=1).border = _THIN_BORDER
        cell = ws.cell(row=r, column=2, value=value)
        cell.border = _THIN_BORDER
        cell.alignment = _LEFT_WRAP
        r += 1

    r += 1
    if analysis.warnings:
        ws.cell(row=r, column=1, value="判讀警示（建議人工複核）").font = _LABEL_FONT
        r += 1
        for w in analysis.warnings:
            ws.cell(row=r, column=1, value=f"- {w}")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
            ws.cell(row=r, column=1).alignment = _LEFT_WRAP
            r += 1
    else:
        ws.cell(row=r, column=1, value="判讀警示：無").font = _LABEL_FONT


def _build_checklist_sheet(ws: Worksheet, analysis: DrawingAnalysis) -> None:
    ws.title = "尺寸檢核表"
    ncols = len(_CHECKLIST_HEADERS)

    for col, (title, width) in enumerate(_CHECKLIST_HEADERS, start=1):
        ws.cell(row=1, column=col, value=title)
        ws.column_dimensions[get_column_letter(col)].width = width
    _style_header_row(ws, 1, ncols)
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = f"A1:{get_column_letter(ncols)}1"

    for i, dim in enumerate(analysis.dimensions, start=1):
        row = i + 1
        values = [
            dim.item_no if dim.item_no else i,
            dim.feature,
            DIM_TYPE_LABELS.get(dim.dimension_type, dim.dimension_type),
            dim.nominal_value,
            dim.upper_tol,
            dim.lower_tol,
            dim.upper_limit,
            dim.lower_limit,
            dim.unit,
            "是" if dim.is_critical else "",
            dim.measurement_method,
            dim.location_ref,
            None,
            None,
            None,
            None,  # 判定結果 filled in via formula below
            dim.notes,
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row, column=col, value=value)
            cell.border = _THIN_BORDER
            cell.alignment = _CENTER if col not in (2, 17) else _LEFT_WRAP

        formula = (
            f'=IF(OR(G{row}="",H{row}=""),"需人工比對",'
            f"IF(COUNT(M{row}:O{row})=0,\"\","
            f'IF(AND(OR(M{row}="",AND(M{row}>=$G{row},M{row}<=$H{row})),'
            f'OR(N{row}="",AND(N{row}>=$G{row},N{row}<=$H{row})),'
            f'OR(O{row}="",AND(O{row}>=$G{row},O{row}<=$H{row}))),'
            '"合格","不合格")))'
        )
        ws.cell(row=row, column=16, value=formula)

    last_row = len(analysis.dimensions) + 1
    if last_row >= 2:
        result_range = f"P2:P{last_row}"
        ws.conditional_formatting.add(
            result_range,
            CellIsRule(
                operator="equal",
                formula=['"合格"'],
                fill=PatternFill("solid", fgColor="C6EFCE"),
                font=Font(color="006100"),
            ),
        )
        ws.conditional_formatting.add(
            result_range,
            CellIsRule(
                operator="equal",
                formula=['"不合格"'],
                fill=PatternFill("solid", fgColor="FFC7CE"),
                font=Font(color="9C0006"),
            ),
        )


def build_excel_checklist(
    analysis: DrawingAnalysis,
    output_path: str,
    inspector: str = "",
    inspection_date: Optional[date] = None,
) -> str:
    """Write ``analysis`` out as an Excel QC checklist at ``output_path``."""
    wb = Workbook()
    info_ws = wb.active
    _build_info_sheet(info_ws, analysis, inspector, inspection_date or date.today())

    checklist_ws = wb.create_sheet()
    _build_checklist_sheet(checklist_ws, analysis)

    wb.save(output_path)
    return output_path
