import json

from google import genai

from app.core.config import settings


client = genai.Client(
    api_key=settings.gemini_api_key,
)


def extract_patient_information(
    ocr_text: str,
    services: list[str],
) -> dict:

    services_text = "\n".join(
        f"- {service}"
        for service in services
    )

    prompt = f"""
You are an information extraction assistant
for a French hospital archive system.

The following text was extracted from a scanned
French hospital PDF using OCR.

Your job is ONLY to extract the requested
information.

IMPORTANT RULES:

1. Never invent information.

2. If information is missing, return null.

3. Ignore handwritten or OCR text that is
   incomprehensible or unreliable.

4. Focus specifically on identifying:
   - patient CNI
   - patient first name
   - patient last name
   - hospitalization number
   - hospital service
   - admission date
   - discharge date

5. The hospitalization number is unique.

6. A single PDF represents one hospitalization.

7. The service MUST correspond to one of the
   services provided below.

8. Do NOT invent a service.

9. If the service cannot confidently be matched
   to one of the provided services, return null.

10. Dates must use YYYY-MM-DD.

11. Never calculate or infer dates.

12. Admission and discharge dates are ONLY AI
    suggestions and MUST be verified by the
    archivist before archiving.

13. Return ONLY valid JSON.

Available hospital services:

{services_text}

OCR TEXT:

---------------- BEGIN OCR ----------------

{ocr_text}

----------------- END OCR -----------------

Return exactly this JSON structure:

{{
  "cni": null,
  "first_name": null,
  "last_name": null,
  "hospitalization_number": null,
  "service": null,
  "admission_date": null,
  "discharge_date": null
}}
"""

    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
        },
    )

    raw_text = response.text.strip()

    if raw_text.startswith("```"):
        raw_text = (
            raw_text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

    result = json.loads(raw_text)

    return {
        "cni": result.get("cni"),
        "first_name": result.get(
            "first_name"
        ),
        "last_name": result.get(
            "last_name"
        ),
        "hospitalization_number": result.get(
            "hospitalization_number"
        ),
        "service": result.get("service"),
        "admission_date": result.get(
            "admission_date"
        ),
        "discharge_date": result.get(
            "discharge_date"
        ),
    }