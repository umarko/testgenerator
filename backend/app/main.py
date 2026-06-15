from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.models import (
    CoverageMapRefinementRequest,
    CoverageMapResponse,
    GenerationRequest,
    GenerationResponse,
    ImportDryRunResponse,
    ImportRequest,
    ImportResponse,
    RefinementRequest,
    WorkItemResponse,
)
from app.services.azure_devops import get_azure_devops_connector
from app.services.ai_generation import generate_ai_tests, generate_coverage_map, refine_ai_tests, refine_coverage_map
from app.services.azure_test_plans import dry_run_test_plan_import, import_test_cases_to_azure
from app.services.importer import mock_import
from app.services.test_generation import generate_mock_tests


app = FastAPI(
    title="QA Test Case Generator API",
    version="0.1.0",
    description="Backend API for Azure DevOps story import and AI-assisted QA test generation.",
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


@app.post("/api/generations/ai", response_model=GenerationResponse)
def create_ai_generation(request: GenerationRequest) -> GenerationResponse:
    return generate_ai_tests(request)


@app.post("/api/generations/refine", response_model=GenerationResponse)
def refine_generation(request: RefinementRequest) -> GenerationResponse:
    return refine_ai_tests(request)


@app.post("/api/coverage-map/ai", response_model=CoverageMapResponse)
def create_coverage_map(request: GenerationRequest) -> CoverageMapResponse:
    return generate_coverage_map(request)


@app.post("/api/coverage-map/refine", response_model=CoverageMapResponse)
def refine_coverage_map_generation(request: CoverageMapRefinementRequest) -> CoverageMapResponse:
    return refine_coverage_map(request)


@app.post("/api/imports/mock", response_model=ImportResponse)
def create_mock_import(request: ImportRequest) -> ImportResponse:
    return mock_import(request)


@app.post("/api/imports/azure/dry-run", response_model=ImportDryRunResponse)
def dry_run_azure_import(request: ImportRequest) -> ImportDryRunResponse:
    return dry_run_test_plan_import(request)


@app.post("/api/imports/azure", response_model=ImportResponse)
def create_azure_import(request: ImportRequest) -> ImportResponse:
    return import_test_cases_to_azure(request)
