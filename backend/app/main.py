from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import GenerationRequest, GenerationResponse, ImportRequest, ImportResponse
from app.services.importer import mock_import
from app.services.test_generation import generate_mock_tests


app = FastAPI(
    title="QA Test Case Generator API",
    version="0.1.0",
    description="Mock backend API for the QA Test Case Generator MVP.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "qa-test-case-generator-api"}


@app.post("/api/generations/mock", response_model=GenerationResponse)
def create_mock_generation(request: GenerationRequest) -> GenerationResponse:
    return generate_mock_tests(request)


@app.post("/api/imports/mock", response_model=ImportResponse)
def create_mock_import(request: ImportRequest) -> ImportResponse:
    return mock_import(request)

