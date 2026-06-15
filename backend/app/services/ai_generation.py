import json
import re
from textwrap import dedent

from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, OpenAI

from app.models import (
    CoverageMapRefinementRequest,
    CoverageMapResponse,
    FunctionalArea,
    GenerationRequest,
    GenerationResponse,
    RefinementRequest,
    TestCase,
)
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


def generate_coverage_map(request: GenerationRequest) -> CoverageMapResponse:
    allowed_categories = _allowed_categories(request)
    allowed_priorities = _allowed_priorities(request)
    allowed_platforms = _allowed_platforms(request)

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
                {"role": "system", "content": _coverage_system_prompt()},
                {
                    "role": "user",
                    "content": _coverage_user_prompt(
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
                    "name": "qa_coverage_map",
                    "strict": True,
                    "schema": _coverage_map_schema(),
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
    functional_areas = [
        FunctionalArea.model_validate(area)
        for area in payload.get("functionalAreas", [])
    ]

    return CoverageMapResponse(
        sourceWorkItemId=request.azure.story_id,
        summary=payload.get("summary", f"Generated AI coverage map for: {request.story.title}"),
        functionalAreas=functional_areas,
        crossFunctionalRisks=payload.get("crossFunctionalRisks", []),
        globalAssumptions=payload.get("globalAssumptions", []),
        globalQuestionsForBA=payload.get("globalQuestionsForBA", []),
        generationSource=f"openai-coverage:{settings.openai_model}",
    )


def refine_coverage_map(request: CoverageMapRefinementRequest) -> CoverageMapResponse:
    allowed_categories = _allowed_categories(request)
    allowed_priorities = _allowed_priorities(request)
    allowed_platforms = _allowed_platforms(request)

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
                {"role": "system", "content": _coverage_system_prompt()},
                {
                    "role": "user",
                    "content": _coverage_refinement_prompt(
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
                    "name": "qa_coverage_map_refinement",
                    "strict": True,
                    "schema": _coverage_map_schema(),
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
    functional_areas = [
        FunctionalArea.model_validate(area)
        for area in payload.get("functionalAreas", [])
    ]

    return CoverageMapResponse(
        sourceWorkItemId=request.azure.story_id,
        summary=payload.get("summary", f"Refined AI coverage map for: {request.story.title}"),
        functionalAreas=functional_areas,
        crossFunctionalRisks=payload.get("crossFunctionalRisks", []),
        globalAssumptions=payload.get("globalAssumptions", []),
        globalQuestionsForBA=payload.get("globalQuestionsForBA", []),
        generationSource=f"openai-coverage-refine:{settings.openai_model}",
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
        Regression: Existing behavior that may be impacted by this story.
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


def _coverage_system_prompt() -> str:
    return dedent(
        """
        You are a senior fintech QA analyst performing test coverage analysis.

        Your task is NOT to create test cases.
        Your task is NOT to create detailed test scenarios.

        Analyze the provided user story, acceptance criteria, business rules, additional user context, and attached documentation.
        Divide the feature into logical functional areas that require testing.
        A functional area should represent a group of related business rules, validations, user interactions, processing logic, integrations, workflows, or impacted existing behavior.
        Your goal is to create a coverage map that helps QA understand whether the complete feature is covered before creating detailed test cases.

        Rules:
        - Do not create test cases.
        - Do not create detailed test scenarios.
        - Do not split the feature into very small UI elements.
        - Do not create separate areas for fields that belong to the same business functionality.
        - Group related validations and behaviors together.
        - Include both new functionality and impacted existing functionality.
        - Include regression areas when the story or documentation states or strongly implies that existing flows may be impacted.
        - Include integration areas when the feature affects external systems, APIs, payment rails, back-office processing, status handling, reporting, audit, or downstream systems.
        - Do not invent functionality that is not supported by the provided documentation.
        - If a business rule, value, status, threshold, permission, role, fee, cut-off time, or error behavior is unclear, do not guess. Put it in questionsForBA.
        - Use assumptions only for execution/test setup context, not for missing business rules.

        Risk guidance:
        - High: money movement, payment processing, transaction status, business routing, authorization/security, data integrity, audit/compliance, or functionality with high customer/business impact.
        - Medium: validations, UI behavior, configuration-based logic, integration details, operational processing, error handling, or regression-sensitive behavior.
        - Low: cosmetic, informational, wording-only, or low-risk display changes.

        Coverage category guidance:
        - Positive: successful expected behavior and happy paths.
        - Negative: invalid input, rejected actions, blocked flows, error handling.
        - Boundary: limits, thresholds, precision, dates, lengths, ranges, cut-off values.
        - Security: authorization, access control, sensitive data exposure, fraud/abuse-resistant behavior.
        - Audit: audit trail, traceability, compliance evidence, logs, operational support.
        - Regression: existing behavior that may be impacted by this story.

        Priority guidance:
        - P1: critical business flow, money movement, irreversible actions, blocking validations, security-critical access, or production-stopping defects.
        - P2: important alternative paths, common negative scenarios, major validations, high-value regression risk.
        - P3: boundary values, less common validations, secondary workflow details.
        - P4: UI clarity, helper text, persistence of low-risk states.
        - P5: rare edge cases, cosmetic behavior, supporting evidence, nice-to-have checks.
        """
    ).strip()


def _coverage_user_prompt(
    request: GenerationRequest,
    allowed_categories: set[str],
    allowed_priorities: set[str],
    allowed_platforms: set[str],
) -> str:
    return dedent(
        f"""
        Create a coverage map for this fintech user story.

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

        Coverage map constraints:
        - Return only functional areas that are directly supported by the provided story, context, or attachment documentation.
        - For each area, recommend only selected categories, selected priorities, and selected platforms.
        - Include sourceEvidence for every functional area.
        - Use suggestedTestFocus only for high-level focus; do not write test cases or detailed steps.
        - Set included to true for every initially recommended area.
        - Keep userNotes empty.
        """
    ).strip()


def _coverage_refinement_prompt(
    request: CoverageMapRefinementRequest,
    allowed_categories: set[str],
    allowed_priorities: set[str],
    allowed_platforms: set[str],
) -> str:
    return dedent(
        f"""
        Refine the existing coverage map for this fintech user story.

        Return the full revised coverage map, not only added or changed areas.
        Preserve useful existing functional areas when they still match the clarified context.
        Respect user notes on each functional area and the global coverage refinement notes.
        If the user excluded an area, keep it excluded unless the documentation clearly shows it is critical and must be reconsidered.
        Add new functional areas when user notes or documentation show missing coverage.

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

        Current coverage map:
        {_coverage_map_context(request.current_coverage_map)}

        Global coverage refinement notes:
        {request.coverage_map_notes or "Not provided."}

        Selected categories:
        {", ".join(sorted(allowed_categories))}

        Selected priorities:
        {", ".join(sorted(allowed_priorities))}

        Selected platforms:
        {", ".join(sorted(allowed_platforms))}

        Coverage refinement constraints:
        - Do not create test cases.
        - Return the complete revised coverage map.
        - Recommend only selected categories, selected priorities, and selected platforms.
        - Treat user notes as authoritative QA feedback unless they conflict with the provided documentation.
        - Do not invent missing business values. Add BA questions instead.
        - Keep sourceEvidence for every functional area.
        - Keep or update included according to user feedback.
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


def _coverage_map_context(coverage_map: CoverageMapResponse) -> str:
    if not coverage_map.functional_areas:
        return "No current coverage areas were provided."

    chunks = [
        f"Summary: {coverage_map.summary}",
        "Functional areas:",
    ]
    for area in coverage_map.functional_areas:
        chunks.append(
            "\n".join(
                [
                    f"- {area.area_id} | included={area.included} | risk={area.risk_level}",
                    f"  Name: {area.area_name}",
                    f"  Description: {area.description}",
                    f"  Main functionality: {'; '.join(area.main_functionality)}",
                    f"  Platforms: {', '.join(area.platforms)}",
                    f"  Categories: {', '.join(area.recommended_categories)}",
                    f"  Priorities: {', '.join(area.recommended_priorities)}",
                    f"  Suggested focus: {'; '.join(area.suggested_test_focus)}",
                    f"  Questions for BA: {'; '.join(area.questions_for_ba) or 'None'}",
                    f"  User notes: {area.user_notes or 'None'}",
                ]
            )
        )

    if coverage_map.cross_functional_risks:
        chunks.append("Cross-functional risks:\n" + "\n".join(f"- {risk}" for risk in coverage_map.cross_functional_risks))
    if coverage_map.global_questions_for_ba:
        chunks.append("Global questions for BA:\n" + "\n".join(f"- {question}" for question in coverage_map.global_questions_for_ba))
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
    if coverage.regression:
        allowed.add("Regression")
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
                            "enum": ["Positive", "Negative", "Boundary", "Security", "Audit", "Regression"],
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


def _coverage_map_schema() -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "functionalAreas",
            "crossFunctionalRisks",
            "globalAssumptions",
            "globalQuestionsForBA",
        ],
        "properties": {
            "summary": {"type": "string"},
            "functionalAreas": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "areaId",
                        "areaName",
                        "description",
                        "mainFunctionality",
                        "qaImportance",
                        "riskLevel",
                        "sourceEvidence",
                        "platforms",
                        "recommendedCategories",
                        "recommendedPriorities",
                        "suggestedTestFocus",
                        "assumptions",
                        "questionsForBA",
                        "included",
                        "userNotes",
                    ],
                    "properties": {
                        "areaId": {"type": "string"},
                        "areaName": {"type": "string"},
                        "description": {"type": "string"},
                        "mainFunctionality": {"type": "array", "items": {"type": "string"}},
                        "qaImportance": {"type": "string"},
                        "riskLevel": {"type": "string", "enum": ["High", "Medium", "Low"]},
                        "sourceEvidence": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["sourceType", "sourceName", "evidence"],
                                "properties": {
                                    "sourceType": {"type": "string"},
                                    "sourceName": {"type": "string"},
                                    "evidence": {"type": "string"},
                                },
                            },
                        },
                        "platforms": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["Web", "Android", "iOS", "API"]},
                        },
                        "recommendedCategories": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["Positive", "Negative", "Boundary", "Security", "Audit", "Regression"],
                            },
                        },
                        "recommendedPriorities": {
                            "type": "array",
                            "items": {"type": "string", "enum": ["P1", "P2", "P3", "P4", "P5"]},
                        },
                        "suggestedTestFocus": {"type": "array", "items": {"type": "string"}},
                        "assumptions": {"type": "array", "items": {"type": "string"}},
                        "questionsForBA": {"type": "array", "items": {"type": "string"}},
                        "included": {"type": "boolean"},
                        "userNotes": {"type": "string"},
                    },
                },
            },
            "crossFunctionalRisks": {"type": "array", "items": {"type": "string"}},
            "globalAssumptions": {"type": "array", "items": {"type": "string"}},
            "globalQuestionsForBA": {"type": "array", "items": {"type": "string"}},
        },
    }
