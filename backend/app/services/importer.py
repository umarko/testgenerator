from app.models import ImportedTestCase, ImportRequest, ImportResponse


def mock_import(request: ImportRequest) -> ImportResponse:
    story_number = int(request.source_work_item_id) if request.source_work_item_id.isdigit() else 1
    base_id = 55000 + story_number

    created = [
        ImportedTestCase(
            id=base_id + index,
            title=test_case.title,
            category=test_case.category,
            priority=test_case.priority,
        )
        for index, test_case in enumerate(request.test_cases)
    ]

    return ImportResponse(
        status="mock-imported",
        message=(
            f"{len(created)} test cases are ready for Azure DevOps plan "
            f"{request.target.test_plan_id}, suite {request.target.test_suite_id}, "
            f"linked to work item {request.source_work_item_id}."
        ),
        createdTestCases=created,
    )
