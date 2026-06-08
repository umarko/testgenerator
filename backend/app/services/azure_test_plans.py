from fastapi import HTTPException

from app.models import (
    DryRunPlannedTestCase,
    DryRunValidation,
    ImportDryRunResponse,
    ImportRequest,
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
    if _is_valid_so_far(validations):
        plan_name, suite_name = _validate_azure_target(request, connector, validations)

    planned = [
        DryRunPlannedTestCase(
            sequence=index + 1,
            title=test_case.title,
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
        validations=validations,
        plannedTestCases=planned,
    )


def _validate_request(request: ImportRequest) -> list[DryRunValidation]:
    validations = []
    validations.append(
        _validation(
            "Source story",
            bool(request.source_work_item_id.strip()),
            f"Source work item #{request.source_work_item_id} will be linked to each test case.",
            "Source Work Item ID is missing.",
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
            "Test Suite ID",
            bool(request.target.test_suite_id.strip()),
            f"Test Suite #{request.target.test_suite_id} will be validated in Azure DevOps.",
            "Test Suite ID is required.",
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
) -> tuple[str, str]:
    plan_name = ""
    suite_name = ""

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
        return plan_name, suite_name

    try:
        suite_payload = connector.get_test_suite(
            request.target.test_plan_id,
            request.target.test_suite_id,
        )
        suite_name = suite_payload.get("name", "")
        plan_name = plan_name or (suite_payload.get("plan") or {}).get("name", "")
        validations.append(
            DryRunValidation(
                name="Azure Test Suite",
                status="valid",
                message=(
                    f"Test Suite #{request.target.test_suite_id}"
                    f"{f' ({suite_name})' if suite_name else ''} exists in the selected plan."
                ),
            )
        )
    except HTTPException as exc:
        validations.append(
            DryRunValidation(
                name="Azure Test Suite",
                status="invalid",
                message=f"Could not read Test Suite #{request.target.test_suite_id}: {exc.detail}",
            )
        )

    return plan_name, suite_name


def _first_invalid_test_case(request: ImportRequest) -> str:
    for index, test_case in enumerate(request.test_cases, start=1):
        if not test_case.title.strip():
            return f"Test case {index} is missing a title."
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
