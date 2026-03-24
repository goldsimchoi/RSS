from typing import Annotated
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    debug: bool = False
    timezone: str = "Asia/Seoul"
    database_url: str = "sqlite:///./rss_watcher.db"
    sources_config_path: Path = Path("config/sources.yaml")
    sources_example_path: Path = Path("config/sources.example.yaml")
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from: str = "noreply@example.com"
    smtp_to: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["alerts@example.com"])
    poll_on_startup: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RSS_",
        extra="ignore",
    )

    @field_validator("smtp_to", mode="before")
    @classmethod
    def split_smtp_to(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, list):
            return value
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def effective_sources_config_path(self) -> Path:
        if self.sources_config_path.exists():
            return self.sources_config_path
        return self.sources_example_path


settings = Settings()
