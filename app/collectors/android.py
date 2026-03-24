from __future__ import annotations

import json
import re

from bs4 import BeautifulSoup

from app.collectors.base import SourceAdapter
from app.collectors.utils import extract_cve_ids, extract_keywords, make_absolute_url, normalize_text, parse_datetime
from app.models import CollectedRecord, PollSource

BULLETIN_PATH_PATTERN = re.compile(r"^/docs/security/bulletin/\d{4}/\d{4}-\d{2}-\d{2}(?:\.html)?$")


class AndroidBulletinIndexAdapter(SourceAdapter):
    async def collect(self, source: PollSource) -> list[CollectedRecord]:
        if not source.url:
            return []

        overview_html = await self._fetch_text(source.url)
        overview_soup = BeautifulSoup(overview_html, "html.parser")

        bulletin_links: list[str] = []
        seen_links: set[str] = set()
        for anchor in overview_soup.find_all("a", href=True):
            href = anchor["href"]
            href = href.split("?")[0]
            if not BULLETIN_PATH_PATTERN.match(href):
                continue

            absolute_url = make_absolute_url("https://source.android.com", href)
            if absolute_url in seen_links:
                continue
            seen_links.add(absolute_url)
            bulletin_links.append(absolute_url)
            if len(bulletin_links) >= source.max_entries:
                break

        records: list[CollectedRecord] = []
        for bulletin_url in bulletin_links:
            bulletin_html = await self._fetch_text(bulletin_url)
            bulletin_soup = BeautifulSoup(bulletin_html, "html.parser")
            records.append(self._build_bulletin_record(source, bulletin_url, bulletin_soup))

        return records

    async def _fetch_text(self, url: str) -> str:
        response = await self.http_client.get(
            url,
            timeout=30.0,
            headers={"User-Agent": "rss-watcher/0.1"},
        )
        response.raise_for_status()
        return response.text

    def _build_bulletin_record(self, source: PollSource, bulletin_url: str, soup: BeautifulSoup) -> CollectedRecord:
        title = self._extract_bulletin_title(soup, bulletin_url)

        page_text = normalize_text(soup.get_text(" ", strip=True))
        cve_ids = extract_cve_ids(page_text)
        summary = self._summarize_bulletin(soup, cve_ids)
        published_at = parse_datetime(self._extract_bulletin_date(bulletin_url))
        keywords = extract_keywords(f"{title}\n{summary}")

        return CollectedRecord(
            source_id=source.id,
            family=source.family,
            kind=source.default_kind or "bulletin",
            external_id=bulletin_url,
            canonical_key=bulletin_url,
            title=title,
            summary=summary,
            url=bulletin_url,
            published_at=published_at,
            raw_type="html",
            raw_payload={
                "bulletin_url": bulletin_url,
                "cve_count": len(cve_ids),
                "sample_cves": cve_ids[:20],
            },
            keywords=keywords,
            cve_ids=cve_ids,
        )

    def _summarize_bulletin(self, soup: BeautifulSoup, cve_ids: list[str]) -> str:
        severity_counts = {"Critical": 0, "High": 0, "Moderate": 0, "Low": 0}
        table_rows = 0

        for row in soup.find_all("tr"):
            cells = [normalize_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["th", "td"])]
            if not cells:
                continue
            table_rows += 1
            for severity in severity_counts:
                if severity in cells:
                    severity_counts[severity] += 1

        interesting_lines = [
            f"cve_count={len(cve_ids)}",
            f"table_rows={table_rows}",
            "severity_counts="
            + ", ".join(f"{severity}:{count}" for severity, count in severity_counts.items() if count),
        ]

        note = soup.find("aside", class_="note")
        if note:
            interesting_lines.append(f"note={normalize_text(note.get_text(' ', strip=True))[:300]}")

        if cve_ids:
            interesting_lines.append(f"sample_cves={', '.join(cve_ids[:10])}")

        return " | ".join(line for line in interesting_lines if line and not line.endswith("="))

    def _extract_bulletin_date(self, bulletin_url: str) -> str:
        match = re.search(r"(\d{4}-\d{2}-\d{2})", bulletin_url)
        return match.group(1) if match else ""

    def _extract_bulletin_title(self, soup: BeautifulSoup, bulletin_url: str) -> str:
        title_candidates = [
            soup.find("meta", attrs={"property": "og:title"}),
            soup.find("title"),
            soup.find("h1"),
        ]
        for candidate in title_candidates:
            if candidate is None:
                continue
            raw = candidate.get("content") if candidate.has_attr("content") else candidate.get_text(" ", strip=True)
            title = normalize_text(raw).split("|", 1)[0].strip()
            title = re.sub(r"(Bulletin)([A-Z][a-z]+ \d{4})", r"\1 \2", title)
            if title:
                return title
        return bulletin_url.rsplit("/", 1)[-1]


class GitilesLogAdapter(SourceAdapter):
    async def collect(self, source: PollSource) -> list[CollectedRecord]:
        if not source.repo_url or not source.branches:
            return []

        records: list[CollectedRecord] = []
        per_branch_limit = max(1, source.max_entries // len(source.branches))

        for branch in source.branches:
            url = f"{source.repo_url}/+log/refs/heads/{branch}?format=JSON"
            response = await self.http_client.get(
                url,
                timeout=30.0,
                headers={"User-Agent": "rss-watcher/0.1"},
            )
            response.raise_for_status()
            payload = _load_gitiles_json(response.text)
            for entry in payload.get("log", [])[:per_branch_limit]:
                if not isinstance(entry, dict):
                    continue

                commit_id = str(entry.get("commit"))
                message = str(entry.get("message", "")).strip()
                title = normalize_text(message.splitlines()[0] if message else commit_id)
                published_at = parse_datetime(entry.get("author", {}).get("time"))
                url = f"{source.repo_url}/+/{commit_id}"
                cve_ids = extract_cve_ids(message)
                keywords = extract_keywords(message)

                records.append(
                    CollectedRecord(
                        source_id=source.id,
                        family=source.family,
                        kind=source.default_kind or "commit",
                        external_id=commit_id,
                        canonical_key=f"{source.id}:{branch}:{commit_id}",
                        title=title,
                        summary=normalize_text(message)[:2000],
                        url=url,
                        published_at=published_at,
                        raw_type="json",
                        raw_payload=entry,
                        keywords=keywords,
                        cve_ids=cve_ids,
                        branch=branch,
                    )
                )

        return records


def _load_gitiles_json(text: str) -> dict:
    cleaned = text.lstrip()
    if cleaned.startswith(")]}'"):
        cleaned = cleaned.split("\n", 1)[1]
    return json.loads(cleaned)
