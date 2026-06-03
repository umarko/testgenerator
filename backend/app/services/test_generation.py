from app.models import GenerationRequest, GenerationResponse, TestCase, TestStep


def generate_mock_tests(request: GenerationRequest) -> GenerationResponse:
    if _is_wise_transfer_story(request):
        return _generate_wise_transfer_tests(request)

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


def _is_wise_transfer_story(request: GenerationRequest) -> bool:
    context = f"{request.story.title}\n{request.story.acceptance_criteria}".lower()
    return "wise" in context and ("currency" in context or "currencies" in context)


def _generate_wise_transfer_tests(request: GenerationRequest) -> GenerationResponse:
    policy = request.generation_policy
    tests = [
        _test_case(
            "Verify Wise country list contains only supported countries",
            "High",
            "Positive",
            ["User is authenticated", "International transfer flow is available"],
            [
                ("Open international transfer country selection", "Country selection is displayed"),
                (
                    "Review available Wise-supported countries",
                    "Only Switzerland, United Kingdom and United States are available for Wise flow",
                ),
            ],
        ),
        _test_case(
            "Verify local currency is applied for Switzerland Wise transfer",
            "High",
            "Positive",
            ["User is authenticated", "Switzerland is selected as destination country"],
            [
                ("Select Switzerland as destination country", "Currency is set to CHF"),
                ("Enter valid amount in CHF", "Amount is accepted for Wise eligibility check"),
            ],
        ),
        _test_case(
            "Verify local currency is applied for United Kingdom Wise transfer",
            "High",
            "Positive",
            ["User is authenticated", "United Kingdom is selected as destination country"],
            [
                ("Select United Kingdom as destination country", "Currency is set to GBP"),
                ("Enter valid amount in GBP", "Amount is accepted for Wise eligibility check"),
            ],
        ),
        _test_case(
            "Verify local currency is applied for United States Wise transfer",
            "High",
            "Positive",
            ["User is authenticated", "United States is selected as destination country"],
            [
                ("Select United States as destination country", "Currency is set to USD"),
                ("Enter valid amount in USD", "Amount is accepted for Wise eligibility check"),
            ],
        ),
        _test_case(
            "Verify unsupported country cannot be selected for Wise transfer",
            "High",
            "Negative",
            ["User is authenticated", "International transfer flow is available"],
            [
                ("Attempt to select a country outside Switzerland, United Kingdom and United States", "Country is not available for Wise or Wise eligibility is not offered"),
                ("Continue transfer setup", "User cannot proceed through Wise flow for unsupported country"),
            ],
        ),
        _test_case(
            "Verify mismatched country and currency combination is rejected",
            "High",
            "Negative",
            ["User is authenticated", "Wise country and currency fields are visible"],
            [
                ("Select Switzerland and attempt to use currency other than CHF", "Currency mismatch is prevented or validation message is displayed"),
                ("Attempt to continue", "System does not confirm Wise eligibility for mismatched input"),
            ],
        ),
        _test_case(
            "Verify Wise eligibility is confirmed based on country, currency and amount",
            "High",
            "Positive",
            ["User is authenticated", "Supported country and matching currency are selected"],
            [
                ("Enter valid country, currency and amount", "Input fields are accepted"),
                ("Trigger eligibility check or continue transfer setup", "System confirms transaction eligibility for Wise"),
            ],
        ),
        _test_case(
            "Verify amount is mandatory for Wise eligibility confirmation",
            "High",
            "Negative",
            ["User is authenticated", "Supported country and matching currency are selected"],
            [
                ("Leave amount empty", "Amount field is marked as required"),
                ("Attempt to continue", "Wise eligibility is not confirmed without amount"),
            ],
        ),
        _test_case(
            "Verify Commission OUR becomes read-only after IBAN is entered",
            "Medium",
            "Regression",
            ["User is authenticated", "International transfer form is open"],
            [
                ("Enter a valid IBAN", "IBAN is accepted"),
                ("Attempt to change Commission OUR field", "Commission OUR is clearly labeled as fixed and cannot be modified"),
            ],
        ),
        _test_case(
            "Verify Currency becomes read-only after IBAN is entered",
            "High",
            "Regression",
            ["User is authenticated", "International transfer form is open"],
            [
                ("Enter a valid IBAN", "IBAN is accepted"),
                ("Attempt to change Currency field", "Currency is clearly labeled as fixed and cannot be modified"),
            ],
        ),
        _test_case(
            "Verify Value date becomes read-only after IBAN is entered",
            "Medium",
            "Regression",
            ["User is authenticated", "International transfer form is open"],
            [
                ("Enter a valid IBAN", "IBAN is accepted"),
                ("Attempt to change Value date field", "Value date is clearly labeled as fixed and cannot be modified"),
            ],
        ),
        _test_case(
            "Verify fixed fields are visually clear after IBAN entry",
            "Medium",
            "Positive",
            ["User is authenticated", "A valid IBAN has been entered"],
            [
                ("Review Commission OUR, Currency and Value date fields", "All fixed fields are visibly disabled or marked as non-editable"),
                ("Review helper text or labels", "User understands why the fields cannot be changed"),
            ],
        ),
        _test_case(
            "Verify UI instructions guide the user through Wise transfer setup",
            "Low",
            "Positive",
            ["User is authenticated", "Wise transfer flow is available"],
            [
                ("Open each step of the transfer process", "Instructions are visible and clear for country, currency, amount and IBAN entry"),
                ("Review validation and eligibility messages", "Messages are understandable and consistent with the selected inputs"),
            ],
        ),
        _test_case(
            "Verify auditability of Wise eligibility decision",
            "Medium",
            "Audit",
            ["Audit logging is enabled", "Wise eligibility check is performed"],
            [
                ("Complete Wise eligibility check with valid input", "Eligibility result is displayed"),
                ("Check audit record", "Audit record contains country, currency, amount, user, timestamp and eligibility result"),
            ],
        ),
        _test_case(
            "Verify Wise flow handles service unavailable response",
            "High",
            "Negative",
            ["User is authenticated", "Wise eligibility service is unavailable"],
            [
                ("Enter valid Wise input data", "Input fields are accepted"),
                ("Trigger eligibility check", "Clear service unavailable message is displayed and no false eligibility confirmation is shown"),
            ],
        ),
    ]

    selected_tests = tests[: policy.max_test_cases]

    return GenerationResponse(
        sourceWorkItemId=request.azure.story_id,
        summary=f"Generated Wise transfer manual test coverage for: {request.story.title}",
        assumptions=[
            "Wise eligibility is determined by country, currency and amount.",
            "Supported country/currency pairs are Switzerland/CHF, United Kingdom/GBP and United States/USD.",
            "Commission OUR, Currency and Value date become fixed after IBAN entry.",
        ],
        questionsForBA=[
            "What are the amount limits for Wise eligibility per currency?",
            "Should unsupported countries be hidden or visible with a disabled Wise option?",
            "What exact message should be shown when Wise eligibility service is unavailable?",
        ],
        testCases=selected_tests,
        generationSource="azure-devops-context-mock",
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
