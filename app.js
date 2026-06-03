const state = {
  currentStep: "source",
  assumptions: [],
  questions: [],
  testCases: [],
  source: {}
};

const elements = {
  appStatus: document.querySelector("#appStatus"),
  sourcePanel: document.querySelector("#sourcePanel"),
  reviewPanel: document.querySelector("#reviewPanel"),
  importPanel: document.querySelector("#importPanel"),
  generateButton: document.querySelector("#generateButton"),
  resetButton: document.querySelector("#resetButton"),
  addTestButton: document.querySelector("#addTestButton"),
  mockImportButton: document.querySelector("#mockImportButton"),
  backToSourceButton: document.querySelector("#backToSourceButton"),
  backToReviewButton: document.querySelector("#backToReviewButton"),
  downloadJsonButton: document.querySelector("#downloadJsonButton"),
  assumptionsList: document.querySelector("#assumptionsList"),
  questionsList: document.querySelector("#questionsList"),
  testList: document.querySelector("#testList"),
  resultSummary: document.querySelector("#resultSummary"),
  resultList: document.querySelector("#resultList")
};

const coverageInputs = [
  "includePositive",
  "includeNegative",
  "includeBoundary",
  "includeSecurity",
  "includeAudit"
].map((id) => document.querySelector(`#${id}`));

function readSource() {
  return {
    organization: document.querySelector("#organization").value.trim(),
    project: document.querySelector("#project").value.trim(),
    storyId: document.querySelector("#storyId").value.trim(),
    testPlanId: document.querySelector("#testPlanId").value.trim(),
    testSuiteId: document.querySelector("#testSuiteId").value.trim(),
    maxTestCases: Number(document.querySelector("#maxTestCases").value || 8),
    storyTitle: document.querySelector("#storyTitle").value.trim(),
    acceptanceCriteria: document.querySelector("#acceptanceCriteria").value.trim(),
    coverage: Object.fromEntries(
      coverageInputs.map((input) => [input.id.replace("include", "").toLowerCase(), input.checked])
    )
  };
}

function setStep(step) {
  state.currentStep = step;
  elements.sourcePanel.classList.toggle("is-hidden", step !== "source");
  elements.reviewPanel.classList.toggle("is-hidden", step !== "review");
  elements.importPanel.classList.toggle("is-hidden", step !== "import");

  document.querySelectorAll(".step").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.step === step);
  });

  const labels = {
    source: "Draft",
    review: `${state.testCases.length} tests`,
    import: "Mock imported"
  };
  elements.appStatus.textContent = labels[step];
}

