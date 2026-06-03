# QA Test Case Generator

AI-assisted tool for generating manual QA test cases from Azure DevOps user stories.

Target repository:

```text
https://github.com/umarko/testgenerator.git
```

## Current status

The project is in MVP discovery/design phase.

Available documents:

- `MVP_Blueprint_QA_Test_Case_Generator.md` - practical MVP blueprint covering scope, Azure DevOps integration, AI input/output structure, review workflow, risks, and implementation phases.

## MVP goal

The first version should let a QA user:

1. Enter an Azure DevOps User Story ID.
2. Fetch story details and acceptance criteria.
3. Generate structured manual test case proposals with AI.
4. Review and edit generated tests.
5. Import approved tests into Azure DevOps Test Plans.

The MVP should keep human review mandatory before Azure DevOps import.

