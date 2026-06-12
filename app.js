const state = {
  currentStep: "source",
  assumptions: [],
  questions: [],
  testCases: [],
  source: {},
  expandedTestIndex: null,
  generationSource: "frontend-fallback",
  storyImported: false,
  currentPage: 1,
  pageSize: 25,
  attachments: [],
  lastDryRunValid: false,
  reviewFilters: {
    platform: "",
    category: "",
    priority: ""
  },
  importScope: {
    coverage: {
      positive: true,
      negative: true,
      boundary: true,
      security: true,
      audit: true
    },
    priorities: {
      p1: true,
      p2: true,
      p3: true,
      p4: true,
      p5: true
    },
    platforms: {
      web: true,
      android: true,
      ios: true,
      api: true
    }
  },
  revisions: [],
  latestDiff: null
};

const PAGE_SIZE = 25;
const MAX_TESTS_PER_PLATFORM = 50;

const API_BASE_URL = "http://127.0.0.1:8000/api";

const elements = {
  appStatus: document.querySelector("#appStatus"),
  sourcePanel: document.querySelector("#sourcePanel"),
  reviewPanel: document.querySelector("#reviewPanel"),
  importPanel: document.querySelector("#importPanel"),
  importStoryButton: document.querySelector("#importStoryButton"),
  generateButton: document.querySelector("#generateButton"),
  resetButton: document.querySelector("#resetButton"),
  addTestButton: document.querySelector("#addTestButton"),
  refineButton: document.querySelector("#refineButton"),
  mockImportButton: document.querySelector("#mockImportButton"),
  realImportButton: document.querySelector("#realImportButton"),
  backToSourceButton: document.querySelector("#backToSourceButton"),
  backToReviewButton: document.querySelector("#backToReviewButton"),
  downloadJsonButton: document.querySelector("#downloadJsonButton"),
  assumptionsList: document.querySelector("#assumptionsList"),
  questionsList: document.querySelector("#questionsList"),
  revisionPanel: document.querySelector("#revisionPanel"),
  revisionSummary: document.querySelector("#revisionSummary"),
  revisionAddedList: document.querySelector("#revisionAddedList"),
  revisionRemovedList: document.querySelector("#revisionRemovedList"),
  revisionChangedList: document.querySelector("#revisionChangedList"),
  testList: document.querySelector("#testList"),
  sourceStatus: document.querySelector("#sourceStatus"),
  paginationBar: document.querySelector("#paginationBar"),
  paginationInfo: document.querySelector("#paginationInfo"),
  previousPageButton: document.querySelector("#previousPageButton"),
  nextPageButton: document.querySelector("#nextPageButton"),
  platformFilter: document.querySelector("#platformFilter"),
  categoryFilter: document.querySelector("#categoryFilter"),
  priorityFilter: document.querySelector("#priorityFilter"),
  importScopeTotal: document.querySelector("#importScopeTotal"),
  importScopeSummary: document.querySelector("#importScopeSummary"),
  attachmentPanel: document.querySelector("#attachmentPanel"),
  attachmentList: document.querySelector("#attachmentList"),
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

const priorityInputs = [
  "includeP1",
  "includeP2",
  "includeP3",
  "includeP4",
  "includeP5"
].map((id) => document.querySelector(`#${id}`));

const platformInputs = [
  "includeWeb",
  "includeAndroid",
  "includeIos",
  "includeApi"
].map((id) => document.querySelector(`#${id}`));

const importCoverageInputs = [
  "importPositive",
  "importNegative",
  "importBoundary",
  "importSecurity",
  "importAudit"
].map((id) => document.querySelector(`#${id}`));

const importPriorityInputs = [
  "importP1",
  "importP2",
  "importP3",
  "importP4",
  "importP5"
].map((id) => document.querySelector(`#${id}`));

const importPlatformInputs = [
  "importWeb",
  "importAndroid",
  "importIos",
  "importApi"
].map((id) => document.querySelector(`#${id}`));

function readSource() {
  return {
    organization: document.querySelector("#organization").value.trim(),
    project: document.querySelector("#project").value.trim(),
    storyId: document.querySelector("#storyId").value.trim(),
    storyTitle: document.querySelector("#storyTitle").value.trim(),
    acceptanceCriteria: document.querySelector("#acceptanceCriteria").value.trim(),
    additionalContext: document.querySelector("#additionalContext").value.trim(),
    attachments: state.attachments,
    coverage: Object.fromEntries(
      coverageInputs.map((input) => [input.id.replace("include", "").toLowerCase(), input.checked])
    ),
    priorities: Object.fromEntries(
      priorityInputs.map((input) => [input.id.replace("include", "").toLowerCase(), input.checked])
    ),
    platforms: Object.fromEntries(
      platformInputs.map((input) => {
        const key = input.id.replace("include", "").toLowerCase();
        return [key === "ios" ? "ios" : key, input.checked];
      })
    )
  };
}

function readImportTarget() {
  const suiteIdsByPlatform = {
    Web: document.querySelector("#webSuiteId").value.trim(),
    Android: document.querySelector("#androidSuiteId").value.trim(),
    iOS: document.querySelector("#iosSuiteId").value.trim(),
    API: document.querySelector("#apiSuiteId").value.trim()
  };
  return {
    testPlanId: document.querySelector("#testPlanId").value.trim(),
    testSuiteId: suiteIdsByPlatform.Web,
    suiteIdsByPlatform
  };
}

function applyImportTargetToSource() {
  state.source = {
    ...state.source,
    ...readImportTarget()
  };
}

function setStoryImported(imported, message) {
  state.storyImported = imported;
  elements.generateButton.disabled = !imported;
  elements.sourceStatus.textContent = message;
  elements.sourceStatus.classList.toggle("is-success", imported);
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
      priority: "P1",
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
      priority: "P1",
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
      priority: "P2",
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
      priority: "P5",
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
      priority: "P1",
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
      priority: "P3",
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

  tests.push(
    {
      title: "Verify confirmation screen displays correct payment summary",
      priority: "P4",
      category: "Positive",
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
    },
    {
      title: "Verify payment reference validation for unsupported characters",
      priority: "P3",
      category: "Negative",
      preconditions: ["User is authenticated", "Domestic payment form is open"],
      steps: [
        {
          action: "Enter unsupported characters in the payment reference field",
          expectedResult: "Reference validation message is displayed"
        },
        {
          action: "Attempt to continue",
          expectedResult: "User cannot proceed until the reference is corrected"
        }
      ]
    },
    {
      title: "Verify user can cancel payment before final confirmation",
      priority: "P4",
      category: "Regression",
      preconditions: ["User is authenticated", "Payment review screen is displayed"],
      steps: [
        {
          action: "Select cancel or back action before final confirmation",
          expectedResult: "Payment is not submitted"
        },
        {
          action: "Return to payments overview",
          expectedResult: "No new payment is created"
        }
      ]
    },
    {
      title: "Verify validation message is clear for invalid beneficiary account",
      priority: "P2",
      category: "Negative",
      preconditions: ["User is authenticated", "Domestic payment form is open"],
      steps: [
        {
          action: "Enter an invalid beneficiary account number",
          expectedResult: "Beneficiary account validation error is displayed"
        },
        {
          action: "Attempt to submit the payment",
          expectedResult: "Payment is not submitted"
        }
      ]
    },
    {
      title: "Verify payment amount accepts supported decimal precision",
      priority: "P3",
      category: "Boundary",
      preconditions: ["User is authenticated", "Domestic payment form is open"],
      steps: [
        {
          action: "Enter amount with supported decimal precision",
          expectedResult: "Amount is accepted"
        },
        {
          action: "Enter amount with unsupported decimal precision",
          expectedResult: "Amount validation message is displayed"
        }
      ]
    },
    {
      title: "Verify duplicate submit does not create duplicate payments",
      priority: "P1",
      category: "Security",
      preconditions: ["User is authenticated", "Valid payment data is entered"],
      steps: [
        {
          action: "Submit the payment and immediately attempt a second submit",
          expectedResult: "Only one payment request is created"
        },
        {
          action: "Check confirmation or status screen",
          expectedResult: "User sees one final payment confirmation"
        }
      ]
    },
    {
      title: "Verify payment form handles service unavailable response",
      priority: "P2",
      category: "Negative",
      preconditions: ["User is authenticated", "Payment service is unavailable"],
      steps: [
        {
          action: "Submit valid payment data",
          expectedResult: "User sees a clear service unavailable message"
        },
        {
          action: "Review payment status",
          expectedResult: "No confirmed payment is shown without successful processing"
        }
      ]
    },
    {
      title: "Verify mandatory field error messages disappear after correction",
      priority: "P5",
      category: "Regression",
      preconditions: ["User is authenticated", "Mandatory field errors are visible"],
      steps: [
        {
          action: "Correct all mandatory fields",
          expectedResult: "Validation messages are removed"
        },
        {
          action: "Continue to review screen",
          expectedResult: "Review screen is displayed"
        }
      ]
    },
    {
      title: "Verify screen data is preserved when returning from review to form",
      priority: "P4",
      category: "Regression",
      preconditions: ["User is authenticated", "Payment review screen is displayed"],
      steps: [
        {
          action: "Return from payment review to payment form",
          expectedResult: "Previously entered payment data is still displayed"
        },
        {
          action: "Continue again to review screen",
          expectedResult: "Updated review data is displayed"
        }
      ]
    },
    {
      title: "Verify audit record exists for failed payment submission",
      priority: "P3",
      category: "Audit",
      preconditions: ["Audit logging is enabled", "Payment submission fails"],
      steps: [
        {
          action: "Submit payment data that triggers a failure",
          expectedResult: "Failure is displayed to the user"
        },
        {
          action: "Check audit record for failed submission",
          expectedResult: "Audit record contains user, timestamp, action and failure result"
        }
      ]
    }
  );

  return limitTests(
    filterTestsByPlatform(
      filterTestsByPriority(filterTestsByCoverage(tests, source.coverage), source.priorities),
      source.platforms
    ),
    MAX_TESTS_PER_PLATFORM
  );
}

async function generateTests() {
  state.source = readSource();
  if (!state.storyImported) {
    alert("Import the user story before generating tests.");
    return;
  }

  state.pageSize = PAGE_SIZE;
  state.currentPage = 1;
  state.lastDryRunValid = false;
  elements.realImportButton.disabled = true;
  elements.generateButton.disabled = true;
  elements.generateButton.textContent = "Generating...";

  try {
    const response = await requestBackendGeneration(state.source);
    applyGenerationResponse(response);
  } catch (error) {
    console.error("AI generation failed.", error);
    alert(`AI generation failed. ${error.message}`);
    return;
  } finally {
    elements.generateButton.disabled = false;
    elements.generateButton.textContent = "Generate tests";
  }

  state.expandedTestIndex = null;
  renderReview();
  setStep("review");
}

async function importStory() {
  const source = readSource();
  if (!source.storyId) {
    alert("Enter a User Story ID first.");
    return;
  }

  elements.importStoryButton.disabled = true;
  elements.importStoryButton.textContent = "Importing...";
  setStoryImported(false, "Importing story from Azure DevOps...");

  try {
    const story = await requestBackendStory(source.storyId);
    document.querySelector("#storyTitle").value = story.title || "";
    document.querySelector("#acceptanceCriteria").value = story.acceptanceCriteria || story.description || "";
    state.attachments = story.attachments || [];
    renderAttachments();
    setStoryImported(true, `Imported ${story.workItemType} #${story.id}: ${story.title}`);
  } catch (error) {
    console.error("Story import failed.", error);
    setStoryImported(false, "Story import failed. Check that the backend is running and the token is valid.");
    alert("Story import failed. Start the backend and try again.");
  } finally {
    elements.importStoryButton.disabled = false;
    elements.importStoryButton.textContent = "Import story";
  }
}

async function requestBackendStory(storyId) {
  const response = await fetch(`${API_BASE_URL}/azure/work-items/${encodeURIComponent(storyId)}`);

  if (!response.ok) {
    throw new Error(`Story import API returned ${response.status}`);
  }

  return response.json();
}

async function requestBackendGeneration(source) {
  const response = await fetch(`${API_BASE_URL}/generations/ai`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      azure: {
        organization: source.organization,
        project: source.project,
        storyId: source.storyId
      },
      story: {
        title: source.storyTitle,
        acceptanceCriteria: source.acceptanceCriteria,
        additionalContext: source.additionalContext,
        attachments: source.attachments
      },
      figma: {
        enabled: false,
        links: [],
        screens: []
      },
      generationPolicy: {
        domain: "fintech",
        testStyle: "manual",
        coverage: source.coverage,
        priorities: source.priorities,
        platforms: source.platforms,
        maxTestCasesPerPlatform: MAX_TESTS_PER_PLATFORM
      }
    })
  });

  if (!response.ok) {
    let message = `Generation API returned ${response.status}`;
    try {
      const errorPayload = await response.json();
      if (errorPayload.detail) {
        message = errorPayload.detail;
      }
    } catch (error) {
      console.warn("Generation API error response was not JSON.", error);
    }
    throw new Error(message);
  }

  return response.json();
}