function createBaseTests(source) {
  const tests = [];

  if (source.coverage.positive) {
    tests.push({
      title: "Verify domestic payment is created with valid mandatory data",
      priority: "High",
      category: "Positive",
      preconditions: [
        "User is authenticated",
        "User has an active account with sufficient balance"
      ],
      steps: [
        {
          action: "Open the domestic payment form",
          expectedResult: "Domestic payment form is displayed"
        },
        {
          action: "Enter valid beneficiary account, amount and payment reference",
          expectedResult: "All mandatory fields are accepted"
        },
        {
          action: "Submit the payment",
          expectedResult: "Confirmation screen is displayed and payment is created"
        }
      ]
    });
  }

  if (source.coverage.negative) {
    tests.push({
      title: "Verify payment cannot be submitted when mandatory fields are empty",
      priority: "High",
      category: "Negative",
      preconditions: ["User is authenticated"],
      steps: [
        {
          action: "Open the domestic payment form",
          expectedResult: "Domestic payment form is displayed"
        },
        {
          action: "Leave mandatory fields empty and submit the form",
          expectedResult: "Validation messages are displayed and payment is not submitted"
        }
      ]
    });

    tests.push({
      title: "Verify payment is blocked when available balance is insufficient",
      priority: "High",
      category: "Negative",
      preconditions: [
        "User is authenticated",
        "User has an active account with insufficient balance"
      ],
      steps: [
        {
          action: "Enter payment amount greater than available balance",
          expectedResult: "Amount is accepted for review or validation is triggered according to business rules"
        },
        {
          action: "Submit the payment",
          expectedResult: "Payment is not created and insufficient balance message is shown"
        }
      ]
    });
  }

  if (source.coverage.boundary) {
    tests.push({
      title: "Verify amount boundary validation for minimum and maximum values",
      priority: "Medium",
      category: "Boundary",
      preconditions: ["User is authenticated", "Payment limits are configured"],
      steps: [
        {
          action: "Submit payment with the minimum allowed amount",
          expectedResult: "Payment can be submitted if all other data is valid"
        },
        {
          action: "Submit payment above the maximum allowed amount",
          expectedResult: "Payment is rejected with a clear limit validation message"
        }
      ]
    });
  }

  if (source.coverage.security) {
    tests.push({
      title: "Verify user cannot create payment from an unauthorized account",
      priority: "High",
      category: "Security",
      preconditions: ["User is authenticated", "User does not have permission for selected account"],
      steps: [
        {
          action: "Attempt to open or submit payment from unauthorized account",
          expectedResult: "Account is not selectable or submission is blocked"
        },
        {
          action: "Review displayed error state",
          expectedResult: "No sensitive account details are exposed"
        }
      ]
    });
  }

  if (source.coverage.audit) {
    tests.push({
      title: "Verify payment creation attempt is auditable",
      priority: "Medium",
      category: "Audit",
      preconditions: ["Audit logging is enabled"],
      steps: [
        {
          action: "Submit a successful domestic payment",
          expectedResult: "Payment confirmation is displayed"
        },
        {
          action: "Check audit record for the payment creation attempt",
          expectedResult: "Audit record contains user, timestamp, action and result"
        }
      ]
    });
  }

  tests.push({
    title: "Verify confirmation screen displays correct payment summary",
    priority: "Medium",
    category: "Regression",
    preconditions: ["User has submitted a valid domestic payment"],
    steps: [
      {
        action: "Review beneficiary, amount, reference and account on confirmation screen",
        expectedResult: "Displayed values match submitted payment data"
      },
      {
        action: "Navigate away from confirmation screen",
        expectedResult: "User returns to the expected payments area"
      }
    ]
  });

  return tests.slice(0, source.maxTestCases);
}

function generateTests() {
  state.source = readSource();
  state.assumptions = [
    "User is authenticated before opening the payment flow.",
    "Domestic payment limits are configured outside this story.",
    "Generated tests must be reviewed by QA before Azure DevOps import."
  ];
  state.questions = [
    "What special characters are allowed in the payment reference field?",
    "Should insufficient balance be validated before or after final submit?"
  ];
  state.testCases = createBaseTests(state.source);
  renderReview();
  setStep("review");
}

function renderList(listElement, items) {
  listElement.replaceChildren();
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    listElement.appendChild(li);
  });
}

function renderReview() {
  renderList(elements.assumptionsList, state.assumptions);
  renderList(elements.questionsList, state.questions);
  elements.testList.replaceChildren();
  state.testCases.forEach((testCase, index) => {
    elements.testList.appendChild(renderTestCard(testCase, index));
  });
  elements.appStatus.textContent = `${state.testCases.length} tests`;
}

function renderTestCard(testCase, index) {
  const template = document.querySelector("#testCaseTemplate");
  const card = template.content.firstElementChild.cloneNode(true);

  card.querySelector(".test-title").value = testCase.title;
  card.querySelector(".test-priority").value = testCase.priority;
  card.querySelector(".test-category").value = testCase.category;
  card.querySelector(".test-preconditions").value = testCase.preconditions.join("\n");

  card.querySelector(".test-title").addEventListener("input", (event) => {
    state.testCases[index].title = event.target.value;
  });
  card.querySelector(".test-priority").addEventListener("change", (event) => {
    state.testCases[index].priority = event.target.value;
  });
  card.querySelector(".test-category").addEventListener("change", (event) => {
    state.testCases[index].category = event.target.value;
  });
  card.querySelector(".test-preconditions").addEventListener("input", (event) => {
    state.testCases[index].preconditions = splitLines(event.target.value);
  });
  card.querySelector(".delete-test").addEventListener("click", () => {
    state.testCases.splice(index, 1);
    renderReview();
  });
  card.querySelector(".add-step").addEventListener("click", () => {
    state.testCases[index].steps.push({
      action: "New action",
      expectedResult: "Expected result"
    });
    renderReview();
  });

  const stepsList = card.querySelector(".steps-list");
  testCase.steps.forEach((step, stepIndex) => {
    stepsList.appendChild(renderStepRow(step, index, stepIndex));
  });

  return card;
}

