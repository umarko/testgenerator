import hashlib
import json
from pathlib import Path

from app.models import GenerationRequest, GenerationResponse
from app.settings import BACKEND_ROOT


CACHE_DIR = BACKEND_ROOT / "local_data" / "generation_cache"


def load_cached_generation(request: GenerationRequest) -> GenerationResponse | None:
    path = _cache_path(request)
    if not path.exists():
        return None

    return GenerationResponse.model_validate_json(path.read_text(encoding="utf-8"))


def save_cached_generation(request: GenerationRequest, response: GenerationResponse) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(request)
    path.write_text(response.model_dump_json(by_alias=True, indent=2), encoding="utf-8")


def _cache_path(request: GenerationRequest) -> Path:
    story_id = "".join(char for char in request.azure.story_id if char.isalnum()) or "draft"
    return CACHE_DIR / f"{story_id}-{_cache_key(request)}.json"


def _cache_key(request: GenerationRequest) -> str:
    included_attachments = [
        {
            "id": attachment.id,
            "name": attachment.name,
            "textHash": hashlib.sha256(attachment.text.encode("utf-8")).hexdigest(),
        }
        for attachment in request.story.attachments
        if attachment.included and attachment.text.strip()
    ]
    payload = {
        "storyId": request.azure.story_id,
        "title": request.story.title,
        "acceptanceCriteria": request.story.acceptance_criteria,
        "additionalContext": request.story.additional_context,
        "attachments": included_attachments,
        "coverage": request.generation_policy.coverage.model_dump(),
        "priorities": request.generation_policy.priorities.model_dump(),
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