function readRefinementNotes() {
  return {
    clarifiedBusinessRules: document.querySelector("#clarifiedBusinessRules").value.trim(),
    coverageGaps: document.querySelector("#coverageGaps").value.trim(),
    testsToAvoidOrChange: document.querySelector("#testsToAvoidOrChange").value.trim(),
    additionalInstruction: document.querySelector("#additionalRefinementInstruction").value.trim()
  };
}

function hasRefinementNotes(notes) {
  return Object.values(notes).some(Boolean);
}

async function refineTests() {
  state.source = { ...state.source, ...readSource() };
  const refinementNotes = readRefinementNotes();
  if (!state.testCases.length) {
    alert("Generate tests before using AI refinement.");
    return;
  }
  if (!hasRefinementNotes(refinementNotes)) {
    alert("Add at least one refinement note before sending to AI.");
    return;
  }

  elements.refineButton.disabled = true;
  elements.refineButton.textContent = "Refining...";

  try {
    const previousSnapshot = createRevisionSnapshot("Before refinement", state.testCases);
    const response = await requestBackendRefinement(state.source, refinementNotes);
    applyGenerationResponse(response, { preserveRevisionHistory: true, preserveImportScope: true });
    const currentSnapshot = createRevisionSnapshot("Refined with AI", state.testCases);
    state.revisions.push(previousSnapshot, currentSnapshot);
    state.latestDiff = diffTestCases(previousSnapshot.testCases, currentSnapshot.testCases);
    invalidateDryRun();
    state.currentPage = 1;
    state.expandedTestIndex = null;
    renderReview();
  } catch (error) {
    alert(`AI refinement failed. ${error.message}`);
  } finally {
    elements.refineButton.disabled = false;
    elements.refineButton.textContent = "Refine with AI";
  }
}

