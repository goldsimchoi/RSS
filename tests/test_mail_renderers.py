from datetime import datetime, timezone

from app.db.models import Item
from app.mail.renderers import render_daily_digest_email, render_immediate_alert_email
from app.models import CollectedRecord


def test_render_immediate_alert_email_includes_html_and_plain_text() -> None:
    record = CollectedRecord(
        source_id="linux_cve_announce",
        family="linux",
        kind="cve",
        external_id="example-id",
        canonical_key="linux_cve_announce:example-id",
        title="CVE-2026-9999: netfilter: fix use-after-free",
        summary="A use-after-free in netfilter was fixed and backported.",
        url="https://lore.kernel.org/linux-cve-announce/example/",
        published_at=datetime(2026, 3, 24, 0, 0, tzinfo=timezone.utc),
        raw_type="atom",
        cve_ids=["CVE-2026-9999"],
        keywords=["use-after-free", "netfilter"],
    )

    message = render_immediate_alert_email(
        record=record,
        severity_bucket="confirmed_security",
        score=140,
        reasons=["official confirmed security source", "cve indicator", "keyword:use-after-free"],
    )

    assert "Immediate alert" in message.subject
    assert "RSS Watcher Immediate Alert" in message.body
    assert "CVE-2026-9999" in message.body
    assert message.html_body is not None
    assert "Open upstream source" in message.html_body
    assert "Why this matched" in message.html_body


def test_render_daily_digest_email_groups_sections() -> None:
    items = [
        Item(
            source_id="linux_cve_announce",
            family="linux",
            kind="cve",
            canonical_key="a",
            external_id="a",
            title="CVE-2026-0001",
            summary="Critical kernel fix",
            url="https://example.com/a",
            score=140,
            severity_bucket="confirmed_security",
            published_at=datetime(2026, 3, 24, 0, 0, tzinfo=timezone.utc),
        ),
        Item(
            source_id="android_common_kernel",
            family="android",
            kind="commit",
            canonical_key="b",
            external_id="b",
            title="ANDROID: fix overflow",
            summary="Overflow fix in a common-kernel path",
            url="https://example.com/b",
            score=25,
            severity_bucket="security_candidate_medium",
            published_at=datetime(2026, 3, 24, 1, 0, tzinfo=timezone.utc),
        ),
    ]

    message = render_daily_digest_email(
        items=items,
        since=datetime(2026, 3, 23, 0, 0, tzinfo=timezone.utc),
    )

    assert "Daily digest" in message.subject
    assert "RSS Watcher Daily Digest" in message.body
    assert "confirmed_security: 1" in message.body
    assert "security_candidate_medium: 1" in message.body
    assert message.html_body is not None
    assert "Kernel and Android update digest" in message.html_body
    assert "Confirmed Security" in message.html_body
    assert "Security Candidate Medium" in message.html_body
