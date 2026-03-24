import asyncio

import httpx

from app.collectors.android import AndroidBulletinIndexAdapter, GitilesLogAdapter
from app.collectors.kernel_org import KernelOrgReleasesAdapter
from app.collectors.lore import LoreListAdapter
from app.models import PollSource


def test_kernel_org_releases_adapter_parses_release_list() -> None:
    payload = {
        "releases": [
            {
                "moniker": "stable",
                "version": "6.19.9",
                "released": {"isodate": "2026-03-19"},
                "source": "https://cdn.kernel.org/pub/linux/kernel/v6.x/linux-6.19.9.tar.xz",
                "gitweb": "https://git.kernel.org/stable/h/v6.19.9",
            }
        ],
        "latest_stable": {"version": "6.19.9"},
    }

    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    source = PollSource(
        id="kernel_releases",
        adapter="kernel_org_releases",
        family="linux",
        poll_every="10m",
        url="https://www.kernel.org/releases.json",
    )

    async def run() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            adapter = KernelOrgReleasesAdapter(client)
            records = await adapter.collect(source)
        assert len(records) == 1
        assert records[0].title == "Kernel stable release 6.19.9"
        assert records[0].canonical_key == "kernel_releases:stable:6.19.9"

    asyncio.run(run())


def test_lore_adapter_parses_atom_feed_and_cves() -> None:
    atom = """<?xml version="1.0" encoding="us-ascii"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>CVE-2026-0001: netfilter: fix use-after-free</title>
    <updated>2026-03-20T08:14:08Z</updated>
    <link href="https://lore.kernel.org/linux-cve-announce/example/"/>
    <id>urn:uuid:test-entry</id>
    <content type="xhtml">
      <div xmlns="http://www.w3.org/1999/xhtml">
        <pre>The Linux kernel CVE team assigned CVE-2026-0001. This fixes a use-after-free in netfilter.</pre>
      </div>
    </content>
  </entry>
</feed>
"""

    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=atom))
    source = PollSource(
        id="linux_cve_announce",
        adapter="lore_list",
        family="linux",
        poll_every="10m",
        list_url="https://lore.kernel.org/linux-cve-announce/",
        default_kind="cve",
    )

    async def run() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            adapter = LoreListAdapter(client)
            records = await adapter.collect(source)
        assert len(records) == 1
        assert records[0].cve_ids == ["CVE-2026-0001"]
        assert "use-after-free" in records[0].keywords
        assert records[0].url == "https://lore.kernel.org/linux-cve-announce/example/"

    asyncio.run(run())


def test_android_bulletin_adapter_parses_latest_bulletin_summary() -> None:
    overview_html = """
    <html><body>
      <a href="/docs/security/bulletin/2026/2026-03-01">March</a>
    </body></html>
    """
    bulletin_html = """
    <html>
      <head>
        <meta property="og:title" content="Android Security BulletinMarch 2026 | Android Open Source Project">
      </head>
      <body>
        <aside class="note"><b>Note</b>: CVE-2026-1111 may be under limited exploitation.</aside>
        <table>
          <tr><th>CVE</th><th>References</th><th>Type</th><th>Severity</th></tr>
          <tr><td>CVE-2026-1111</td><td>A-1</td><td>EoP</td><td>Critical</td></tr>
          <tr><td>CVE-2026-1112</td><td>A-2</td><td>EoP</td><td>High</td></tr>
        </table>
      </body>
    </html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/asb-overview"):
            return httpx.Response(200, text=overview_html)
        return httpx.Response(200, text=bulletin_html)

    transport = httpx.MockTransport(handler)
    source = PollSource(
        id="android_bulletin_overview",
        adapter="android_bulletin_index",
        family="android",
        poll_every="6h",
        url="https://source.android.com/docs/security/bulletin/asb-overview",
        default_kind="bulletin",
        max_entries=1,
    )

    async def run() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            adapter = AndroidBulletinIndexAdapter(client)
            records = await adapter.collect(source)
        assert len(records) == 1
        assert records[0].title == "Android Security Bulletin March 2026"
        assert records[0].cve_ids == ["CVE-2026-1111", "CVE-2026-1112"]
        assert "Critical:1" in records[0].summary

    asyncio.run(run())


def test_gitiles_adapter_parses_json_log() -> None:
    payload = """ )]}'
{
  "log": [
    {
      "commit": "abc123",
      "author": {"time": "Mon Mar 23 19:01:23 2026 +0000"},
      "message": "ANDROID: fix overflow in io_uring path\\n\\nFixes: 1234"
    }
  ]
}
"""

    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=payload))
    source = PollSource(
        id="android_common_kernel",
        adapter="gitiles_log",
        family="android",
        poll_every="60m",
        repo_url="https://android.googlesource.com/kernel/common",
        branches=["android-mainline"],
        default_kind="commit",
        max_entries=5,
    )

    async def run() -> None:
        async with httpx.AsyncClient(transport=transport) as client:
            adapter = GitilesLogAdapter(client)
            records = await adapter.collect(source)
        assert len(records) == 1
        assert records[0].branch == "android-mainline"
        assert "overflow" in records[0].keywords
        assert records[0].url.endswith("/+/abc123")

    asyncio.run(run())