async function requestBackendRefinement(source, refinementNotes) {
  const response = await fetch(`${API_BASE_URL}/generations/refine`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      azure: {
        organization: source.organization,
        project: source.project,
        storyId: source.storyId
      },
      story: {
        title: source.storyTitle,
        acceptanceCriteria: source.acceptanceCriteria,
        additionalContext: source.additionalContext,
        attachments: source.attachments
      },
      figma: {
        enabled: false,
        links: [],
        screens: []
      },
      generationPolicy: {
        domain: "fintech",
        testStyle: "manual",
        coverage: source.coverage,
        priorities: source.priorities,
        platforms: source.platforms,
        maxTestCasesPerPlatform: MAX_TESTS_PER_PLATFORM
      },
      currentTestCases: state.testCases,
      currentAssumptions: state.assumptions,
      currentQuestionsForBA: state.questions,
      refinementNotes
    })
  });

  if (!response.ok) {
    let message = `Refinement API returned ${response.status}`;
    try {
      const errorPayload = await response.json();
      if (errorPayload.detail) {
        message = errorPayload.detail;
      }
    } catch (error) {
      console.warn("Refinement API error response was not JSON.", error);
    }
    throw new Error(message);
  }

  return response.json();
}

function applyGenerationResponse(response, options = {}) {
  resetReviewFilters();
  if (!options.preserveRevisionHistory) {
    resetRevisionHistory();
  }
  if (!options.preserveImportScope) {
    resetImportScope();
  }
  state.assumptions = response.assumptions || [];
  state.questions = response.questionsForBA || [];
  state.testCases = (response.testCases || []).map((testCase) => ({
    title: testCase.title,
    platform: testCase.platform || "Web",
    priority: testCase.priority,
    category: testCase.category,
    preconditions: testCase.preconditions || [],
    steps: (testCase.steps || []).map((step) => ({
      action: step.action,
      expectedResult: step.expectedResult
    }))
  }));
  state.generationSource = response.generationSource || "backend";
}

