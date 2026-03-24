from __future__ import annotations

from app.collectors.base import SourceAdapter
from app.collectors.utils import extract_keywords, parse_datetime
from app.models import CollectedRecord, PollSource


class KernelOrgReleasesAdapter(SourceAdapter):
    async def collect(self, source: PollSource) -> list[CollectedRecord]:
        if not source.url:
            return []

        response = await self.http_client.get(source.url, timeout=30.0)
        response.raise_for_status()
        payload = response.json()

        releases = payload.get("releases", [])
        if not isinstance(releases, list):
            return []

        records: list[CollectedRecord] = []
        for release in releases[: source.max_entries]:
            if not isinstance(release, dict):
                continue

            version = str(release.get("version", "unknown"))
            moniker = str(release.get("moniker", "release"))
            released = release.get("released", {})
            published_at = parse_datetime((released or {}).get("isodate"))
            title = f"Kernel {moniker} release {version}"
            summary_parts = [
                f"moniker={moniker}",
                f"version={version}",
                f"released={released.get('isodate') if isinstance(released, dict) else 'unknown'}",
            ]
            if release.get("changelog"):
                summary_parts.append(f"changelog={release['changelog']}")

            records.append(
                CollectedRecord(
                    source_id=source.id,
                    family=source.family,
                    kind=source.default_kind or "release",
                    external_id=f"{moniker}:{version}",
                    canonical_key=f"{source.id}:{moniker}:{version}",
                    title=title,
                    summary=" | ".join(summary_parts),
                    url=str(release.get("gitweb") or release.get("source") or source.url),
                    published_at=published_at,
                    raw_type="json",
                    raw_payload=release,
                    keywords=["release", moniker, *extract_keywords(title)],
                    branch=moniker,
                )
            )

        return records
