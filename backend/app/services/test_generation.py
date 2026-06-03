from app.models import GenerationRequest, GenerationResponse, TestCase, TestStep


def generate_mock_tests(request: GenerationRequest) -> GenerationResponse:
    policy = request.generation_policy
    coverage = policy.coverage
    tests: list[TestCase] = []

    if coverage.positive:
        tests.append(
            _test_case(
                "Verify domestic payment is created with valid mandatory data",
                "High",
                "Positive",
                [
                    "User is authenticated",
                    "User has an active account with sufficient balance",
                ],
                [
                    ("Open the domestic payment form", "Domestic payment form is displayed"),
                    (
                        "Enter valid beneficiary account, amount and payment reference",
                        "All mandatory fields are accepted",
                    ),
                    (
                        "Submit the payment",
                        "Confirmation screen is displayed and payment is created",
                    ),
                ],
            )
        )

    if coverage.negative:
        tests.extend(
            [
                _test_case(
                    "Verify payment cannot be submitted when mandatory fields are empty",
                    "High",
                    "Negative",
                    ["User is authenticated"],
                    [
                        ("Open the domestic payment form", "Domestic payment form is displayed"),
                        (
                            "Leave mandatory fields empty and submit the form",
                            "Validation messages are displayed and payment is not submitted",
                        ),
                    ],
                ),
                _test_case(
                    "Verify payment is blocked when available balance is insufficient",
                    "High",
                    "Negative",
                    [
                        "User is authenticated",
                        "User has an active account with insufficient balance",
                    ],
                    [
                        (
                            "Enter payment amount greater than available balance",
                            "Amount is accepted for review or validation is triggered according to business rules",
                        ),
                        (
                            "Submit the payment",
                            "Payment is not created and insufficient balance message is shown",
                        ),
                    ],
                ),
            ]
        )

    if coverage.boundary:
        tests.extend(
            [
                _test_case(
                    "Verify amount boundary validation for minimum and maximum values",
                    "Medium",
                    "Boundary",
                    ["User is authenticated", "Payment limits are configured"],
                    [
                        (
                            "Submit payment with the minimum allowed amount",
                            "Payment can be submitted if all other data is valid",
                        ),
                        (
                            "Submit payment above the maximum allowed amount",
                            "Payment is rejected with a clear limit validation message",
                        ),
                    ],
                ),
                _test_case(
                    "Verify payment amount accepts supported decimal precision",
                    "Medium",
                    "Boundary",
                    ["User is authenticated", "Domestic payment form is open"],
                    [
                        ("Enter amount with supported decimal precision", "Amount is accepted"),
                        (
                            "Enter amount with unsupported decimal precision",
                            "Amount validation message is displayed",
                        ),
                    ],
                ),
            ]
        )

    if coverage.security:
        tests.extend(
            [
                _test_case(
                    "Verify user cannot create payment from an unauthorized account",
                    "High",
                    "Security",
                    [
                        "User is authenticated",
                        "User does not have permission for selected account",
                    ],
                    [
                        (
                            "Attempt to open or submit payment from unauthorized account",
                            "Account is not selectable or submission is blocked",
                        ),
                        (
                            "Review displayed error state",
                            "No sensitive account details are exposed",
                        ),
                    ],
                ),
                _test_case(
                    "Verify duplicate submit does not create duplicate payments",
                    "High",
                    "Security",
                    ["User is authenticated", "Valid payment data is entered"],
                    [
                        (
                            "Submit the payment and immediately attempt a second submit",
                            "Only one payment request is created",
                        ),
                        (
                            "Check confirmation or status screen",
                            "User sees one final payment confirmation",
                        ),
                    ],
                ),
            ]
        )

    if coverage.audit:
        tests.extend(
            [
                _test_case(
                    "Verify payment creation attempt is auditable",
                    "Medium",
                    "Audit",
                    ["Audit logging is enabled"],
                    [
                        (
                            "Submit a successful domestic payment",
                            "Payment confirmation is displayed",
                        ),
                        (
                            "Check audit record for the payment creation attempt",
                            "Audit record contains user, timestamp, action and result",
                        ),
                    ],
                ),
                _test_case(
                    "Verify audit record exists for failed payment submission",
                    "Medium",
                    "Audit",
                    ["Audit logging is enabled", "Payment submission fails"],
                    [
                        ("Submit payment data that triggers a failure", "Failure is displayed to the user"),
                        (
                            "Check audit record for failed submission",
                            "Audit record contains user, timestamp, action and failure result",
                        ),
                    ],
                ),
            ]
        )

    tests.extend(
        [
            _test_case(
                "Verify confirmation screen displays correct payment summary",
                "Medium",
                "Regression",
                ["User has submitted a valid domestic payment"],
                [
                    (
                        "Review beneficiary, amount, reference and account on confirmation screen",
                        "Displayed values match submitted payment data",
                    ),
                    (
                        "Navigate away from confirmation screen",
                        "User returns to the expected payments area",
                    ),
                ],
            ),
            _test_case(
                "Verify payment reference validation for unsupported characters",
                "Medium",
                "Negative",
                ["User is authenticated", "Domestic payment form is open"],
                [
                    (
                        "Enter unsupported characters in the payment reference field",
                        "Reference validation message is displayed",
                    ),
                    (
                        "Attempt to continue",
                        "User cannot proceed until the reference is corrected",
                    ),
                ],
            ),
            _test_case(
                "Verify user can cancel payment before final confirmation",
                "Medium",
                "Regression",
                ["User is authenticated", "Payment review screen is displayed"],
                [
                    (
                        "Select cancel or back action before final confirmation",
                        "Payment is not submitted",
                    ),
                    ("Return to payments overview", "No new payment is created"),
                ],
            ),
            _test_case(
                "Verify validation message is clear for invalid beneficiary account",
                "High",
                "Negative",
                ["User is authenticated", "Domestic payment form is open"],
                [
                    (
                        "Enter an invalid beneficiary account number",
                        "Beneficiary account validation error is displayed",
                    ),
                    ("Attempt to submit the payment", "Payment is not submitted"),
                ],
            ),
            _test_case(
                "Verify payment form handles service unavailable response",
                "High",
                "Negative",
                ["User is authenticated", "Payment service is unavailable"],
                [
                    (
                        "Submit valid payment data",
                        "User sees a clear service unavailable message",
                    ),
                    (
                        "Review payment status",
                        "No confirmed payment is shown without successful processing",
                    ),
                ],
            ),
            _test_case(
                "Verify mandatory field error messages disappear after correction",
                "Low",
                "Regression",
                ["User is authenticated", "Mandatory field errors are visible"],
                [
                    ("Correct all mandatory fields", "Validation messages are removed"),
                    ("Continue to review screen", "Review screen is displayed"),
                ],
            ),
            _test_case(
                "Verify screen data is preserved when returning from review to form",
                "Medium",
                "Regression",
                ["User is authenticated", "Payment review screen is displayed"],
                [
                    (
                        "Return from payment review to payment form",
                        "Previously entered payment data is still displayed",
                    ),
                    (
                        "Continue again to review screen",
                        "Updated review data is displayed",
                    ),
                ],
            ),
        ]
    )

    selected_tests = tests[: policy.max_test_cases]

    return GenerationResponse(
        sourceWorkItemId=request.azure.story_id,
        summary=f"Generated mock manual test coverage for: {request.story.title}",
        assumptions=[
            "User is authenticated before opening the payment flow.",
            "Domestic payment limits are configured outside this story.",
            "Generated tests must be reviewed by QA before Azure DevOps import.",
        ],
        questionsForBA=[
            "What special characters are allowed in the payment reference field?",
            "Should insufficient balance be validated before or after final submit?",
        ],
        testCases=selected_tests,
        generationSource="backend-mock",
    )


def _test_case(
    title: str,
    priority: str,
    category: str,
    preconditions: list[str],
    steps: list[tuple[str, str]],
) -> TestCase:
    return TestCase(
        title=title,
        priority=priority,
        category=category,
        preconditions=preconditions,
        steps=[
            TestStep(action=action, expectedResult=expected_result)
            for action, expected_result in steps
        ],
        coverage=[category],
        tags=["manual", category.lower(), "backend-mock"],
    )