function applyFrontendGenerationFallback() {
  resetReviewFilters();
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
  state.generationSource = "frontend-fallback";
}

function renderList(listElement, items) {
  listElement.replaceChildren();
  items.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    listElement.appendChild(li);
  });
}

function renderAttachments() {
  elements.attachmentList.replaceChildren();
  elements.attachmentPanel.classList.toggle("is-hidden", !state.attachments.length);

  if (!state.attachments.length) {
    return;
  }

  state.attachments.forEach((attachment, index) => {
    const row = document.createElement("div");
    row.className = "attachment-row";
    const textLength = attachment.text ? attachment.text.length : 0;
    row.innerHTML = `
      <div>
        <strong>${escapeHtml(attachment.name)}</strong>
        <span>${escapeHtml(attachment.extractionStatus || "not-extracted")} · ${textLength} chars extracted</span>
      </div>
      <button class="compact-action" type="button">Remove</button>
    `;
    row.querySelector("button").addEventListener("click", () => {
      state.attachments.splice(index, 1);
      renderAttachments();
      setStoryImported(true, "Attachment list updated. Generate tests with the remaining documentation.");
    });
    elements.attachmentList.appendChild(row);
  });
}

function renderReview() {
  renderList(elements.assumptionsList, state.assumptions);
  renderList(elements.questionsList, state.questions);
  renderRevisionHistory();
  renderImportScopeSummary();
  elements.testList.replaceChildren();

  const filteredEntries = getFilteredTestEntries();
  const totalPages = getTotalPages();
  state.currentPage = Math.min(Math.max(state.currentPage, 1), totalPages);
  const startIndex = (state.currentPage - 1) * state.pageSize;
  const visibleEntries = filteredEntries.slice(startIndex, startIndex + state.pageSize);

  visibleEntries.forEach(({ testCase, index: absoluteIndex }) => {
    renderTestRows(testCase, absoluteIndex).forEach((row) => elements.testList.appendChild(row));
  });

  renderPagination();
  elements.appStatus.textContent = `${filteredEntries.length}/${state.testCases.length} tests`;
}

function renderPagination() {
  const filteredCount = getFilteredTestEntries().length;
  const totalPages = getTotalPages();
  const start = filteredCount ? (state.currentPage - 1) * state.pageSize + 1 : 0;
  const end = Math.min(state.currentPage * state.pageSize, filteredCount);

  elements.paginationInfo.textContent = `Showing ${start}-${end} of ${filteredCount} filtered tests. Total ${state.testCases.length}. Page ${state.currentPage} of ${totalPages}.`;
  elements.previousPageButton.disabled = state.currentPage <= 1;
  elements.nextPageButton.disabled = state.currentPage >= totalPages;
  elements.paginationBar.classList.toggle("is-hidden", filteredCount <= state.pageSize);
}

function getTotalPages() {
  return Math.max(1, Math.ceil(getFilteredTestEntries().length / state.pageSize));
}

function getFilteredTestEntries() {
  return state.testCases
    .map((testCase, index) => ({ testCase, index }))
    .filter(({ testCase }) => {
      const platform = testCase.platform || "Web";
      return (
        (!state.reviewFilters.platform || platform === state.reviewFilters.platform) &&
        (!state.reviewFilters.category || testCase.category === state.reviewFilters.category) &&
        (!state.reviewFilters.priority || testCase.priority === state.reviewFilters.priority)
      );
    });
}

function readImportScope() {
  return {
    coverage: Object.fromEntries(
      importCoverageInputs.map((input) => [input.id.replace("import", "").toLowerCase(), input.checked])
    ),
    priorities: Object.fromEntries(
      importPriorityInputs.map((input) => [input.id.replace("import", "").toLowerCase(), input.checked])
    ),
    platforms: Object.fromEntries(
      importPlatformInputs.map((input) => {
        const key = input.id.replace("import", "").toLowerCase();
        return [key === "ios" ? "ios" : key, input.checked];
      })
    )
  };
}

function getImportScopedTestCases() {
  return filterTestsByPlatform(
    filterTestsByPriority(filterTestsByCoverage(state.testCases, state.importScope.coverage), state.importScope.priorities),
    state.importScope.platforms
  );
}

function renderImportScopeSummary() {
  const selectedTests = getImportScopedTestCases();
  const summary = buildImportScopeSummary(selectedTests);
  elements.importScopeTotal.textContent = `${selectedTests.length} of ${state.testCases.length} selected`;
  elements.importScopeSummary.replaceChildren();

  const platforms = ["Web", "Android", "iOS", "API"];
  platforms.forEach((platform) => {
    elements.importScopeSummary.appendChild(renderImportScopeRow(platform, summary.platforms[platform]));
  });
  elements.importScopeSummary.appendChild(renderImportScopeRow("Total", summary.total, true));
}

function buildImportScopeSummary(testCases) {
  const priorities = ["P1", "P2", "P3", "P4", "P5"];
  const platforms = ["Web", "Android", "iOS", "API"];
  const summary = {
    platforms: Object.fromEntries(platforms.map((platform) => [platform, createPriorityCounts()])),
    total: createPriorityCounts()
  };

  testCases.forEach((testCase) => {
    const platform = testCase.platform || "Web";
    const priority = testCase.priority;
    if (!summary.platforms[platform] || !priorities.includes(priority)) {
      return;
    }
    summary.platforms[platform][priority] += 1;
    summary.platforms[platform].total += 1;
    summary.total[priority] += 1;
    summary.total.total += 1;
  });

  return summary;
}

function createPriorityCounts() {
  return {
    P1: 0,
    P2: 0,
    P3: 0,
    P4: 0,
    P5: 0,
    total: 0
  };
}

