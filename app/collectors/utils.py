from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape


ABSOLUTE_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
CVE_PATTERN = re.compile(r"\bCVE-\d{4}-\d+\b", re.IGNORECASE)


def make_absolute_url(base: str, maybe_relative: str) -> str:
    if ABSOLUTE_URL_PATTERN.match(maybe_relative):
        return maybe_relative
    if base.endswith("/") and maybe_relative.startswith("/"):
        return base[:-1] + maybe_relative
    if base.endswith("/") or maybe_relative.startswith("/"):
        return base + maybe_relative
    return f"{base}/{maybe_relative}"


def normalize_text(value: str) -> str:
    return " ".join(unescape(value).split())


def extract_cve_ids(text: str) -> list[str]:
    found = {match.upper() for match in CVE_PATTERN.findall(text)}
    return sorted(found)


def extract_keywords(text: str) -> list[str]:
    haystack = text.lower()
    keywords: list[str] = []
    for keyword in [
        "use-after-free",
        "out-of-bounds",
        "overflow",
        "type confusion",
        "privilege escalation",
        "arbitrary write",
        "refcount",
        "exploit",
        "fixes:",
        "cc: stable",
        "binder",
        "netfilter",
        "io_uring",
        "credentials",
        "mm/",
        "fs/",
        "critical",
        "high",
    ]:
        if keyword in haystack:
            keywords.append(keyword)
    return keywords


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(timezone.utc)

    try:
        if value.endswith("Z"):
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        pass

    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
