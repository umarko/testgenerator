import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app.models import WorkItemAttachment, WorkItemRelation, WorkItemResponse
from app.services.attachment_text import extract_attachment_text
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
        return json.loads(self._get_bytes(url).decode("utf-8"))

    def _get_bytes(self, url: str) -> bytes:
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
                return response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise HTTPException(status_code=exc.code, detail=detail) from exc
        except URLError as exc:
            raise HTTPException(status_code=502, detail=f"Azure DevOps is unavailable: {exc}") from exc

    def _normalize_work_item(self, payload: dict) -> WorkItemResponse:
        fields = payload.get("fields", {})
        description_html = fields.get("System.Description", "")
        relations = [
            WorkItemRelation(
                rel=relation.get("rel", ""),
                url=relation.get("url", ""),
                name=(relation.get("attributes") or {}).get("name", ""),
            )
            for relation in payload.get("relations", []) or []
        ]
        attachments = self._extract_attachments(payload.get("relations", []) or [], description_html)

        return WorkItemResponse(
            id=payload["id"],
            workItemType=fields.get("System.WorkItemType", ""),
            state=fields.get("System.State", ""),
            title=fields.get("System.Title", ""),
            description=html_to_text(description_html),
            acceptanceCriteria=html_to_text(fields.get("Microsoft.VSTS.Common.AcceptanceCriteria")),
            areaPath=fields.get("System.AreaPath", ""),
            iterationPath=fields.get("System.IterationPath", ""),
            priority=fields.get("Microsoft.VSTS.Common.Priority"),
            parentId=fields.get("System.Parent"),
            relations=relations,
            attachments=attachments,
        )

    def _extract_attachments(self, relations: list[dict], description_html: str) -> list[WorkItemAttachment]:
        candidates: list[tuple[str, str]] = []
        for relation in relations:
            rel = relation.get("rel", "")
            url = relation.get("url", "")
            name = (relation.get("attributes") or {}).get("name", "")
            if rel == "AttachedFile" and url:
                candidates.append((url, name or self._file_name_from_url(url)))

        for url in re.findall(r"https?://[^\"'<>\s]+/_apis/wit/attachments/[^\"'<>\s]+", description_html or ""):
            candidates.append((url, self._file_name_from_url(url)))

        attachments = []
        seen_urls = set()
        for url, name in candidates:
            if url in seen_urls:
                continue
            seen_urls.add(url)
            attachments.append(self._download_attachment(url, name))
        return attachments

    def _download_attachment(self, url: str, name: str) -> WorkItemAttachment:
        attachment_id = self._attachment_id_from_url(url)
        file_name = name or f"attachment-{attachment_id}"

        try:
            content = self._get_bytes(url)
            text, status = extract_attachment_text(file_name, content)
        except HTTPException:
            raise
        except Exception as exc:
            text = ""
            status = f"extraction-failed: {exc}"

        return WorkItemAttachment(
            id=attachment_id,
            name=file_name,
            url=url,
            text=text,
            extractionStatus=status,
            included=bool(text),
        )

    def _file_name_from_url(self, url: str) -> str:
        query = parse_qs(urlparse(url).query)
        file_name = query.get("fileName", [""])[0]
        return file_name or PathlessUrlName.from_url(url)

    def _attachment_id_from_url(self, url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        return path.rsplit("/", 1)[-1]

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


class PathlessUrlName:
    @staticmethod
    def from_url(url: str) -> str:
        path = urlparse(url).path.rstrip("/")
        return path.rsplit("/", 1)[-1] if path else "attachment"
