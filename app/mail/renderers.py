from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from html import escape

from app.db.models import Item
from app.mail.base import MailMessage
from app.models import CollectedRecord

SEVERITY_ORDER = [
    "confirmed_security",
    "security_candidate_high",
    "security_candidate_medium",
    "general_patch",
    "release_only",
]

SEVERITY_COLORS = {
    "confirmed_security": ("#7f1d1d", "#fee2e2", "#991b1b"),
    "security_candidate_high": ("#78350f", "#fef3c7", "#b45309"),
    "security_candidate_medium": ("#1e3a8a", "#dbeafe", "#1d4ed8"),
    "general_patch": ("#14532d", "#dcfce7", "#15803d"),
    "release_only": ("#374151", "#e5e7eb", "#4b5563"),
}

SOURCE_LABELS = {
    "kernel_releases": "Kernel.org Releases",
    "linux_cve_announce": "Linux CVE Announce",
    "linux_stable": "Linux Stable",
    "linux_lkml": "LKML",
    "android_bulletin_overview": "Android Security Bulletins",
    "android_common_kernel": "Android Common Kernel",
}


def render_immediate_alert_email(
    record: CollectedRecord,
    severity_bucket: str,
    score: int,
    reasons: list[str],
) -> MailMessage:
    subject = f"[RSS Watcher] Immediate alert: {record.title}"
    cve_text = ", ".join(record.cve_ids) if record.cve_ids else "n/a"
    reasons_text = ", ".join(reasons) if reasons else "n/a"
    published_text = _format_datetime(record.published_at)
    source_label = SOURCE_LABELS.get(record.source_id, record.source_id)

    body_lines = [
        "RSS Watcher Immediate Alert",
        "",
        f"Title: {record.title}",
        f"Severity: {severity_bucket}",
        f"Score: {score}",
        f"Source: {source_label}",
        f"Kind: {record.kind}",
        f"Published: {published_text}",
        f"CVE IDs: {cve_text}",
        f"Reasons: {reasons_text}",
        "",
        "Summary:",
        record.summary or "n/a",
        "",
        f"Open source: {record.url}",
    ]

    html_body = _render_layout(
        eyebrow="Immediate Alert",
        title=record.title,
        subtitle="A high-confidence item matched your kernel or Android watch rules.",
        summary_stats=[
            ("Severity", severity_bucket),
            ("Score", str(score)),
            ("Source", source_label),
            ("Published", published_text),
        ],
        sections=[
            _render_card(
                title="Why this matched",
                body=f"<p>{escape(reasons_text)}</p>",
                accent=severity_bucket,
            ),
            _render_card(
                title="Details",
                body=(
                    f"<p><strong>Kind:</strong> {escape(record.kind)}</p>"
                    f"<p><strong>CVE IDs:</strong> {escape(cve_text)}</p>"
                    f"<p><strong>Summary:</strong><br>{escape(record.summary or 'n/a')}</p>"
                    f"<p><a class=\"button\" href=\"{escape(record.url)}\">Open upstream source</a></p>"
                ),
                accent=severity_bucket,
            ),
        ],
    )

    return MailMessage(subject=subject, body="\n".join(body_lines), html_body=html_body)


def render_daily_digest_email(items: list[Item], since: datetime) -> MailMessage:
    counts = Counter(item.severity_bucket for item in items)
    subject = f"[RSS Watcher] Daily digest ({len(items)} items)"
    window_text = f"{_format_datetime(since)} to {_format_datetime(datetime.now(timezone.utc))}"

    body_lines = [
        "RSS Watcher Daily Digest",
        "",
        f"Window: {window_text}",
        f"Total items: {len(items)}",
        "",
        "Summary:",
    ]
    for severity in SEVERITY_ORDER:
        count = counts.get(severity, 0)
        if count:
            body_lines.append(f"- {severity}: {count}")

    sections_html: list[str] = []
    for severity in SEVERITY_ORDER:
        group = [item for item in items if item.severity_bucket == severity]
        if not group:
            continue

        body_lines.extend(["", severity, "-" * len(severity)])
        for item in group[:20]:
            source_label = SOURCE_LABELS.get(item.source_id, item.source_id)
            body_lines.append(f"* {item.title}")
            body_lines.append(f"  score={item.score} source={source_label} url={item.url}")

        card_items = []
        for item in group[:20]:
            source_label = SOURCE_LABELS.get(item.source_id, item.source_id)
            meta_bits = [
                f"<span class=\"pill\">{escape(source_label)}</span>",
                f"<span class=\"pill\">score {item.score}</span>",
            ]
            if item.kind:
                meta_bits.append(f"<span class=\"pill\">{escape(item.kind)}</span>")
            card_items.append(
                _render_card(
                    title=item.title,
                    body=(
                        f"<div class=\"meta-row\">{''.join(meta_bits)}</div>"
                        f"<p>{escape(_trim(item.summary or 'No summary', 240))}</p>"
                        f"<p><a class=\"button button-secondary\" href=\"{escape(item.url)}\">Open upstream source</a></p>"
                    ),
                    accent=severity,
                )
            )

        sections_html.append(
            f"""
            <section class="section">
              <div class="section-header">
                <h2>{escape(severity.replace('_', ' ').title())}</h2>
                <span class="count">{len(group)} items</span>
              </div>
              {''.join(card_items)}
            </section>
            """
        )

    html_body = _render_layout(
        eyebrow="Daily Digest",
        title="Kernel and Android update digest",
        subtitle="A grouped summary of the last 24 hours of tracked activity.",
        summary_stats=[
            ("Window", window_text),
            ("Total", str(len(items))),
            *[(severity.replace("_", " ").title(), str(counts[severity])) for severity in SEVERITY_ORDER if counts.get(severity)],
        ],
        sections=sections_html,
    )

    return MailMessage(subject=subject, body="\n".join(body_lines), html_body=html_body)


