from pydantic import BaseModel, Field


class CoverageOptions(BaseModel):
    positive: bool = True
    negative: bool = True
    boundary: bool = True
    security: bool = True
    audit: bool = True


class AzureSource(BaseModel):
    organization: str = ""
    project: str = ""
    story_id: str = Field(default="", alias="storyId")
    test_plan_id: str = Field(default="", alias="testPlanId")
    test_suite_id: str = Field(default="", alias="testSuiteId")


class StoryContext(BaseModel):
    title: str = ""
    acceptance_criteria: str = Field(default="", alias="acceptanceCriteria")


class FigmaContext(BaseModel):
    enabled: bool = False
    links: list[str] = Field(default_factory=list)
    screens: list[dict] = Field(default_factory=list)


class GenerationPolicy(BaseModel):
    domain: str = "fintech"
    test_style: str = Field(default="manual", alias="testStyle")
    max_test_cases: int = Field(default=15, alias="maxTestCases", ge=1, le=30)
    coverage: CoverageOptions = Field(default_factory=CoverageOptions)


class GenerationRequest(BaseModel):
    azure: AzureSource
    story: StoryContext
    figma: FigmaContext = Field(default_factory=FigmaContext)
    generation_policy: GenerationPolicy = Field(default_factory=GenerationPolicy, alias="generationPolicy")


class WorkItemRelation(BaseModel):
    rel: str
    url: str
    name: str = ""


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


class TestStep(BaseModel):
    action: str
    expected_result: str = Field(alias="expectedResult")


class TestCase(BaseModel):
    title: str
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


class ImportTarget(BaseModel):
    test_plan_id: str = Field(alias="testPlanId")
    test_suite_id: str = Field(alias="testSuiteId")


class ImportRequest(BaseModel):
    source_work_item_id: str = Field(alias="sourceWorkItemId")
    target: ImportTarget
    test_cases: list[TestCase] = Field(alias="testCases")


class ImportedTestCase(BaseModel):
    id: int
    title: str
    category: str
    priority: str
    status: str = "Ready for Azure DevOps import"


class ImportResponse(BaseModel):
    status: str
    message: str
    created_test_cases: list[ImportedTestCase] = Field(alias="createdTestCases")
