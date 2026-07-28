"""Local OCR pipeline for scanned/photographed MTR certificates.

Runs entirely on-device via Tesseract (through PyMuPDF for PDF page
rendering) — no network call, no API token cost. This is the default path
for scanned/image certificates; AI-based extraction is a separate, opt-in
step applied afterwards to the resulting *text* (see extraction.py).

Requires the system 'tesseract-ocr' binary plus language packs:
    apt-get install tesseract-ocr tesseract-ocr-chi-tra tesseract-ocr-chi-sim tesseract-ocr-vie
"""
import io
from typing import List

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from .extraction import pdf_bytes_to_text

# English + Traditional/Simplified Chinese + Vietnamese — the languages
# these plumbing-industry supplier certs are most often issued in.
OCR_LANGUAGES = "eng+chi_tra+chi_sim+vie"
RENDER_DPI = 300
NATIVE_TEXT_MIN_CHARS = 40  # below this, a "PDF" is treated as scan/photo-only

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp")


def is_image_file(filename: str) -> bool:
    return filename.lower().endswith(IMAGE_EXTENSIONS)


def ocr_image_bytes(data: bytes) -> str:
    image = Image.open(io.BytesIO(data))
    return pytesseract.image_to_string(image, lang=OCR_LANGUAGES)


def pdf_to_page_images(data: bytes) -> List[Image.Image]:
    doc = fitz.open(stream=data, filetype="pdf")
    zoom = RENDER_DPI / 72
    matrix = fitz.Matrix(zoom, zoom)
    images = []
    for page in doc:
        pix = page.get_pixmap(matrix=matrix)
        images.append(Image.open(io.BytesIO(pix.tobytes("png"))))
    return images


def ocr_pdf_bytes(data: bytes) -> str:
    pages = pdf_to_page_images(data)
    return "\n\n".join(pytesseract.image_to_string(p, lang=OCR_LANGUAGES) for p in pages)


def file_to_images(filename: str, data: bytes) -> List[Image.Image]:
    """Renders a file to page images for Claude vision extraction. Returns
    an empty list for file types with no visual page to send (e.g. .txt)."""
    lower = filename.lower()
    if is_image_file(lower):
        return [Image.open(io.BytesIO(data))]
    if lower.endswith(".pdf"):
        return pdf_to_page_images(data)
    return []


def get_document_text(filename: str, data: bytes) -> tuple[str, str]:
    """Returns (text, text_source) where text_source is one of:
    'native_pdf' (text layer read directly, zero cost), 'ocr' (local
    Tesseract), 'plain_text' (.txt upload)."""
    lower = filename.lower()
    if is_image_file(lower):
        return ocr_image_bytes(data), "ocr"
    if lower.endswith(".pdf"):
        native_text = pdf_bytes_to_text(data)
        if len(native_text.strip()) >= NATIVE_TEXT_MIN_CHARS:
            return native_text, "native_pdf"
        return ocr_pdf_bytes(data), "ocr"
    return data.decode("utf-8", errors="ignore"), "plain_text"
