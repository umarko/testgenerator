from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import GenerationRequest, GenerationResponse, ImportRequest, ImportResponse, WorkItemResponse
from app.services.azure_devops import get_azure_devops_connector
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


@app.get("/api/azure/work-items/{work_item_id}", response_model=WorkItemResponse)
def get_work_item(work_item_id: str) -> WorkItemResponse:
    return get_azure_devops_connector().get_work_item(work_item_id)


@app.post("/api/generations/mock", response_model=GenerationResponse)
def create_mock_generation(request: GenerationRequest) -> GenerationResponse:
    if request.azure.story_id:
        work_item = get_azure_devops_connector().get_work_item(request.azure.story_id)
        request.story.title = work_item.title
        request.story.acceptance_criteria = work_item.acceptance_criteria or work_item.description
    return generate_mock_tests(request)


@app.post("/api/imports/mock", response_model=ImportResponse)
def create_mock_import(request: ImportRequest) -> ImportResponse:
    return mock_import(request)
