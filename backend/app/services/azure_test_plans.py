from fastapi import HTTPException

from app.models import (
    DryRunPlannedTestCase,
    DryRunValidation,
    ImportedTestCase,
    ImportDryRunResponse,
    ImportRequest,
    ImportResponse,
)
from app.services.azure_devops import AzureDevOpsConnector, get_azure_devops_connector


def dry_run_test_plan_import(
    request: ImportRequest,
    connector: AzureDevOpsConnector | None = None,
) -> ImportDryRunResponse:
    connector = connector or get_azure_devops_connector()
    validations = _validate_request(request)

    plan_name = ""
    suite_name = ""
    suite_names_by_platform = {}
    if _is_valid_so_far(validations):
        plan_name, suite_name, suite_names_by_platform = _validate_azure_target(request, connector, validations)
    if _is_valid_so_far(validations) and request.test_cases:
        _validate_test_case_creation(request, connector, validations)

    planned = [
        DryRunPlannedTestCase(
            sequence=index + 1,
            title=test_case.title,
            platform=test_case.platform,
            category=test_case.category,
            priority=test_case.priority,
            stepCount=len(test_case.steps),
            wouldCreateWorkItem=True,
            wouldLinkToStory=bool(request.source_work_item_id),
            wouldAddToSuite=True,
        )
        for index, test_case in enumerate(request.test_cases)
    ]

    status = "valid" if _is_valid_so_far(validations) else "invalid"
    valid_count = len([validation for validation in validations if validation.status == "valid"])
    message = (
        f"Dry run completed with {valid_count}/{len(validations)} validations passing. "
        f"{len(planned)} test cases would be created and added to the suite."
    )
    if status == "invalid":
        message = "Dry run found issues. No Azure DevOps changes were made."

    return ImportDryRunResponse(
        status=status,
        message=message,
        sourceWorkItemId=request.source_work_item_id,
        testPlanId=request.target.test_plan_id,
        testSuiteId=request.target.test_suite_id,
        testPlanName=plan_name,
        testSuiteName=suite_name,
        suiteNamesByPlatform=suite_names_by_platform,
        validations=validations,
        plannedTestCases=planned,
    )


def import_test_cases_to_azure(
    request: ImportRequest,
    connector: AzureDevOpsConnector | None = None,
) -> ImportResponse:
    connector = connector or get_azure_devops_connector()
    dry_run = dry_run_test_plan_import(request, connector)
    if dry_run.status != "valid":
        raise HTTPException(
            status_code=400,
            detail="Azure import was blocked because dry run validation failed.",
        )

    imported = []
    failures = []
    for index, test_case in enumerate(request.test_cases, start=1):
        test_case_id = None
        try:
            created_work_item = connector.create_manual_test_case(
                test_case,
                request.source_work_item_id,
            )
            test_case_id = int(created_work_item["id"])
            suite_id = _suite_id_for_platform(request, test_case.platform)
            connector.add_test_case_to_suite(request.target.test_plan_id, suite_id, test_case_id)
            imported.append(
                ImportedTestCase(
                    id=test_case_id,
                    title=test_case.title,
                    platform=test_case.platform,
                    category=test_case.category,
                    priority=test_case.priority,
                    status="Created and added to Azure Test Suite",
                )
            )
        except HTTPException as exc:
            stage = "add to suite" if test_case_id else "create work item"
            created_note = f" Created work item #{test_case_id} before failure." if test_case_id else ""
            failures.append(
                f"Test case {index} '{test_case.title}' failed during {stage}: "
                f"{exc.status_code} {exc.detail}.{created_note}"
            )
        except Exception as exc:
            stage = "add to suite" if test_case_id else "create work item"
            created_note = f" Created work item #{test_case_id} before failure." if test_case_id else ""
            failures.append(
                f"Test case {index} '{test_case.title}' failed during {stage}: {exc}.{created_note}"
            )

    if failures and imported:
        status = "partially-imported"
        message = (
            f"{len(imported)} test cases were imported. "
            f"{len(failures)} failed: {' | '.join(failures[:3])}"
        )
    elif failures:
        status = "failed"
        message = f"No test cases were imported. {' | '.join(failures[:3])}"
    else:
        status = "imported"
        message = (
            f"{len(imported)} test cases were created in Azure DevOps and added to "
            f"plan {request.target.test_plan_id}."
        )

    return ImportResponse(
        status=status,
        message=message,
        createdTestCases=imported,
    )


def _validate_request(request: ImportRequest) -> list[DryRunValidation]:
    validations = []
    validations.append(
        _validation(
            "Link Work Item",
            bool(request.source_work_item_id.strip()),
            f"Work item #{request.source_work_item_id} will be linked to each test case.",
            "Link Work Item ID is missing.",
        )
    )
    validations.append(
        _validation(
            "Test Plan ID",
            bool(request.target.test_plan_id.strip()),
            f"Test Plan #{request.target.test_plan_id} will be validated in Azure DevOps.",
            "Test Plan ID is required.",
        )
    )
    validations.append(
        _validation(
            "Platform suite mapping",
            _has_all_required_suite_ids(request),
            "Every platform present in the test set has a target Test Suite ID.",
            "Each platform present in the test set must have a target Test Suite ID.",
        )
    )
    validations.append(
        _validation(
            "Test cases",
            bool(request.test_cases),
            f"{len(request.test_cases)} test cases are ready for dry run validation.",
            "There are no test cases to import.",
        )
    )

    invalid_test = _first_invalid_test_case(request)
    validations.append(
        _validation(
            "Test case content",
            invalid_test == "",
            "All test cases have title, priority, category and at least one complete step.",
            invalid_test,
        )
    )
    return validations


