from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class PollSource(BaseModel):
    id: str
    enabled: bool = True
    adapter: str
    family: str
    poll_every: str
    max_entries: int = 20
    notify_policy: str = "digest"
    default_kind: str | None = None
    url: str | None = None
    list_url: str | None = None
    repo_url: str | None = None
    branches: list[str] = Field(default_factory=list)


class KeywordRuleConfig(BaseModel):
    sources: list[str] = Field(default_factory=list)
    subject_or_body_any: list[str] = Field(default_factory=list)


class DeliveryConfig(BaseModel):
    immediate_score_min: int = 100
    digest_score_min: int = 1
    digest_cron: str = "0 9 * * *"
    smtp_profile: str = "default"


class SourcesConfig(BaseModel):
    timezone: str = "Asia/Seoul"
    sources: list[PollSource] = Field(default_factory=list)
    keyword_rules: dict[str, KeywordRuleConfig] = Field(default_factory=dict)
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)


class CollectedRecord(BaseModel):
    source_id: str
    family: str
    kind: str
    external_id: str
    canonical_key: str
    title: str
    summary: str = ""
    url: str
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    raw_type: str
    raw_payload: dict[str, Any] = Field(default_factory=dict)
    keywords: list[str] = Field(default_factory=list)
    cve_ids: list[str] = Field(default_factory=list)
    subsystem: str | None = None
    branch: str | None = None
