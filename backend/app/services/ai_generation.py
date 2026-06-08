import json
from textwrap import dedent

from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, OpenAI

from app.models import GenerationRequest, GenerationResponse, TestCase
from app.settings import get_settings
from app.services.generation_cache import load_cached_generation, save_cached_generation
from app.services.test_generation import MAX_TESTS_PER_STORY


ATTACHMENT_TEXT_LIMIT = 12000


def generate_ai_tests(request: GenerationRequest) -> GenerationResponse:
    allowed_categories = _allowed_categories(request)
    allowed_priorities = _allowed_priorities(request)

    if not allowed_categories or not allowed_priorities:
        return _empty_response(request)

    cached_response = load_cached_generation(request)
    if cached_response:
        cached_response.generation_source = f"local-ai-cache:{cached_response.generation_source}"
        return cached_response

    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENAI_API_KEY is not configured in backend/.env.",
        )

    client = OpenAI(api_key=settings.openai_api_key)
    try:
        response = client.responses.create(
            model=settings.openai_model,
            input=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": _user_prompt(request, allowed_categories, allowed_priorities)},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "qa_test_generation",
                    "strict": True,
                    "schema": _generation_schema(),
                }
            },
        )
    except APIStatusError as exc:
        detail = _openai_error_detail(exc)
        raise HTTPException(status_code=502, detail=detail) from exc
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=502,
            detail="OpenAI API is not reachable. Check network access and proxy/firewall settings.",
        ) from exc

    payload = _parse_response_json(response)
    test_cases = [
        TestCase.model_validate(test_case)
        for test_case in payload.get("testCases", [])
    ]
    test_cases = _filter_and_limit(test_cases, allowed_categories, allowed_priorities)

    generation_response = GenerationResponse(
        sourceWorkItemId=request.azure.story_id,
        summary=payload.get("summary", f"Generated AI manual test coverage for: {request.story.title}"),
        assumptions=payload.get("assumptions", []),
        questionsForBA=payload.get("questionsForBA", []),
        testCases=test_cases,
        generationSource=f"openai:{settings.openai_model}",
    )
    save_cached_generation(request, generation_response)
    return generation_response


def _system_prompt() -> str:
    return dedent(
        """
        You are a senior fintech QA analyst creating manual test cases from Azure DevOps user stories and functional specifications.

        Generate only test cases that are directly supported by the provided story, acceptance criteria, additional user context, and included attachment documentation.
        Do not invent product behavior. If important business rules are missing, add questions for BA instead of guessing.
        Respect the selected Category/Coverage and Priority filters strictly.
        The maximum number of test cases is a cap, not a target. Generate only the number of tests that are genuinely useful.

        Priority definitions:
        P1: Critical path tests for core business flow, money movement, irreversible actions, blocking validations, security-critical access, or defects that would stop production use.
        P2: High business value tests for important alternative paths, common negative scenarios, important validations, and major regression risks.
        P3: Medium priority tests for boundary values, less common validations, secondary workflow details, and useful but not release-blocking coverage.
        P4: Low priority tests for UI clarity, helper text, field state persistence, and low-risk usability or regression checks.
        P5: Lowest priority tests for audit/supporting evidence, rare edge cases, cosmetic behavior, or nice-to-have checks unless the story makes them business-critical.

        Category definitions:
        Positive: Successful and expected user/business flows.
        Negative: Invalid input, blocked actions, failures, and error handling.
        Boundary: Limits, ranges, precision, dates, lengths, thresholds, and edge values.
        Security: Authorization, access control, sensitive data exposure, duplicate submission, and abuse-resistant behavior.
        Audit: Audit trail, traceability, logs, evidence, compliance records, and operational support checks.
        """
    ).strip()


def _user_prompt(
    request: GenerationRequest,
    allowed_categories: set[str],
    allowed_priorities: set[str],
) -> str:
    return dedent(
        f"""
        Create manual QA test cases for this fintech user story.

        Azure work item ID:
        {request.azure.story_id}

        Story title:
        {request.story.title}

        Acceptance criteria / description:
        {request.story.acceptance_criteria or "Not provided."}

        Additional user-provided context:
        {request.story.additional_context or "Not provided."}

        Included attachment documentation:
        {_attachment_context(request)}

        Selected categories:
        {", ".join(sorted(allowed_categories))}

        Selected priorities:
        {", ".join(sorted(allowed_priorities))}

        Generation constraints:
        - Return at most {MAX_TESTS_PER_STORY} test cases.
        - Return only selected categories and selected priorities.
        - Use priorities according to the supplied QA priority definitions.
        - Do not create 150 tests by default. Use the amount justified by the story and documentation.
        - Each test case must have clear preconditions and at least one action/expected result step.
        - Prefer concise, reviewable manual tests suitable for import into Azure DevOps Test Plans.
        """
    ).strip()


