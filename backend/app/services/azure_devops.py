import base64
import json
import re
from html import escape
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException

from app.models import TestCase, WorkItemAttachment, WorkItemRelation, WorkItemResponse
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

    def create_manual_test_case(self, test_case: TestCase, source_work_item_id: str) -> dict:
        self._validate_settings()
        patch = self._test_case_patch(test_case, source_work_item_id)
        return self._post_json_patch(self._create_work_item_url("Test Case"), patch)

    def validate_manual_test_case(self, test_case: TestCase, source_work_item_id: str) -> dict:
        self._validate_settings()
        patch = self._test_case_patch(test_case, source_work_item_id)
        return self._post_json_patch(self._create_work_item_url("Test Case", validate_only=True), patch)

    def add_test_case_to_suite(self, plan_id: str, suite_id: str, test_case_id: int) -> dict:
        self._validate_settings()
        return self._post_json(
            self._suite_test_case_url(plan_id, suite_id, str(test_case_id)),
            {},
        )

    def get_test_suite(self, plan_id: str, suite_id: str) -> dict:
        self._validate_settings()
        return self._get_json(self._test_suite_url(plan_id, suite_id))

    def get_test_suites_for_plan(self, plan_id: str) -> dict:
        self._validate_settings()
        return self._get_json(self._test_suites_url(plan_id))

    def _work_item_url(self, work_item_id: str) -> str:
        base_url = self.settings.azure_devops_base_url.rstrip("/")
        collection = quote(self.settings.azure_devops_collection.strip("/"))
        project = quote(self.settings.azure_devops_project.strip("/"))
        api_version = quote(self.settings.azure_devops_api_version)
        return (
            f"{base_url}/{collection}/{project}/_apis/wit/workitems/{quote(work_item_id)}"
            f"?$expand=all&api-version={api_version}"
        )

    def _test_suites_url(self, plan_id: str) -> str:
        base_url = self.settings.azure_devops_base_url.rstrip("/")
        collection = quote(self.settings.azure_devops_collection.strip("/"))
        project = quote(self.settings.azure_devops_project.strip("/"))
        api_version = quote(self.settings.azure_devops_api_version)
        return (
            f"{base_url}/{collection}/{project}/_apis/test/Plans/{quote(plan_id)}/suites"
            f"?api-version={api_version}"
        )

    def _test_suite_url(self, plan_id: str, suite_id: str) -> str:
        base_url = self.settings.azure_devops_base_url.rstrip("/")
        collection = quote(self.settings.azure_devops_collection.strip("/"))
        project = quote(self.settings.azure_devops_project.strip("/"))
        api_version = quote(self.settings.azure_devops_api_version)
        return (
            f"{base_url}/{collection}/{project}/_apis/test/Plans/{quote(plan_id)}/suites/{quote(suite_id)}"
            f"?api-version={api_version}"
        )

    def _suite_test_case_url(self, plan_id: str, suite_id: str, test_case_ids: str) -> str:
        base_url = self.settings.azure_devops_base_url.rstrip("/")
        collection = quote(self.settings.azure_devops_collection.strip("/"))
        project = quote(self.settings.azure_devops_project.strip("/"))
        api_version = quote(self.settings.azure_devops_api_version)
        return (
            f"{base_url}/{collection}/{project}/_apis/test/Plans/{quote(plan_id)}"
            f"/suites/{quote(suite_id)}/testcases/{quote(test_case_ids)}"
            f"?api-version={api_version}"
        )

    def _create_work_item_url(self, work_item_type: str, validate_only: bool = False) -> str:
        base_url = self.settings.azure_devops_base_url.rstrip("/")
        collection = quote(self.settings.azure_devops_collection.strip("/"))
        project = quote(self.settings.azure_devops_project.strip("/"))
        api_version = quote(self.settings.azure_devops_api_version)
        validate_query = "&validateOnly=true" if validate_only else ""
        return (
            f"{base_url}/{collection}/{project}/_apis/wit/workitems/${quote(work_item_type)}"
            f"?api-version={api_version}{validate_query}"
        )

    def _get_json(self, url: str) -> dict:
        return json.loads(self._get_bytes(url).decode("utf-8"))

    def _get_bytes(self, url: str) -> bytes:
        request = Request(
            url,
            headers={
                **self._auth_headers(),
                "Accept": "application/json",
            },
            method="GET",
        )
        return self._send_request(request)

    def _post_json(self, url: str, payload: dict) -> dict:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                **self._auth_headers(),
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        content = self._send_request(request)
        return json.loads(content.decode("utf-8")) if content else {}

    def _post_json_patch(self, url: str, payload: list[dict]) -> dict:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                **self._auth_headers(),
                "Accept": "application/json",
                "Content-Type": "application/json-patch+json",
            },
            method="POST",
        )
        return json.loads(self._send_request(request).decode("utf-8"))

    def _send_request(self, request: Request) -> bytes:
        try:
            with urlopen(request, timeout=20) as response:
                return response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            if not detail.strip():
                detail = f"{exc.reason or 'No response body'} ({request.get_method()} {request.full_url})"
            raise HTTPException(status_code=exc.code, detail=detail) from exc
        except URLError as exc:
            raise HTTPException(status_code=502, detail=f"Azure DevOps is unavailable: {exc}") from exc

    def _auth_headers(self) -> dict[str, str]:
        token = ":" + self.settings.azure_devops_pat
        encoded_token = base64.b64encode(token.encode("ascii")).decode("ascii")
        return {"Authorization": f"Basic {encoded_token}"}

    def _test_case_patch(self, test_case: TestCase, source_work_item_id: str) -> list[dict]:
        tags = set(test_case.tags)
        tags.add("AI Generated")
        tags.add(test_case.category)
        tags.add(test_case.priority)
        patch = [
            {"op": "add", "path": "/fields/System.Title", "value": test_case.title},
            {
                "op": "add",
                "path": "/fields/System.Description",
                "value": self._description_html(test_case),
            },
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.Common.Priority",
                "value": self._priority_number(test_case.priority),
            },
            {
                "op": "add",
                "path": "/fields/System.Tags",
                "value": "; ".join(sorted(tag for tag in tags if tag)),
            },
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.TCM.Steps",
                "value": self._steps_xml(test_case),
            },
        ]

        if source_work_item_id:
            patch.append(
                {
                    "op": "add",
                    "path": "/relations/-",
                    "value": {
                        "rel": "Microsoft.VSTS.Common.TestedBy-Reverse",
                        "url": self._work_item_relation_url(source_work_item_id),
                        "attributes": {"comment": "Generated by QA Test Case Generator"},
                    },
                }
            )
        return patch

    def _description_html(self, test_case: TestCase) -> str:
        preconditions = "".join(f"<li>{escape(item)}</li>" for item in test_case.preconditions)
        coverage = ", ".join(test_case.coverage or [test_case.category])
        return (
            f"<p><strong>Category:</strong> {escape(test_case.category)}</p>"
            f"<p><strong>Priority:</strong> {escape(test_case.priority)}</p>"
            f"<p><strong>Coverage:</strong> {escape(coverage)}</p>"
            f"<p><strong>Preconditions:</strong></p><ul>{preconditions}</ul>"
        )

    def _steps_xml(self, test_case: TestCase) -> str:
        steps = []
        for index, step in enumerate(test_case.steps, start=1):
            steps.append(
                f'<step id="{index}" type="ActionStep">'
                f'<parameterizedString isformatted="true">{escape(step.action)}</parameterizedString>'
                f'<parameterizedString isformatted="true">{escape(step.expected_result)}</parameterizedString>'
                "<description/>"
                "</step>"
            )
        return f'<steps id="0" last="{len(test_case.steps)}">{"".join(steps)}</steps>'

    def _priority_number(self, priority: str) -> int:
        if priority.upper().startswith("P") and priority[1:].isdigit():
            return max(1, min(int(priority[1:]), 5))
        return 3

    def _work_item_relation_url(self, work_item_id: str) -> str:
        base_url = self.settings.azure_devops_base_url.rstrip("/")
        collection = quote(self.settings.azure_devops_collection.strip("/"))
        project = quote(self.settings.azure_devops_project.strip("/"))
        return f"{base_url}/{collection}/{project}/_apis/wit/workItems/{quote(work_item_id)}"

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