function renderImportScopeRow(label, counts, isTotal = false) {
  const row = document.createElement("tr");
  if (isTotal) {
    row.className = "scope-total-row";
  }
  row.innerHTML = `
    <th scope="row">${escapeHtml(label)}</th>
    <td>${counts.P1}</td>
    <td>${counts.P2}</td>
    <td>${counts.P3}</td>
    <td>${counts.P4}</td>
    <td>${counts.P5}</td>
    <td>${counts.total}</td>
  `;
  return row;
}

function createRevisionSnapshot(label, testCases) {
  return {
    label,
    createdAt: new Date().toISOString(),
    testCases: cloneTestCases(testCases)
  };
}

function cloneTestCases(testCases) {
  return testCases.map((testCase) => ({
    title: testCase.title,
    platform: testCase.platform || "Web",
    priority: testCase.priority,
    category: testCase.category,
    preconditions: [...(testCase.preconditions || [])],
    steps: (testCase.steps || []).map((step) => ({
      action: step.action,
      expectedResult: step.expectedResult
    }))
  }));
}

function diffTestCases(previousTests, currentTests) {
  const previousMap = new Map(previousTests.map((testCase) => [testCaseDiffKey(testCase), testCase]));
  const currentMap = new Map(currentTests.map((testCase) => [testCaseDiffKey(testCase), testCase]));
  const added = [];
  const removed = [];
  const changed = [];

  currentMap.forEach((testCase, key) => {
    const previous = previousMap.get(key);
    if (!previous) {
      added.push(testCase);
      return;
    }
    const changes = describeTestChanges(previous, testCase);
    if (changes.length) {
      changed.push({ before: previous, after: testCase, changes });
    }
  });

  previousMap.forEach((testCase, key) => {
    if (!currentMap.has(key)) {
      removed.push(testCase);
    }
  });

  return {
    added,
    removed,
    changed,
    unchanged: currentTests.length - added.length - changed.length
  };
}

function testCaseDiffKey(testCase) {
  return `${testCase.platform || "Web"}::${normalizeTitle(testCase.title)}`;
}

function normalizeTitle(title) {
  return String(title || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function describeTestChanges(previous, current) {
  const changes = [];
  if (previous.priority !== current.priority) {
    changes.push(`Priority ${previous.priority} -> ${current.priority}`);
  }
  if (previous.category !== current.category) {
    changes.push(`Category ${previous.category} -> ${current.category}`);
  }
  if (JSON.stringify(previous.preconditions || []) !== JSON.stringify(current.preconditions || [])) {
    changes.push("Preconditions changed");
  }
  if (JSON.stringify(previous.steps || []) !== JSON.stringify(current.steps || [])) {
    changes.push("Steps changed");
  }
  return changes;
}

function renderRevisionHistory() {
  const diff = state.latestDiff;
  elements.revisionPanel.classList.toggle("is-hidden", !diff);
  if (!diff) {
    return;
  }

  elements.revisionSummary.textContent = `Added ${diff.added.length} | Removed ${diff.removed.length} | Changed ${diff.changed.length} | Unchanged ${diff.unchanged}`;
  renderRevisionList(elements.revisionAddedList, diff.added.map(formatTestCaseRef));
  renderRevisionList(elements.revisionRemovedList, diff.removed.map(formatTestCaseRef));
  renderRevisionList(
    elements.revisionChangedList,
    diff.changed.map((item) => `${formatTestCaseRef(item.after)} - ${item.changes.join(", ")}`)
  );
}

function renderRevisionList(listElement, items) {
  listElement.replaceChildren();
  if (!items.length) {
    const li = document.createElement("li");
    li.textContent = "None";
    listElement.appendChild(li);
    return;
  }
  items.slice(0, 10).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    listElement.appendChild(li);
  });
  if (items.length > 10) {
    const li = document.createElement("li");
    li.textContent = `+${items.length - 10} more`;
    listElement.appendChild(li);
  }
}

function formatTestCaseRef(testCase) {
  return `[${testCase.platform || "Web"}][${testCase.category}][${testCase.priority}] ${testCase.title}`;
}