def _attachment_context(request: GenerationRequest) -> str:
    included = [
        attachment
        for attachment in request.story.attachments
        if attachment.included and attachment.text.strip()
    ]
    if not included:
        return "No readable included attachment text was provided."

    chunks = []
    for attachment in included:
        text = attachment.text.strip()[:ATTACHMENT_TEXT_LIMIT]
        chunks.append(f"Attachment: {attachment.name}\n{text}")
    return "\n\n".join(chunks)


def _allowed_categories(request: GenerationRequest) -> set[str]:
    coverage = request.generation_policy.coverage
    allowed = set()
    if coverage.positive:
        allowed.add("Positive")
    if coverage.negative:
        allowed.add("Negative")
    if coverage.boundary:
        allowed.add("Boundary")
    if coverage.security:
        allowed.add("Security")
    if coverage.audit:
        allowed.add("Audit")
    return allowed


def _allowed_priorities(request: GenerationRequest) -> set[str]:
    priorities = request.generation_policy.priorities
    allowed = set()
    if priorities.p1:
        allowed.add("P1")
    if priorities.p2:
        allowed.add("P2")
    if priorities.p3:
        allowed.add("P3")
    if priorities.p4:
        allowed.add("P4")
    if priorities.p5:
        allowed.add("P5")
    return allowed


def _filter_and_limit(
    test_cases: list[TestCase],
    allowed_categories: set[str],
    allowed_priorities: set[str],
) -> list[TestCase]:
    filtered = [
        test_case
        for test_case in test_cases
        if test_case.category in allowed_categories
        and test_case.priority in allowed_priorities
        and test_case.steps
    ]
    return filtered[:MAX_TESTS_PER_STORY]


def _empty_response(request: GenerationRequest) -> GenerationResponse:
    return GenerationResponse(
        sourceWorkItemId=request.azure.story_id,
        summary="No test cases generated because no category or priority was selected.",
        assumptions=[],
        questionsForBA=[],
        testCases=[],
        generationSource="openai-not-called",
    )


def _parse_response_json(response) -> dict:
    output_text = getattr(response, "output_text", "")
    if not output_text:
        for item in getattr(response, "output", []):
            for content in getattr(item, "content", []):
                text = getattr(content, "text", "")
                if text:
                    output_text += text

    if not output_text:
        raise HTTPException(status_code=502, detail="OpenAI response did not include JSON text.")

    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="OpenAI response was not valid JSON.") from exc


def _openai_error_detail(exc: APIStatusError) -> str:
    message = "OpenAI API request failed."
    if exc.status_code == 429:
        message = "OpenAI quota is exceeded or billing is not active for this API key."
    error_body = getattr(exc, "body", None)
    if isinstance(error_body, dict):
        error = error_body.get("error")
        if isinstance(error, dict) and error.get("message"):
            message = error["message"]
    return f"OpenAI API returned {exc.status_code}: {message}"


def _generation_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "assumptions", "questionsForBA", "testCases"],
        "properties": {
            "summary": {"type": "string"},
            "assumptions": {"type": "array", "items": {"type": "string"}},
            "questionsForBA": {"type": "array", "items": {"type": "string"}},
            "testCases": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "title",
                        "priority",
                        "category",
                        "preconditions",
                        "steps",
                        "coverage",
                        "tags",
                    ],
                    "properties": {
                        "title": {"type": "string"},
                        "priority": {"type": "string", "enum": ["P1", "P2", "P3", "P4", "P5"]},
                        "category": {
                            "type": "string",
                            "enum": ["Positive", "Negative", "Boundary", "Security", "Audit"],
                        },
                        "preconditions": {"type": "array", "items": {"type": "string"}},
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["action", "expectedResult"],
                                "properties": {
                                    "action": {"type": "string"},
                                    "expectedResult": {"type": "string"},
                                },
                            },
                        },
                        "coverage": {"type": "array", "items": {"type": "string"}},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
    }