def _render_layout(
    *,
    eyebrow: str,
    title: str,
    subtitle: str,
    summary_stats: list[tuple[str, str]],
    sections: list[str],
) -> str:
    stats_html = "".join(
        f"""
        <div class="stat">
          <div class="stat-label">{escape(label)}</div>
          <div class="stat-value">{escape(value)}</div>
        </div>
        """
        for label, value in summary_stats
    )

    return f"""\
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
      body {{
        margin: 0;
        padding: 0;
        background: #f3f6fb;
        color: #0f172a;
        font-family: "Segoe UI", Arial, sans-serif;
      }}
      .wrapper {{
        width: 100%;
        padding: 24px 0;
      }}
      .container {{
        max-width: 760px;
        margin: 0 auto;
        background: #ffffff;
        border: 1px solid #dbe2ea;
        border-radius: 18px;
        overflow: hidden;
      }}
      .hero {{
        padding: 32px 32px 20px;
        background: linear-gradient(135deg, #0f172a 0%, #1d4ed8 100%);
        color: #ffffff;
      }}
      .eyebrow {{
        display: inline-block;
        font-size: 12px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        opacity: 0.8;
        margin-bottom: 12px;
      }}
      .hero h1 {{
        margin: 0 0 10px;
        font-size: 28px;
        line-height: 1.25;
      }}
      .hero p {{
        margin: 0;
        font-size: 15px;
        line-height: 1.6;
        color: #dbeafe;
      }}
      .stats {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 12px;
        padding: 20px 32px 8px;
      }}
      .stat {{
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 14px;
        padding: 14px 16px;
      }}
      .stat-label {{
        font-size: 12px;
        color: #64748b;
        margin-bottom: 6px;
        text-transform: uppercase;
        letter-spacing: 0.04em;
      }}
      .stat-value {{
        font-size: 15px;
        font-weight: 600;
        color: #0f172a;
      }}
      .content {{
        padding: 8px 32px 32px;
      }}
      .section {{
        margin-top: 24px;
      }}
      .section-header {{
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 12px;
        margin-bottom: 12px;
      }}
      .section-header h2 {{
        margin: 0;
        font-size: 18px;
      }}
      .count {{
        color: #475569;
        font-size: 13px;
      }}
      .card {{
        border: 1px solid #e2e8f0;
        border-left-width: 5px;
        border-radius: 14px;
        padding: 16px 18px;
        margin-bottom: 12px;
        background: #ffffff;
      }}
      .card h3 {{
        margin: 0 0 10px;
        font-size: 17px;
        line-height: 1.35;
      }}
      .card p {{
        margin: 0 0 10px;
        color: #334155;
        line-height: 1.6;
      }}
      .meta-row {{
        margin-bottom: 10px;
      }}
      .pill {{
        display: inline-block;
        margin-right: 8px;
        margin-bottom: 8px;
        padding: 5px 10px;
        border-radius: 999px;
        background: #eef2ff;
        color: #3730a3;
        font-size: 12px;
        font-weight: 600;
      }}
      .button {{
        display: inline-block;
        padding: 10px 14px;
        border-radius: 10px;
        background: #1d4ed8;
        color: #ffffff !important;
        text-decoration: none;
        font-weight: 600;
      }}
      .button-secondary {{
        background: #0f172a;
      }}
      .footer {{
        padding: 18px 32px 26px;
        font-size: 12px;
        color: #64748b;
        border-top: 1px solid #e2e8f0;
        background: #f8fafc;
      }}
      @media only screen and (max-width: 640px) {{
        .hero, .content, .stats, .footer {{
          padding-left: 20px;
          padding-right: 20px;
        }}
        .hero h1 {{
          font-size: 24px;
        }}
      }}
    </style>
  </head>
  <body>
    <div class="wrapper">
      <div class="container">
        <div class="hero">
          <div class="eyebrow">{escape(eyebrow)}</div>
          <h1>{escape(title)}</h1>
          <p>{escape(subtitle)}</p>
        </div>
        <div class="stats">{stats_html}</div>
        <div class="content">{''.join(sections)}</div>
        <div class="footer">
          Sent by RSS Watcher. This email includes a plain-text fallback for clients that do not render HTML.
        </div>
      </div>
    </div>
  </body>
</html>
"""


def _render_card(*, title: str, body: str, accent: str) -> str:
    border_color, background_color, text_color = SEVERITY_COLORS.get(
        accent,
        ("#1d4ed8", "#eff6ff", "#1e40af"),
    )
    return f"""
    <article class="card" style="border-left-color:{border_color}; background:{background_color};">
      <h3 style="color:{text_color};">{escape(title)}</h3>
      {body}
    </article>
    """


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _trim(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."
