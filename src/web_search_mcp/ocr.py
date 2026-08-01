import io

from web_search_mcp.observability import get_logger

_logger = get_logger("ocr")


def extract_text_from_image_bytes(image_bytes: bytes) -> str:
    """Görsel baytlarından (PNG, JPEG, WebP) tesseract OCR kullanarak metin çıkarır."""
    if not image_bytes:
        return ""

    try:
        import pytesseract
        from PIL import Image

        image = Image.open(io.BytesIO(image_bytes))
        text = pytesseract.image_to_string(image)
        return (text or "").strip()
    except Exception as e:
        _logger.warning("OCR extraction failed or Tesseract not installed: %s", str(e))
        return ""
