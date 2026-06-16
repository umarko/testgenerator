from pydantic import BaseModel, Field


class CoverageOptions(BaseModel):
    positive: bool = True
    negative: bool = True
    boundary: bool = True
    security: bool = True
    audit: bool = True
    regression: bool = True


class PriorityOptions(BaseModel):
    p1: bool = True
    p2: bool = True
    p3: bool = True
    p4: bool = True
    p5: bool = True


class PlatformOptions(BaseModel):
    web: bool = True
    android: bool = True
    ios: bool = True
    api: bool = False


class AzureSource(BaseModel):
    organization: str = ""
    project: str = ""
    story_id: str = Field(default="", alias="storyId")
    test_plan_id: str = Field(default="", alias="testPlanId")
    test_suite_id: str = Field(default="", alias="testSuiteId")


class StoryContext(BaseModel):
    title: str = ""
    acceptance_criteria: str = Field(default="", alias="acceptanceCriteria")
    additional_context: str = Field(default="", alias="additionalContext")
    attachments: list["WorkItemAttachment"] = Field(default_factory=list)


class FigmaContext(BaseModel):
    enabled: bool = False
    links: list[str] = Field(default_factory=list)
    screens: list[dict] = Field(default_factory=list)


class GenerationPolicy(BaseModel):
    domain: str = "fintech"
    test_style: str = Field(default="manual", alias="testStyle")
    max_test_cases_per_platform: int = Field(default=50, alias="maxTestCasesPerPlatform", ge=1, le=50)
    coverage: CoverageOptions = Field(default_factory=CoverageOptions)
    priorities: PriorityOptions = Field(default_factory=PriorityOptions)
    platforms: PlatformOptions = Field(default_factory=PlatformOptions)


class SourceEvidence(BaseModel):
    source_type: str = Field(alias="sourceType")
    source_name: str = Field(default="", alias="sourceName")
    evidence: str


class FunctionalArea(BaseModel):
    area_id: str = Field(alias="areaId")
    area_name: str = Field(alias="areaName")
    description: str
    main_functionality: list[str] = Field(alias="mainFunctionality")
    qa_importance: str = Field(alias="qaImportance")
    risk_level: str = Field(alias="riskLevel")
    source_evidence: list[SourceEvidence] = Field(default_factory=list, alias="sourceEvidence")
    platforms: list[str] = Field(default_factory=list)
    recommended_categories: list[str] = Field(default_factory=list, alias="recommendedCategories")
    recommended_priorities: list[str] = Field(default_factory=list, alias="recommendedPriorities")
    suggested_test_focus: list[str] = Field(default_factory=list, alias="suggestedTestFocus")
    assumptions: list[str] = Field(default_factory=list)
    questions_for_ba: list[str] = Field(default_factory=list, alias="questionsForBA")
    included: bool = True
    user_notes: str = Field(default="", alias="userNotes")


class CoverageMapResponse(BaseModel):
    source_work_item_id: str = Field(alias="sourceWorkItemId")
    summary: str
    functional_areas: list[FunctionalArea] = Field(alias="functionalAreas")
    cross_functional_risks: list[str] = Field(default_factory=list, alias="crossFunctionalRisks")
    global_assumptions: list[str] = Field(default_factory=list, alias="globalAssumptions")
    global_questions_for_ba: list[str] = Field(default_factory=list, alias="globalQuestionsForBA")
    generation_source: str = Field(default="backend", alias="generationSource")


class ApprovedCoverageMap(BaseModel):
    summary: str = ""
    functional_areas: list[FunctionalArea] = Field(default_factory=list, alias="functionalAreas")
    cross_functional_risks: list[str] = Field(default_factory=list, alias="crossFunctionalRisks")
    global_assumptions: list[str] = Field(default_factory=list, alias="globalAssumptions")
    global_questions_for_ba: list[str] = Field(default_factory=list, alias="globalQuestionsForBA")


class GenerationRequest(BaseModel):
    azure: AzureSource
    story: StoryContext
    figma: FigmaContext = Field(default_factory=FigmaContext)
    generation_policy: GenerationPolicy = Field(default_factory=GenerationPolicy, alias="generationPolicy")
    approved_coverage_map: ApprovedCoverageMap | None = Field(default=None, alias="approvedCoverageMap")


