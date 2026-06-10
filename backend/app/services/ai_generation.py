import json
import re
from textwrap import dedent

from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, OpenAI

from app.models import GenerationRequest, GenerationResponse, RefinementRequest, TestCase
from app.settings import get_settings
from app.services.generation_cache import load_cached_generation, save_cached_generation
from app.services.test_generation import MAX_TESTS_PER_PLATFORM


ATTACHMENT_TEXT_LIMIT = 12000
PLATFORM_TITLE_PREFIXES = {
    "Web": "WEB",
    "Android": "Android",
    "iOS": "iOS",
    "API": "API",
}
PLATFORM_TITLE_PATTERN = re.compile(r"^\s*(WEB|Web|Android|iOS|IOS|API)\s*[-:]\s*", re.IGNORECASE)


def generate_ai_tests(request: GenerationRequest) -> GenerationResponse:
    allowed_categories = _allowed_categories(request)
    allowed_priorities = _allowed_priorities(request)
    allowed_platforms = _allowed_platforms(request)

    if not allowed_categories or not allowed_priorities or not allowed_platforms:
        return _empty_response(request)

    cached_response = load_cached_generation(request)
    if cached_response:
        _normalize_test_case_titles(cached_response.test_cases)
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
                {"role": "user", "content": _user_prompt(request, allowed_categories, allowed_priorities, allowed_platforms)},
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
    test_cases = _filter_and_limit(test_cases, allowed_categories, allowed_priorities, allowed_platforms)
    _normalize_test_case_titles(test_cases)

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