def _validate_azure_target(
    request: ImportRequest,
    connector: AzureDevOpsConnector,
    validations: list[DryRunValidation],
) -> tuple[str, str, dict[str, str]]:
    plan_name = ""
    suite_name = ""
    suite_names_by_platform = {}

    try:
        suites_payload = connector.get_test_suites_for_plan(request.target.test_plan_id)
        suites = suites_payload.get("value", [])
        plan_name = _plan_name_from_suites(suites)
        validations.append(
            DryRunValidation(
                name="Azure Test Plan",
                status="valid",
                message=(
                    f"Azure DevOps returned {len(suites)} suites for Test Plan "
                    f"#{request.target.test_plan_id}."
                ),
            )
        )
    except HTTPException as exc:
        validations.append(
            DryRunValidation(
                name="Azure Test Plan",
                status="invalid",
                message=f"Could not read Test Plan #{request.target.test_plan_id}: {exc.detail}",
            )
        )
        return plan_name, suite_name, suite_names_by_platform

    for platform in _platforms_in_tests(request):
        suite_id = _suite_id_for_platform(request, platform)
        try:
            suite_payload = connector.get_test_suite(request.target.test_plan_id, suite_id)
            current_suite_name = suite_payload.get("name", "")
            suite_names_by_platform[platform] = current_suite_name
            if not suite_name:
                suite_name = current_suite_name
            plan_name = plan_name or (suite_payload.get("plan") or {}).get("name", "")
            validations.append(
                DryRunValidation(
                    name=f"Azure Test Suite - {platform}",
                    status="valid",
                    message=(
                        f"{platform} Test Suite #{suite_id}"
                        f"{f' ({current_suite_name})' if current_suite_name else ''} exists in the selected plan."
                    ),
                )
            )
        except HTTPException as exc:
            validations.append(
                DryRunValidation(
                    name=f"Azure Test Suite - {platform}",
                    status="invalid",
                    message=f"Could not read {platform} Test Suite #{suite_id}: {exc.detail}",
                )
            )

    return plan_name, suite_name, suite_names_by_platform


def _validate_test_case_creation(
    request: ImportRequest,
    connector: AzureDevOpsConnector,
    validations: list[DryRunValidation],
) -> None:
    try:
        connector.validate_manual_test_case(request.test_cases[0], request.source_work_item_id)
        validations.append(
            DryRunValidation(
                name="Azure Test Case create permission",
                status="valid",
                message="Azure DevOps accepted the Test Case payload in validate-only mode.",
            )
        )
    except HTTPException as exc:
        validations.append(
            DryRunValidation(
                name="Azure Test Case create permission",
                status="invalid",
                message=f"Azure DevOps rejected the Test Case payload in validate-only mode: {exc.detail}",
            )
        )


def _first_invalid_test_case(request: ImportRequest) -> str:
    for index, test_case in enumerate(request.test_cases, start=1):
        if not test_case.title.strip():
            return f"Test case {index} is missing a title."
        if not test_case.platform.strip():
            return f"Test case {index} is missing a platform."
        if not test_case.priority.strip():
            return f"Test case {index} is missing a priority."
        if not test_case.category.strip():
            return f"Test case {index} is missing a category."
        if not test_case.steps:
            return f"Test case {index} has no steps."
        for step_index, step in enumerate(test_case.steps, start=1):
            if not step.action.strip() or not step.expected_result.strip():
                return f"Test case {index}, step {step_index} is incomplete."
    return ""


def _platforms_in_tests(request: ImportRequest) -> list[str]:
    seen = []
    for test_case in request.test_cases:
        if test_case.platform not in seen:
            seen.append(test_case.platform)
    return seen


def _suite_id_for_platform(request: ImportRequest, platform: str) -> str:
    return (
        request.target.suite_ids_by_platform.get(platform)
        or request.target.suite_ids_by_platform.get(platform.lower())
        or request.target.test_suite_id
        or ""
    ).strip()


def _has_all_required_suite_ids(request: ImportRequest) -> bool:
    return all(_suite_id_for_platform(request, platform) for platform in _platforms_in_tests(request))


def _validation(name: str, condition: bool, valid_message: str, invalid_message: str) -> DryRunValidation:
    return DryRunValidation(
        name=name,
        status="valid" if condition else "invalid",
        message=valid_message if condition else invalid_message,
    )


def _is_valid_so_far(validations: list[DryRunValidation]) -> bool:
    return all(validation.status == "valid" for validation in validations)


def _plan_name_from_suites(suites: list[dict]) -> str:
    for suite in suites:
        plan = suite.get("plan") or {}
        if plan.get("name"):
            return plan["name"]
    return ""