function renderTestRows(testCase, index) {
  const template = document.querySelector("#testCaseTemplate");
  const fragment = template.content.cloneNode(true);
  const summaryRow = fragment.querySelector(".test-summary-row");
  const detailRow = fragment.querySelector(".test-detail-row");
  const toggleButton = fragment.querySelector(".toggle-test");
  const titleCell = fragment.querySelector(".test-summary-title");
  const platformCell = fragment.querySelector(".test-summary-platform");
  const categoryCell = fragment.querySelector(".test-summary-category");
  const priorityCell = fragment.querySelector(".test-summary-priority");

  summaryRow.querySelector(".test-number").textContent = index + 1;
  titleCell.textContent = testCase.title;
  platformCell.textContent = testCase.platform || "Web";
  categoryCell.textContent = testCase.category;
  priorityCell.textContent = testCase.priority;

  const isExpanded = state.expandedTestIndex === index;
  detailRow.classList.toggle("is-hidden", !isExpanded);
  toggleButton.textContent = isExpanded ? "Close" : "Open";
  toggleButton.setAttribute("aria-expanded", String(isExpanded));

  toggleButton.addEventListener("click", () => {
    state.expandedTestIndex = isExpanded ? null : index;
    renderReview();
  });

  detailRow.querySelector(".test-title").value = testCase.title;
  detailRow.querySelector(".test-platform").value = testCase.platform || "Web";
  detailRow.querySelector(".test-priority").value = testCase.priority;
  detailRow.querySelector(".test-category").value = testCase.category;
  detailRow.querySelector(".test-preconditions").value = testCase.preconditions.join("\n");

  detailRow.querySelector(".test-title").addEventListener("input", (event) => {
    invalidateDryRun();
    state.testCases[index].title = event.target.value;
    titleCell.textContent = event.target.value;
  });
  detailRow.querySelector(".test-priority").addEventListener("change", (event) => {
    invalidateDryRun();
    state.testCases[index].priority = event.target.value;
    priorityCell.textContent = event.target.value;
    renderImportScopeSummary();
  });
  detailRow.querySelector(".test-platform").addEventListener("change", (event) => {
    invalidateDryRun();
    state.testCases[index].platform = event.target.value;
    platformCell.textContent = event.target.value;
    renderImportScopeSummary();
  });
  detailRow.querySelector(".test-category").addEventListener("change", (event) => {
    invalidateDryRun();
    state.testCases[index].category = event.target.value;
    categoryCell.textContent = event.target.value;
    renderImportScopeSummary();
  });
  detailRow.querySelector(".test-preconditions").addEventListener("input", (event) => {
    invalidateDryRun();
    state.testCases[index].preconditions = splitLines(event.target.value);
  });
  detailRow.querySelector(".delete-test").addEventListener("click", () => {
    invalidateDryRun();
    state.testCases.splice(index, 1);
    state.expandedTestIndex = null;
    renderReview();
  });
  detailRow.querySelector(".add-step").addEventListener("click", () => {
    invalidateDryRun();
    state.testCases[index].steps.push({
      action: "New action",
      expectedResult: "Expected result"
    });
    renderReview();
  });

  const stepsList = detailRow.querySelector(".steps-list");
  testCase.steps.forEach((step, stepIndex) => {
    stepsList.appendChild(renderStepRow(step, index, stepIndex));
  });

  return [summaryRow, detailRow];
}

function renderStepRow(step, testIndex, stepIndex) {
  const template = document.querySelector("#stepTemplate");
  const row = template.content.firstElementChild.cloneNode(true);

  row.querySelector(".step-action").value = step.action;
  row.querySelector(".step-expected").value = step.expectedResult;
  row.querySelector(".step-action").addEventListener("input", (event) => {
    invalidateDryRun();
    state.testCases[testIndex].steps[stepIndex].action = event.target.value;
  });
  row.querySelector(".step-expected").addEventListener("input", (event) => {
    invalidateDryRun();
    state.testCases[testIndex].steps[stepIndex].expectedResult = event.target.value;
  });
  row.querySelector(".delete-step").addEventListener("click", () => {
    invalidateDryRun();
    state.testCases[testIndex].steps.splice(stepIndex, 1);
    renderReview();
  });

  return row;
}

function invalidateDryRun() {
  state.lastDryRunValid = false;
  elements.realImportButton.disabled = true;
}

function resetReviewFilters() {
  state.reviewFilters = {
    platform: "",
    category: "",
    priority: ""
  };
  elements.platformFilter.value = "";
  elements.categoryFilter.value = "";
  elements.priorityFilter.value = "";
}

function resetRevisionHistory() {
  state.revisions = [];
  state.latestDiff = null;
}

function resetImportScope() {
  importCoverageInputs.forEach((input) => {
    const key = input.id.replace("import", "").toLowerCase();
    input.checked = state.source.coverage?.[key] ?? true;
  });
  importPriorityInputs.forEach((input) => {
    const key = input.id.replace("import", "").toLowerCase();
    input.checked = state.source.priorities?.[key] ?? true;
  });
  importPlatformInputs.forEach((input) => {
    const key = input.id.replace("import", "").toLowerCase();
    input.checked = state.source.platforms?.[key === "ios" ? "ios" : key] ?? true;
  });
  state.importScope = readImportScope();
}

function handleImportScopeChange() {
  state.importScope = readImportScope();
  invalidateDryRun();
  renderImportScopeSummary();
}

function resetRefinementNotes() {
  document.querySelector("#clarifiedBusinessRules").value = "";
  document.querySelector("#coverageGaps").value = "";
  document.querySelector("#testsToAvoidOrChange").value = "";
  document.querySelector("#additionalRefinementInstruction").value = "";
}

