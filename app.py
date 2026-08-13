"""Friendly web UI for the drawing QA agent.

Run with:
    streamlit run app.py

Upload an engineering drawing (PDF/PNG/JPG), Claude reads the dimensions
and tolerances off it, and you download a ready-to-print Excel checklist.
No command-line knowledge needed once this is running.
"""

from __future__ import annotations

import io
import os
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from drawing_qa_agent.checklist import DIM_TYPE_LABELS, build_excel_checklist
from drawing_qa_agent.extractor import DrawingExtractor, DrawingExtractorError

st.set_page_config(page_title="圖面判讀檢核表產生器", page_icon="📐", layout="wide")

_SUPPORTED_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def _get_api_key() -> str | None:
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        return env_key
    return st.session_state.get("api_key") or None


def _render_sidebar() -> None:
    st.sidebar.header("⚙️ 設定")
    if os.environ.get("ANTHROPIC_API_KEY"):
        st.sidebar.success("已從系統環境變數讀到 API 金鑰")
    else:
        key = st.sidebar.text_input(
            "Anthropic API 金鑰",
            type="password",
            value=st.session_state.get("api_key", ""),
            help="到 console.anthropic.com 申請，只會保留在這次瀏覽器分頁的記憶體中，不會存檔。",
        )
        if key:
            st.session_state["api_key"] = key

    st.sidebar.divider()
    with st.sidebar.expander("進階設定"):
        st.number_input(
            "最大輸出長度（token數）",
            min_value=4000,
            max_value=64000,
            value=st.session_state.get("max_tokens", 16000),
            step=2000,
            key="max_tokens",
            help="圖面尺寸項目很多、判讀出現「超過 max_tokens 上限而被截斷」時，把這個值調高再試一次。",
        )

    st.sidebar.divider()
    st.sidebar.caption(
        "本工具由 AI 判讀圖面，結果僅供初判參考，"
        "正式檢驗結果仍須由品保工程師覆核確認。"
    )


def _preview_bytes(uploaded_file) -> None:
    suffix = Path(uploaded_file.name).suffix.lower()
    data = uploaded_file.getvalue()
    if suffix == ".pdf":
        try:
            import pymupdf

            doc = pymupdf.open(stream=data, filetype="pdf")
            pix = doc[0].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5))
            st.image(pix.tobytes("png"), caption=f"{uploaded_file.name}（第 1 頁預覽）", width=420)
            doc.close()
        except Exception:
            st.info(f"已上傳：{uploaded_file.name}（PDF 無法預覽，不影響判讀）")
    else:
        st.image(data, caption=uploaded_file.name, width=420)


def _dimensions_dataframe(analysis) -> pd.DataFrame:
    rows = []
    for d in analysis.dimensions:
        rows.append(
            {
                "項次": d.item_no,
                "尺寸/特徵說明": d.feature,
                "類型": DIM_TYPE_LABELS.get(d.dimension_type, d.dimension_type),
                "標稱值": d.nominal_value,
                "管制上限": d.upper_limit,
                "管制下限": d.lower_limit,
                "單位": d.unit,
                "關鍵尺寸": "是" if d.is_critical else "",
                "建議量測工具": d.measurement_method,
                "備註": d.notes,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    st.title("📐 圖面判讀 AI 代理 → 品質檢核表")
    st.write(
        "上傳工程圖面（PDF 或 PNG/JPG 圖片），AI 會讀出圖面上的尺寸標註與量測要求，"
        "自動整理成一份可直接列印使用的 Excel 品質檢核表。"
    )

    _render_sidebar()

    uploaded_file = st.file_uploader(
        "上傳圖面檔案", type=["pdf", "png", "jpg", "jpeg", "webp"], accept_multiple_files=False
    )

    col1, col2 = st.columns(2)
    inspector = col1.text_input("檢驗員姓名", value="")
    inspection_date = col2.date_input("檢驗日期", value=date.today())

    if uploaded_file is not None:
        _preview_bytes(uploaded_file)

    run = st.button("🔍 開始判讀圖面", type="primary", disabled=uploaded_file is None)

    if run:
        api_key = _get_api_key()
        if not api_key:
            st.error("請先在左側輸入 Anthropic API 金鑰。")
            return

        suffix = Path(uploaded_file.name).suffix.lower()
        if suffix not in _SUPPORTED_SUFFIXES:
            st.error(f"不支援的檔案格式：{suffix}")
            return

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        try:
            with st.spinner("AI 判讀圖面中，依複雜度可能需要 30 秒 ~ 2 分鐘…"):
                extractor = DrawingExtractor(api_key=api_key, max_tokens=st.session_state.get("max_tokens", 16000))
                analysis = extractor.analyze(tmp_path)
        except DrawingExtractorError as exc:
            st.error(f"判讀失敗：{exc}")
            return
        finally:
            os.unlink(tmp_path)

        st.session_state["analysis"] = analysis
        st.session_state["source_name"] = Path(uploaded_file.name).stem

    analysis = st.session_state.get("analysis")
    if analysis is not None:
        st.success(f"判讀完成，共擷取 {len(analysis.dimensions)} 項尺寸/量測要求。")

        info = analysis.drawing_info
        st.subheader("圖面基本資料")
        st.table(
            pd.DataFrame(
                [
                    {"項目": "圖號", "內容": info.drawing_no or "（未判讀到）"},
                    {"項目": "品名", "內容": info.part_name or "（未判讀到）"},
                    {"項目": "材質", "內容": info.material or "（未判讀到）"},
                    {"項目": "版次", "內容": info.revision or "（未判讀到）"},
                    {"項目": "未注公差", "內容": info.general_tolerance or "（未判讀到）"},
                ]
            )
        )

        if analysis.warnings:
            st.subheader("⚠️ 判讀警示（建議人工複核）")
            for w in analysis.warnings:
                st.warning(w)

        st.subheader("尺寸檢核表預覽")
        st.dataframe(_dimensions_dataframe(analysis), use_container_width=True, hide_index=True)

        excel_buffer = io.BytesIO()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_xlsx:
            build_excel_checklist(
                analysis, tmp_xlsx.name, inspector=inspector, inspection_date=inspection_date
            )
            excel_buffer.write(Path(tmp_xlsx.name).read_bytes())
        os.unlink(tmp_xlsx.name)
        excel_buffer.seek(0)

        st.download_button(
            "⬇️ 下載 Excel 檢核表",
            data=excel_buffer,
            file_name=f"{st.session_state.get('source_name', 'drawing')}_檢核表.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )


if __name__ == "__main__":
    main()
