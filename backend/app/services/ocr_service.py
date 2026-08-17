from pathlib import Path

import pytesseract

from pdf2image import convert_from_path


def extract_text_from_pdf(
    pdf_path: str,
) -> str:

    path = Path(pdf_path)

    if not path.exists():
        raise FileNotFoundError(
            f"PDF not found: {pdf_path}"
        )

    pages = convert_from_path(
        pdf_path,
        dpi=200,
    )

    if not pages:
        raise ValueError(
            "PDF contains no pages"
        )

    text_parts: list[str] = []

    for page_number, page in enumerate(
        pages,
        start=1,
    ):

        text = pytesseract.image_to_string(
            page,
            lang="fra",
        )

        text_parts.append(
            f"\n--- PAGE {page_number} ---\n"
        )

        text_parts.append(text)

    result = "\n".join(text_parts).strip()

    if not result:
        raise ValueError(
            "OCR produced no text"
        )

    return result