function splitLines(value) {
  return value
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function addEmptyTestCase() {
  invalidateDryRun();
  state.testCases.push({
    title: "New test case",
    platform: "Web",
    priority: "P3",
    category: "Positive",
    preconditions: ["User is authenticated"],
    steps: [
      {
        action: "Perform action",
        expectedResult: "Expected result is observed"
      }
    ]
  });
  state.expandedTestIndex = state.testCases.length - 1;
  state.currentPage = getTotalPages();
  renderReview();
}

function validateBeforeImport() {
  const errors = [];
  const platformsInTests = new Set();
  const testCases = getImportScopedTestCases();
  if (!testCases.length) {
    errors.push("Select at least one test case in Import scope before import.");
  }
  testCases.forEach((testCase, index) => {
    platformsInTests.add(testCase.platform || "Web");
    if (!testCase.title.trim()) {
      errors.push(`Test case ${index + 1} needs a title.`);
    }
    if (!(testCase.platform || "").trim()) {
      errors.push(`Test case ${index + 1} needs a platform.`);
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
  platformsInTests.forEach((platform) => {
    if (!state.source.suiteIdsByPlatform?.[platform]) {
      errors.push(`${platform} tests need a ${platform} Suite ID before import.`);
    }
  });
  return errors;
}

async function mockImport() {
  state.source = { ...state.source, ...readSource() };
  applyImportTargetToSource();
  state.importScope = readImportScope();
  const errors = validateBeforeImport();
  if (errors.length) {
    alert(errors.join("\n"));
    return;
  }

  state.lastDryRunValid = false;
  elements.realImportButton.disabled = true;
  elements.mockImportButton.disabled = true;
  elements.mockImportButton.textContent = "Validating...";

  try {
    const response = await requestBackendImport();
    renderImportResult(response);
  } catch (error) {
    console.warn("Backend import unavailable, using frontend fallback.", error);
    renderFrontendImportFallback();
  } finally {
    elements.mockImportButton.disabled = false;
    elements.mockImportButton.textContent = "Dry run Azure import";
  }

  setStep("import");
}

async function realAzureImport() {
  state.source = { ...state.source, ...readSource() };
  applyImportTargetToSource();
  state.importScope = readImportScope();
  const errors = validateBeforeImport();
  if (errors.length) {
    alert(errors.join("\n"));
    return;
  }
  if (!state.lastDryRunValid) {
    alert("Run a successful Azure dry run before real import.");
    return;
  }

  const scopedTestCases = getImportScopedTestCases();
  const confirmed = window.confirm(
    `This will create ${scopedTestCases.length} real Azure DevOps test cases.\n\n` +
      `Story ID: ${state.source.storyId}\n` +
      `Test Plan ID: ${state.source.testPlanId}\n` +
      `Suite mapping:\n${formatSuiteMapping(state.source.suiteIdsByPlatform)}\n\n` +
      "Continue with real Azure import?"
  );
  if (!confirmed) {
    return;
  }

  elements.realImportButton.disabled = true;
  elements.realImportButton.textContent = "Importing...";

  try {
    const response = await requestBackendImport("/imports/azure");
    renderImportResult(response);
    setStep("import");
    showRealImportCompletion(response);
  } catch (error) {
    alert(`Real Azure import failed. ${error.message}`);
  } finally {
    elements.realImportButton.disabled = false;
    elements.realImportButton.textContent = "Real Azure import";
  }
}

async function requestBackendImport(path = "/imports/azure/dry-run") {
  const scopedTestCases = getImportScopedTestCases();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      sourceWorkItemId: state.source.storyId,
      target: {
        testPlanId: state.source.testPlanId,
        testSuiteId: state.source.testSuiteId,
        suiteIdsByPlatform: state.source.suiteIdsByPlatform
      },
      testCases: scopedTestCases
    })
  });

  if (!response.ok) {
    let message = `Import API returned ${response.status}`;
    try {
      const errorPayload = await response.json();
      if (errorPayload.detail) {
        message = errorPayload.detail;
      }
    } catch (error) {
      console.warn("Import API error response was not JSON.", error);
    }
    throw new Error(message);
  }

  return response.json();
}