def refine_ai_tests(request: RefinementRequest) -> GenerationResponse:
    allowed_categories = _allowed_categories(request)
    allowed_priorities = _allowed_priorities(request)
    allowed_platforms = _allowed_platforms(request)

    if not allowed_categories or not allowed_priorities or not allowed_platforms:
        return _empty_response(request)

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
                {
                    "role": "user",
                    "content": _refinement_prompt(
                        request,
                        allowed_categories,
                        allowed_priorities,
                        allowed_platforms,
                    ),
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "qa_test_refinement",
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
    test_cases = _filter_and_limit(test_cases, allowed_categories, allowed_priorities, allowed_platforms)
    _normalize_test_case_titles(test_cases)

    return GenerationResponse(
        sourceWorkItemId=request.azure.story_id,
        summary=payload.get("summary", f"Refined AI manual test coverage for: {request.story.title}"),
        assumptions=payload.get("assumptions", []),
        questionsForBA=payload.get("questionsForBA", []),
        testCases=test_cases,
        generationSource=f"openai-refine:{settings.openai_model}",
    )


def _system_prompt() -> str:
    return dedent(
        """
        You are a senior fintech QA analyst creating manual test cases from Azure DevOps user stories and functional specifications.

        Generate only test cases that are directly supported by the provided story, acceptance criteria, additional user context, and included attachment documentation.
        Do not invent product behavior. If important business rules are missing, add questions for BA instead of guessing.
        Do not invent concrete values, limits, currencies, statuses, field lengths, error messages, roles, permissions, fees, cut-off times, or thresholds unless they are explicitly present in the provided context.
        If a concrete value is missing but needed for a test, create a question for BA and write the test with a generic phrase such as "configured threshold", "defined limit", or "approved message".
        Use assumptions only for execution context that is reasonable but not business-defining, such as "the user is authenticated", "test data exists", or "the feature flag is enabled".
        Use questionsForBA for missing business rules, unclear expected behavior, missing values, unresolved wording, or anything that could change the expected result.
        Respect the selected Category/Coverage and Priority filters strictly.
        The maximum number of test cases is a cap, not a target. Generate only the number of tests that are genuinely useful.
        Each test case must target exactly one platform: Web, Android, iOS, or API.
        Each test case title must start with its platform prefix in this exact format: "WEB - ...", "Android - ...", "iOS - ...", or "API - ...".
        Create platform-specific variants only when behavior, UI, validation, navigation, integration, or risk differs by platform.
        Do not duplicate identical tests across platforms unless separate execution per platform is genuinely needed.

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
    allowed_platforms: set[str],
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

        Selected platforms:
        {", ".join(sorted(allowed_platforms))}

        Generation constraints:
        - Return at most {MAX_TESTS_PER_PLATFORM} test cases per selected platform.
        - Return only selected categories, selected priorities, and selected platforms.
        - Prefix every title with the matching platform, for example "WEB - Verify transfer setup" or "iOS - Verify transfer setup".
        - Use priorities according to the supplied QA priority definitions.
        - Do not create the maximum number by default. Use the amount justified by the story and documentation.
        - Do not invent missing business values. Use generic wording in test cases and add BA questions for missing thresholds, statuses, limits, messages, roles, permissions, fees, cut-off times, or field rules.
        - Put uncertain execution setup in assumptions, but put unclear business behavior in questionsForBA.
        - Each test case must have clear preconditions and at least one action/expected result step.
        - Prefer concise, reviewable manual tests suitable for import into Azure DevOps Test Plans.
        """
    ).strip()


def _refinement_prompt(
    request: RefinementRequest,
    allowed_categories: set[str],
    allowed_priorities: set[str],
    allowed_platforms: set[str],
) -> str:
    return dedent(
        f"""
        Refine an existing manual QA test set for this fintech user story.

        Return the full revised test set, not only added or changed tests.
        Preserve useful existing tests when they still match the clarified context.
        Remove, merge, or rewrite tests that conflict with the user's refinement notes.
        Add missing coverage requested by the user.

        Azure work item ID:
        {request.azure.story_id}

        Story title:
        {request.story.title}

        Acceptance criteria / description:
        {request.story.acceptance_criteria or "Not provided."}

        Additional user-provided source context:
        {request.story.additional_context or "Not provided."}

        Included attachment documentation:
        {_attachment_context(request)}

        Current assumptions:
        {_list_context(request.current_assumptions)}

        Current questions for BA:
        {_list_context(request.current_questions_for_ba)}

        Current test cases:
        {_test_cases_context(request.current_test_cases)}

        User refinement notes - clarified business rules:
        {request.refinement_notes.clarified_business_rules or "Not provided."}

        User refinement notes - coverage gaps:
        {request.refinement_notes.coverage_gaps or "Not provided."}

        User refinement notes - tests to avoid or change:
        {request.refinement_notes.tests_to_avoid_or_change or "Not provided."}

        User refinement notes - additional instruction:
        {request.refinement_notes.additional_instruction or "Not provided."}

        Selected categories:
        {", ".join(sorted(allowed_categories))}

        Selected priorities:
        {", ".join(sorted(allowed_priorities))}

        Selected platforms:
        {", ".join(sorted(allowed_platforms))}

        Refinement constraints:
        - Return the complete revised list of test cases.
        - Return at most {MAX_TESTS_PER_PLATFORM} test cases per selected platform.
        - Return only selected categories, selected priorities, and selected platforms.
        - Preserve or add the matching platform prefix in every title, for example "WEB - Verify transfer setup" or "iOS - Verify transfer setup".
        - Treat clarified business rules from the user as authoritative additional context.
        - Do not invent missing business values. Use generic wording in test cases and add BA questions for missing thresholds, statuses, limits, messages, roles, permissions, fees, cut-off times, or field rules.
        - Put uncertain execution setup in assumptions, but put unclear business behavior in questionsForBA.
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


def _list_context(items: list[str]) -> str:
    if not items:
        return "None."
    return "\n".join(f"- {item}" for item in items)


def _test_cases_context(test_cases: list[TestCase]) -> str:
    if not test_cases:
        return "No current test cases were provided."

    chunks = []
    for index, test_case in enumerate(test_cases, start=1):
        steps = "\n".join(
            f"    {step_index}. Action: {step.action} | Expected: {step.expected_result}"
            for step_index, step in enumerate(test_case.steps, start=1)
        )
        preconditions = "; ".join(test_case.preconditions) or "None"
        chunks.append(
            f"{index}. [{test_case.platform}] [{test_case.category}] [{test_case.priority}] {test_case.title}\n"
            f"   Preconditions: {preconditions}\n"
            f"{steps}"
        )
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


def _allowed_platforms(request: GenerationRequest) -> set[str]:
    platforms = request.generation_policy.platforms
    allowed = set()
    if platforms.web:
        allowed.add("Web")
    if platforms.android:
        allowed.add("Android")
    if platforms.ios:
        allowed.add("iOS")
    if platforms.api:
        allowed.add("API")
    return allowed


def _filter_and_limit(
    test_cases: list[TestCase],
    allowed_categories: set[str],
    allowed_priorities: set[str],
    allowed_platforms: set[str],
) -> list[TestCase]:
    filtered = []
    platform_counts = {platform: 0 for platform in allowed_platforms}
    for test_case in test_cases:
        if (
            test_case.category in allowed_categories
            and test_case.priority in allowed_priorities
            and test_case.platform in allowed_platforms
            and test_case.steps
            and platform_counts[test_case.platform] < MAX_TESTS_PER_PLATFORM
        ):
            filtered.append(test_case)
            platform_counts[test_case.platform] += 1
    return filtered


def _normalize_test_case_titles(test_cases: list[TestCase]) -> None:
    for test_case in test_cases:
        prefix = PLATFORM_TITLE_PREFIXES.get(test_case.platform, test_case.platform or "WEB")
        title_without_prefix = PLATFORM_TITLE_PATTERN.sub("", test_case.title or "").strip()
        title_body = title_without_prefix or "Untitled test case"
        test_case.title = f"{prefix} - {title_body}"


def _empty_response(request: GenerationRequest) -> GenerationResponse:
    return GenerationResponse(
        sourceWorkItemId=request.azure.story_id,
        summary="No test cases generated because no category, priority, or platform was selected.",
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
                        "platform",
                        "priority",
                        "category",
                        "preconditions",
                        "steps",
                        "coverage",
                        "tags",
                    ],
                    "properties": {
                        "title": {"type": "string"},
                        "platform": {"type": "string", "enum": ["Web", "Android", "iOS", "API"]},
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