function renderStepRow(step, testIndex, stepIndex) {
  const template = document.querySelector("#stepTemplate");
  const row = template.content.firstElementChild.cloneNode(true);

  row.querySelector(".step-action").value = step.action;
  row.querySelector(".step-expected").value = step.expectedResult;
  row.querySelector(".step-action").addEventListener("input", (event) => {
    state.testCases[testIndex].steps[stepIndex].action = event.target.value;
  });
  row.querySelector(".step-expected").addEventListener("input", (event) => {
    state.testCases[testIndex].steps[stepIndex].expectedResult = event.target.value;
  });
  row.querySelector(".delete-step").addEventListener("click", () => {
    state.testCases[testIndex].steps.splice(stepIndex, 1);
    renderReview();
  });

  return row;
}

function splitLines(value) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function addEmptyTestCase() {
  state.testCases.push({
    title: "New test case",
    priority: "Medium",
    category: "Regression",
    preconditions: ["User is authenticated"],
    steps: [
      {
        action: "Perform action",
        expectedResult: "Expected result is observed"
      }
    ]
  });
  renderReview();
}

function validateBeforeImport() {
  const errors = [];
  state.testCases.forEach((testCase, index) => {
    if (!testCase.title.trim()) {
      errors.push(`Test case ${index + 1} needs a title.`);
    }
    if (!testCase.steps.length) {
      errors.push(`Test case ${index + 1} needs at least one step.`);
    }
    testCase.steps.forEach((step, stepIndex) => {
      if (!step.action.trim() || !step.expectedResult.trim()) {
        errors.push(`Test case ${index + 1}, step ${stepIndex + 1} needs action and expected result.`);
      }
    });
  });
  return errors;
}

function mockImport() {
  const errors = validateBeforeImport();
  if (errors.length) {
    alert(errors.join("\n"));
    return;
  }

  const baseId = 55000 + Number(state.source.storyId || 1);
  const created = state.testCases.map((testCase, index) => ({
    id: baseId + index,
    title: testCase.title,
    category: testCase.category
  }));

  elements.resultSummary.innerHTML = `
    <strong>${created.length} test cases ready for Azure DevOps import.</strong>
    <p>Target plan ${escapeHtml(state.source.testPlanId)} and suite ${escapeHtml(state.source.testSuiteId)}.</p>
  `;

  elements.resultList.replaceChildren();
  created.forEach((item) => {
    const row = document.createElement("div");
    row.className = "result-row";
    row.innerHTML = `
      <span>${escapeHtml(item.title)}</span>
      <span class="result-id">Mock ID ${item.id}</span>
    `;
    elements.resultList.appendChild(row);
  });

  setStep("import");
}

function downloadJson() {
  const payload = {
    source: state.source,
    assumptions: state.assumptions,
    questionsForBA: state.questions,
    testCases: state.testCases
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `test-cases-story-${state.source.storyId || "draft"}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function resetDraft() {
  state.assumptions = [];
  state.questions = [];
  state.testCases = [];
  setStep("source");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

elements.generateButton.addEventListener("click", generateTests);
elements.resetButton.addEventListener("click", resetDraft);
elements.addTestButton.addEventListener("click", addEmptyTestCase);
elements.mockImportButton.addEventListener("click", mockImport);
elements.backToSourceButton.addEventListener("click", () => setStep("source"));
elements.backToReviewButton.addEventListener("click", () => setStep("review"));
elements.downloadJsonButton.addEventListener("click", downloadJson);

document.querySelectorAll(".step").forEach((button) => {
  button.addEventListener("click", () => {
    if (button.dataset.step === "review" && !state.testCases.length) {
      return;
    }
    if (button.dataset.step === "import" && !state.testCases.length) {
      return;
    }
    setStep(button.dataset.step);
  });
});

setStep("source");
