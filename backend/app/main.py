import os

from fastapi import FastAPI

from app.api.auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
from app.api.patients import router as patients_router
from app.api.services import router as services_router
from app.api.hospitalizations import router as hospitalizations_router


app = FastAPI(
    title="Hospital Archive API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:4200'],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(patients_router)
app.include_router(services_router)
app.include_router(hospitalizations_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}



