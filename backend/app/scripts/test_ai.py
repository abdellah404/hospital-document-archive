from app.services.ai_service import (
    extract_patient_information,
)


ocr_text = """
Nom : ALAOUI
Prénom : Ahmed
CNI : AB123456
ID Hospitalisation : 123
Service : Urgences
"""

services = [
    "Urgences",
    "Pharmacie",
    "Diagnostic",
    "Radiologie",
]


result = extract_patient_information(
    ocr_text,
    services,
)

print(result)