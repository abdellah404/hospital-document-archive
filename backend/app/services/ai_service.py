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
You are extracting structured information
from a French hospital document.

IMPORTANT RULES:

1. Extract only information explicitly present
   or clearly identifiable in the text.

2. Never invent information.

3. If a field cannot be determined,
   return null.

4. For the service field, you MUST choose
   only from the provided services.

5. Ignore incomprehensible or corrupted text.

6. Return JSON only.

Available services:
{services_text}

OCR text:
----------------
{ocr_text}
----------------

Return exactly this structure:

{{
  "cni": null,
  "first_name": null,
  "last_name": null,
  "hospitalization_number": null,
  "service": null
}}
"""

    response = client.models.generate_content(
    model="gemini-3.6-flash",
        contents=prompt,
         config={
        "response_mime_type": "application/json",
    },
    )

    return json.loads(response.text)