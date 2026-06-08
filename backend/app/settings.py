from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_ROOT / ".env")


class Settings(BaseSettings):
    app_env: str = Field(default="local", alias="APP_ENV")
    azure_devops_base_url: str = Field(default="", alias="AZURE_DEVOPS_BASE_URL")
    azure_devops_collection: str = Field(default="", alias="AZURE_DEVOPS_COLLECTION")
    azure_devops_project: str = Field(default="", alias="AZURE_DEVOPS_PROJECT")
    azure_devops_api_version: str = Field(default="5.0", alias="AZURE_DEVOPS_API_VERSION")
    azure_devops_pat: str = Field(default="", alias="AZURE_DEVOPS_PAT")
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1", alias="OPENAI_MODEL")

    model_config = SettingsConfigDict(extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