class CoverageMapRefinementRequest(GenerationRequest):
    current_coverage_map: CoverageMapResponse = Field(alias="currentCoverageMap")
    coverage_map_notes: str = Field(default="", alias="coverageMapNotes")


class WorkItemRelation(BaseModel):
    rel: str
    url: str
    name: str = ""


class WorkItemAttachment(BaseModel):
    id: str
    name: str
    url: str
    text: str = ""
    extraction_status: str = Field(default="not-extracted", alias="extractionStatus")
    included: bool = True


class WorkItemResponse(BaseModel):
    id: int
    work_item_type: str = Field(alias="workItemType")
    state: str
    title: str
    description: str = ""
    acceptance_criteria: str = Field(default="", alias="acceptanceCriteria")
    area_path: str = Field(default="", alias="areaPath")
    iteration_path: str = Field(default="", alias="iterationPath")
    priority: int | None = None
    parent_id: int | None = Field(default=None, alias="parentId")
    relations: list[WorkItemRelation] = Field(default_factory=list)
    attachments: list[WorkItemAttachment] = Field(default_factory=list)


class TestStep(BaseModel):
    action: str
    expected_result: str = Field(alias="expectedResult")


class TestCase(BaseModel):
    title: str
    platform: str = "Web"
    priority: str
    category: str
    preconditions: list[str]
    steps: list[TestStep]
    coverage: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class GenerationResponse(BaseModel):
    source_work_item_id: str = Field(alias="sourceWorkItemId")
    summary: str
    assumptions: list[str]
    questions_for_ba: list[str] = Field(alias="questionsForBA")
    test_cases: list[TestCase] = Field(alias="testCases")
    generation_source: str = Field(default="backend-mock", alias="generationSource")


class RefinementNotes(BaseModel):
    clarified_business_rules: str = Field(default="", alias="clarifiedBusinessRules")
    coverage_gaps: str = Field(default="", alias="coverageGaps")
    tests_to_avoid_or_change: str = Field(default="", alias="testsToAvoidOrChange")
    additional_instruction: str = Field(default="", alias="additionalInstruction")


class RefinementRequest(GenerationRequest):
    current_test_cases: list[TestCase] = Field(default_factory=list, alias="currentTestCases")
    current_assumptions: list[str] = Field(default_factory=list, alias="currentAssumptions")
    current_questions_for_ba: list[str] = Field(default_factory=list, alias="currentQuestionsForBA")
    refinement_notes: RefinementNotes = Field(default_factory=RefinementNotes, alias="refinementNotes")


class ImportTarget(BaseModel):
    test_plan_id: str = Field(alias="testPlanId")
    test_suite_id: str = Field(alias="testSuiteId")
    suite_ids_by_platform: dict[str, str] = Field(default_factory=dict, alias="suiteIdsByPlatform")


class ImportRequest(BaseModel):
    source_work_item_id: str = Field(alias="sourceWorkItemId")
    target: ImportTarget
    test_cases: list[TestCase] = Field(alias="testCases")


class ImportedTestCase(BaseModel):
    id: int
    title: str
    platform: str = "Web"
    category: str
    priority: str
    status: str = "Ready for Azure DevOps import"


class ImportResponse(BaseModel):
    status: str
    message: str
    created_test_cases: list[ImportedTestCase] = Field(alias="createdTestCases")


class DryRunValidation(BaseModel):
    name: str
    status: str
    message: str


class DryRunPlannedTestCase(BaseModel):
    sequence: int
    title: str
    platform: str = "Web"
    category: str
    priority: str
    step_count: int = Field(alias="stepCount")
    would_create_work_item: bool = Field(default=True, alias="wouldCreateWorkItem")
    would_link_to_story: bool = Field(default=True, alias="wouldLinkToStory")
    would_add_to_suite: bool = Field(default=True, alias="wouldAddToSuite")


class ImportDryRunResponse(BaseModel):
    status: str
    message: str
    source_work_item_id: str = Field(alias="sourceWorkItemId")
    test_plan_id: str = Field(alias="testPlanId")
    test_suite_id: str = Field(alias="testSuiteId")
    test_plan_name: str = Field(default="", alias="testPlanName")
    test_suite_name: str = Field(default="", alias="testSuiteName")
    suite_names_by_platform: dict[str, str] = Field(default_factory=dict, alias="suiteNamesByPlatform")
    validations: list[DryRunValidation]
    planned_test_cases: list[DryRunPlannedTestCase] = Field(alias="plannedTestCases")
