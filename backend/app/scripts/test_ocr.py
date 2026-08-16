from app.services.ocr_service import extract_text_from_pdf


pdf_path = "storage/documents/8af19059-8981-4cbf-99a7-02195e1c7ffe.pdf"

text = extract_text_from_pdf(pdf_path)

print(text)