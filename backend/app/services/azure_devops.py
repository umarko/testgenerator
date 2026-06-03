import base64
import json
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app.models import WorkItemRelation, WorkItemResponse
from app.services.html_text import html_to_text
from app.settings import Settings, get_settings


class AzureDevOpsConnector:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_work_item(self, work_item_id: str) -> WorkItemResponse:
        self._validate_settings()
        url = self._work_item_url(work_item_id)
        payload = self._get_json(url)
        return self._normalize_work_item(payload)

    def create_test_case(self, payload: dict) -> dict:
        raise NotImplementedError("Azure DevOps import is not implemented yet.")

    def _work_item_url(self, work_item_id: str) -> str:
        base_url = self.settings.azure_devops_base_url.rstrip("/")
        collection = quote(self.settings.azure_devops_collection.strip("/"))
        project = quote(self.settings.azure_devops_project.strip("/"))
        api_version = quote(self.settings.azure_devops_api_version)
        return (
            f"{base_url}/{collection}/{project}/_apis/wit/workitems/{quote(work_item_id)}"
            f"?$expand=all&api-version={api_version}"
        )

    def _get_json(self, url: str) -> dict:
        token = ":" + self.settings.azure_devops_pat
        encoded_token = base64.b64encode(token.encode("ascii")).decode("ascii")
        request = Request(
            url,
            headers={
                "Authorization": f"Basic {encoded_token}",
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(status_code=exc.code, detail=detail) from exc
        except URLError as exc:
            raise HTTPException(status_code=502, detail=f"Azure DevOps is unavailable: {exc}") from exc

    def _normalize_work_item(self, payload: dict) -> WorkItemResponse:
        fields = payload.get("fields", {})
        relations = [
            WorkItemRelation(
                rel=relation.get("rel", ""),
                url=relation.get("url", ""),
                name=(relation.get("attributes") or {}).get("name", ""),
            )
            for relation in payload.get("relations", []) or []
        ]

        return WorkItemResponse(
            id=payload["id"],
            workItemType=fields.get("System.WorkItemType", ""),
            state=fields.get("System.State", ""),
            title=fields.get("System.Title", ""),
            description=html_to_text(fields.get("System.Description")),
            acceptanceCriteria=html_to_text(fields.get("Microsoft.VSTS.Common.AcceptanceCriteria")),
            areaPath=fields.get("System.AreaPath", ""),
            iterationPath=fields.get("System.IterationPath", ""),
            priority=fields.get("Microsoft.VSTS.Common.Priority"),
            parentId=fields.get("System.Parent"),
            relations=relations,
        )

    def _validate_settings(self) -> None:
        missing = []
        if not self.settings.azure_devops_base_url:
            missing.append("AZURE_DEVOPS_BASE_URL")
        if not self.settings.azure_devops_collection:
            missing.append("AZURE_DEVOPS_COLLECTION")
        if not self.settings.azure_devops_project:
            missing.append("AZURE_DEVOPS_PROJECT")
        if not self.settings.azure_devops_pat:
            missing.append("AZURE_DEVOPS_PAT")

        if missing:
            raise HTTPException(
                status_code=500,
                detail=f"Missing Azure DevOps settings: {', '.join(missing)}",
            )


def get_azure_devops_connector() -> AzureDevOpsConnector:
    return AzureDevOpsConnector()