function renderImportResult(response) {
  const created = response.createdTestCases || response.plannedTestCases || [];
  const validations = response.validations || [];
  const isDryRun = Boolean(response.plannedTestCases);
  state.lastDryRunValid = isDryRun ? response.status === "valid" : state.lastDryRunValid;
  elements.realImportButton.disabled = !state.lastDryRunValid;
  elements.resultSummary.className = `result-summary ${getImportResultClass(response.status, isDryRun)}`;
  elements.resultSummary.innerHTML = `
    <strong>${getImportResultTitle(response, created.length, isDryRun)}</strong>
    <p>${escapeHtml(response.message || "Ready for Azure DevOps import.")}</p>
    ${isDryRun ? `<p>Target plan ${escapeHtml(response.testPlanId)}${response.testPlanName ? ` (${escapeHtml(response.testPlanName)})` : ""}. ${escapeHtml(formatDryRunSuiteNames(response))}</p>` : ""}
  `;

  elements.resultList.replaceChildren();
  validations.forEach((validation) => {
    const row = document.createElement("div");
    row.className = "result-row";
    row.innerHTML = `
      <span>${escapeHtml(validation.name)}: ${escapeHtml(validation.message)}</span>
      <span class="result-id">${escapeHtml(validation.status)}</span>
    `;
    elements.resultList.appendChild(row);
  });

  created.forEach((item) => {
    const row = document.createElement("div");
    row.className = "result-row";
    row.innerHTML = `
      <span>${escapeHtml(item.title)}</span>
      <span class="result-id">${escapeHtml(item.platform || "Web")} - ${isDryRun ? `Would create #${item.sequence}` : `Azure ID ${item.id}`}</span>
    `;
    elements.resultList.appendChild(row);
  });
}

function getImportResultTitle(response, count, isDryRun) {
  if (isDryRun) {
    return "Azure dry run completed";
  }
  if (response.status === "imported") {
    return `Import completed successfully. ${count} test cases imported to Azure DevOps.`;
  }
  if (response.status === "partially-imported") {
    return `Import partially completed. ${count} test cases imported to Azure DevOps.`;
  }
  return "Azure import completed with issues.";
}

function getImportResultClass(status, isDryRun) {
  if (isDryRun) {
    return status === "valid" ? "is-success" : "is-warning";
  }
  if (status === "imported") {
    return "is-success";
  }
  return "is-warning";
}

function showRealImportCompletion(response) {
  const created = response.createdTestCases || [];
  if (response.status === "imported") {
    alert(`Azure import completed successfully. ${created.length} test cases were imported.`);
    return;
  }
  if (response.status === "partially-imported") {
    alert(`Azure import partially completed. ${created.length} test cases were imported. Check Import result details.`);
    return;
  }
  alert("Azure import finished with issues. No test cases were imported. Check Import result details.");
}

function formatSuiteMapping(mapping) {
  return Object.entries(mapping || {})
    .filter(([, suiteId]) => suiteId)
    .map(([platform, suiteId]) => `${platform}: ${suiteId}`)
    .join("\n");
}

function formatDryRunSuiteNames(response) {
  const suiteNames = response.suiteNamesByPlatform || {};
  return Object.entries(suiteNames)
    .map(([platform, name]) => `${platform} suite: ${name}`)
    .join(" | ");
}

function renderFrontendImportFallback() {
  const baseId = 55000 + Number(state.source.storyId || 1);
  const created = getImportScopedTestCases().map((testCase, index) => ({
    id: baseId + index,
    title: testCase.title,
    platform: testCase.platform || "Web",
    category: testCase.category
  }));

  elements.resultSummary.innerHTML = `
    <strong>${created.length} test cases ready for Azure DevOps import.</strong>
    <p>Target plan ${escapeHtml(state.source.testPlanId)}. ${escapeHtml(formatSuiteMapping(state.source.suiteIdsByPlatform))}</p>
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
}

function downloadJson() {
  const payload = {
    source: state.source,
    assumptions: state.assumptions,
    questionsForBA: state.questions,
    testCases: state.testCases,
    importScope: state.importScope,
    importScopedTestCases: getImportScopedTestCases()
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
  state.expandedTestIndex = null;
  state.currentPage = 1;
  state.attachments = [];
  state.lastDryRunValid = false;
  resetRevisionHistory();
  elements.realImportButton.disabled = true;
  resetReviewFilters();
  resetImportScope();
  resetRefinementNotes();
  renderAttachments();
  setStoryImported(false, "Import the story before generating tests.");
  document.querySelector("#storyTitle").value = "";
  document.querySelector("#acceptanceCriteria").value = "";
  document.querySelector("#additionalContext").value = "";
  setStep("source");
}

function limitTests(tests, maxCount) {
  const platformCounts = new Map();
  return tests.filter((test) => {
    const platform = test.platform || "Web";
    const count = platformCounts.get(platform) || 0;
    if (count >= maxCount) {
      return false;
    }
    platformCounts.set(platform, count + 1);
    return true;
  });
}

function filterTestsByCoverage(tests, coverage) {
  const allowedCategories = new Set();
  if (coverage.positive) {
    allowedCategories.add("Positive");
  }
  if (coverage.negative) {
    allowedCategories.add("Negative");
  }
  if (coverage.boundary) {
    allowedCategories.add("Boundary");
  }
  if (coverage.security) {
    allowedCategories.add("Security");
  }
  if (coverage.audit) {
    allowedCategories.add("Audit");
  }
  return tests.filter((test) => allowedCategories.has(test.category));
}

function filterTestsByPriority(tests, priorities) {
  const allowedPriorities = new Set();
  if (priorities.p1) {
    allowedPriorities.add("P1");
  }
  if (priorities.p2) {
    allowedPriorities.add("P2");
  }
  if (priorities.p3) {
    allowedPriorities.add("P3");
  }
  if (priorities.p4) {
    allowedPriorities.add("P4");
  }
  if (priorities.p5) {
    allowedPriorities.add("P5");
  }
  return tests.filter((test) => allowedPriorities.has(test.priority));
}

function filterTestsByPlatform(tests, platforms) {
  const allowedPlatforms = new Set();
  if (platforms.web) {
    allowedPlatforms.add("Web");
  }
  if (platforms.android) {
    allowedPlatforms.add("Android");
  }
  if (platforms.ios) {
    allowedPlatforms.add("iOS");
  }
  if (platforms.api) {
    allowedPlatforms.add("API");
  }
  return tests.filter((test) => allowedPlatforms.has(test.platform || "Web"));
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

elements.importStoryButton.addEventListener("click", importStory);
elements.generateButton.addEventListener("click", generateTests);
elements.resetButton.addEventListener("click", resetDraft);
elements.addTestButton.addEventListener("click", addEmptyTestCase);
elements.refineButton.addEventListener("click", refineTests);
elements.mockImportButton.addEventListener("click", mockImport);
elements.realImportButton.addEventListener("click", realAzureImport);
elements.backToSourceButton.addEventListener("click", () => setStep("source"));
elements.backToReviewButton.addEventListener("click", () => setStep("review"));
elements.downloadJsonButton.addEventListener("click", downloadJson);
[
  [elements.platformFilter, "platform"],
  [elements.categoryFilter, "category"],
  [elements.priorityFilter, "priority"]
].forEach(([select, key]) => {
  select.addEventListener("change", () => {
    state.reviewFilters[key] = select.value;
    state.currentPage = 1;
    state.expandedTestIndex = null;
    renderReview();
  });
});

[...importCoverageInputs, ...importPriorityInputs, ...importPlatformInputs].forEach((input) => {
  input.addEventListener("change", handleImportScopeChange);
});

elements.previousPageButton.addEventListener("click", () => {
  state.currentPage = Math.max(1, state.currentPage - 1);
  state.expandedTestIndex = null;
  renderReview();
});
elements.nextPageButton.addEventListener("click", () => {
  state.currentPage = Math.min(getTotalPages(), state.currentPage + 1);
  state.expandedTestIndex = null;
  renderReview();
});

["storyId", "organization", "project"].forEach((id) => {
  document.querySelector(`#${id}`).addEventListener("input", () => {
    state.attachments = [];
    renderAttachments();
    setStoryImported(false, "Story source changed. Import the story again before generating tests.");
  });
});

[
  "testPlanId",
  "webSuiteId",
  "androidSuiteId",
  "iosSuiteId",
  "apiSuiteId",
  "includeWeb",
  "includeAndroid",
  "includeIos",
  "includeApi"
].forEach((id) => {
  document.querySelector(`#${id}`).addEventListener("input", invalidateDryRun);
  document.querySelector(`#${id}`).addEventListener("change", invalidateDryRun);
});

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

setStoryImported(false, "Import the story before generating tests.");
setStep("source");
