class AzureDevOpsConnector:
    """Placeholder for the real Azure DevOps integration."""

    def get_work_item(self, story_id: str) -> dict:
        raise NotImplementedError("Azure DevOps connector is not implemented in the mock backend.")

    def create_test_case(self, payload: dict) -> dict:
        raise NotImplementedError("Azure DevOps import is not implemented in the mock backend.")

