"""Calls Claude (vision) to interpret an engineering drawing and return
structured dimension / tolerance / measurement data.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional

from .prompts import SYSTEM_PROMPT, USER_PROMPT
from .schema import DIMENSION_TYPES, DrawingAnalysis

DEFAULT_MODEL = os.environ.get("DRAWING_QA_MODEL", "claude-sonnet-5")
DEFAULT_MAX_TOKENS = int(os.environ.get("DRAWING_QA_MAX_TOKENS", "16000"))

TOOL_NAME = "record_drawing_analysis"

_DIMENSION_ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "item_no": {"type": "integer"},
        "feature": {"type": "string"},
        "dimension_type": {"type": "string", "enum": list(DIMENSION_TYPES)},
        "nominal_value": {"type": ["number", "null"]},
        "upper_tol": {"type": ["number", "null"]},
        "lower_tol": {"type": ["number", "null"]},
        "unit": {"type": "string"},
        "upper_limit": {"type": ["number", "null"]},
        "lower_limit": {"type": ["number", "null"]},
        "is_critical": {"type": "boolean"},
        "gdt_symbol": {"type": ["string", "null"]},
        "measurement_method": {"type": "string"},
        "location_ref": {"type": "string"},
        "notes": {"type": "string"},
    },
    "required": ["item_no", "feature", "dimension_type"],
}

TOOL_SCHEMA = {
    "name": TOOL_NAME,
    "description": (
        "記錄一張工程圖面判讀出的所有尺寸標註、公差與量測要求，"
        "供後續自動產生品保檢核表使用。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "drawing_info": {
                "type": "object",
                "properties": {
                    "drawing_no": {"type": "string"},
                    "part_name": {"type": "string"},
                    "material": {"type": "string"},
                    "revision": {"type": "string"},
                    "general_tolerance": {"type": "string"},
                    "default_unit": {"type": "string"},
                },
            },
            "dimensions": {"type": "array", "items": _DIMENSION_ITEM_SCHEMA},
            "warnings": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["drawing_info", "dimensions"],
    },
}

_IMAGE_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_MAX_PDF_PAGES = 5


class DrawingExtractorError(RuntimeError):
    """Raised when a drawing cannot be read or Claude's response can't be parsed."""


def _pdf_to_images(pdf_path: Path, dpi: int = 200) -> list[bytes]:
    """Rasterise a PDF's pages to PNG bytes so they can be sent as vision input."""
    try:
        import pymupdf  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise DrawingExtractorError(
            "讀取 PDF 圖面需要安裝 pymupdf（pip install pymupdf），"
            "或請先將圖面匯出成 PNG/JPG 再輸入。"
        ) from exc

    doc = pymupdf.open(pdf_path)
    try:
        if doc.page_count > _MAX_PDF_PAGES:
            raise DrawingExtractorError(
                f"PDF 有 {doc.page_count} 頁，超過單次判讀上限 "
                f"({_MAX_PDF_PAGES} 頁)，請拆分後再分別判讀。"
            )
        zoom = dpi / 72
        matrix = pymupdf.Matrix(zoom, zoom)
        images = []
        for page in doc:
            pix = page.get_pixmap(matrix=matrix)
            images.append(pix.tobytes("png"))
        return images
    finally:
        doc.close()


def _load_drawing_images(path: str) -> list[tuple[bytes, str]]:
    """Return a list of (image_bytes, media_type) pairs for the given drawing file."""
    p = Path(path)
    if not p.exists():
        raise DrawingExtractorError(f"找不到檔案：{path}")

    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return [(data, "image/png") for data in _pdf_to_images(p)]
    if suffix in _IMAGE_MEDIA_TYPES:
        return [(p.read_bytes(), _IMAGE_MEDIA_TYPES[suffix])]
    raise DrawingExtractorError(
        f"不支援的檔案格式：{suffix}，請提供 PDF 或 PNG/JPG/WEBP 圖片。"
    )


def _extract_json_object(text: str) -> dict:
    """Pull the first top-level JSON object out of Claude's reply."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise DrawingExtractorError("Claude 的回覆中找不到 JSON 物件，無法解析。")
    candidate = text[start : end + 1]
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise DrawingExtractorError(f"無法解析 Claude 回覆的 JSON：{exc}") from exc


class DrawingExtractor:
    """Wraps the Anthropic API to turn a drawing image/PDF into a DrawingAnalysis."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> None:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover
            raise DrawingExtractorError(
                "缺少 anthropic 套件，請先執行 pip install -r requirements.txt"
            ) from exc

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise DrawingExtractorError(
                "缺少 API 金鑰，請設定環境變數 ANTHROPIC_API_KEY 或傳入 api_key 參數。"
            )

        self._client = anthropic.Anthropic(api_key=key)
        self.model = model
        self.max_tokens = max_tokens

    def analyze(self, drawing_path: str) -> DrawingAnalysis:
        """Read the drawing at ``drawing_path`` and return structured dimension data."""
        images = _load_drawing_images(drawing_path)

        content: list[dict] = []
        for data, media_type in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": base64.standard_b64encode(data).decode("utf-8"),
                    },
                }
            )
        content.append({"type": "text", "text": USER_PROMPT})

        response = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            tools=[TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": TOOL_NAME},
        )

        tool_uses = [b for b in response.content if b.type == "tool_use" and b.name == TOOL_NAME]
        if tool_uses:
            # response.input is already a parsed dict — no hand-rolled JSON parsing needed.
            data = tool_uses[0].input
        else:
            # Fallback for the rare case the model answers in plain text instead
            # of using the tool (e.g. hitting max_tokens mid tool-call).
            text_parts = [b.text for b in response.content if b.type == "text"]
            data = _extract_json_object("\n".join(text_parts))

        if response.stop_reason == "max_tokens":
            raise DrawingExtractorError(
                f"這張圖面的尺寸項目較多，判讀結果在 {self.max_tokens} 個 token 的上限內被截斷了。"
                "請調高「最大輸出長度」設定後再判讀一次（網頁介面在左側「進階設定」；"
                "指令列可加上 --max-tokens 24000），或考慮把圖面拆成較小範圍分別判讀。"
            )

        return DrawingAnalysis.from_dict(data)
