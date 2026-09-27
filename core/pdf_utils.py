from __future__ import annotations
from io import BytesIO
import fitz

MAX_PDF_BYTES = 25 * 1024 * 1024
MAX_EXTRACTED_CHARS = 180_000


def extract_pdf_text(uploaded_file) -> str:
    data = uploaded_file.getvalue()
    if not data:
        raise ValueError("The uploaded PDF is empty.")
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("The PDF is larger than 25 MB. Please upload a smaller file.")

    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise ValueError("I couldn't open this PDF. Please check that it is a valid PDF file.") from exc

    parts = []
    total = 0
    try:
        if doc.page_count == 0:
            raise ValueError("The PDF has no pages.")
        for page in doc:
            text = page.get_text("text") or ""
            if text.strip():
                remaining = MAX_EXTRACTED_CHARS - total
                if remaining <= 0:
                    break
                chunk = text[:remaining]
                parts.append(chunk)
                total += len(chunk)
    finally:
        doc.close()

    extracted = "\n\n".join(parts).strip()
    if not extracted:
        raise ValueError(
            "No readable text was found in this PDF. It may be scanned/image-only; this version supports text-based PDFs."
        )
    return extracted
