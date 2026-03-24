from __future__ import annotations

import xml.etree.ElementTree as ET

from app.collectors.base import SourceAdapter
from app.collectors.utils import extract_cve_ids, extract_keywords, make_absolute_url, normalize_text, parse_datetime
from app.models import CollectedRecord, PollSource

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


class LoreListAdapter(SourceAdapter):
    async def collect(self, source: PollSource) -> list[CollectedRecord]:
        if not source.list_url:
            return []

        atom_url = make_absolute_url(source.list_url.rstrip("/"), "new.atom")
        response = await self.http_client.get(atom_url, timeout=30.0)
        response.raise_for_status()
        root = ET.fromstring(response.text)

        records: list[CollectedRecord] = []
        for entry in root.findall("atom:entry", ATOM_NS)[: source.max_entries]:
            title = normalize_text(entry.findtext("atom:title", default="", namespaces=ATOM_NS))
            link = entry.find("atom:link", ATOM_NS)
            url = link.attrib.get("href", source.list_url) if link is not None else source.list_url
            updated = parse_datetime(entry.findtext("atom:updated", default=None, namespaces=ATOM_NS))
            entry_id = normalize_text(entry.findtext("atom:id", default=url, namespaces=ATOM_NS))
            content_text = " ".join(
                normalize_text(text)
                for text in entry.itertext()
                if text and normalize_text(text)
            )
            summary = content_text[:2000]
            cve_ids = extract_cve_ids(f"{title}\n{summary}")
            keywords = extract_keywords(f"{title}\n{summary}")

            records.append(
                CollectedRecord(
                    source_id=source.id,
                    family=source.family,
                    kind=source.default_kind or "patch",
                    external_id=entry_id,
                    canonical_key=url.rstrip("/"),
                    title=title,
                    summary=summary,
                    url=url,
                    published_at=updated,
                    raw_type="atom",
                    raw_payload={
                        "id": entry_id,
                        "title": title,
                        "url": url,
                        "content": summary,
                    },
                    keywords=keywords,
                    cve_ids=cve_ids,
                )
            )

        return records
