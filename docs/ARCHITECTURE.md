# Kernel And Android Update Watcher

## Goal

Build a small self-hosted service that:

- polls official Linux kernel and Android security/kernel sources
- identifies release notes, patch traffic, and likely security-relevant changes
- sends immediate alerts for high-confidence security items
- sends a daily digest email for lower-confidence patch and release activity

This design is intentionally biased toward a small, reliable MVP instead of a large event platform.

## Recommended Operating Model

Use a pull-based polling service first.

Why this is the right starting point:

- you do not need to operate inbound SMTP or IMAP infrastructure
- the main upstream sources are already public
- deduplication is easier when the server owns polling state
- one user or a small team can operate it on one VM

Do not start with Kafka, Celery, or a full mail ingestion pipeline unless you later need very high throughput.

## What To Collect

Split incoming data into three buckets:

1. Confirmed security items
2. Security candidates
3. General patch or release activity

Examples:

- Confirmed security items:
  - `linux-cve-announce`
  - Android Security Bulletins
  - bulletin entries with CVE IDs
- Security candidates:
  - patches mentioning `use-after-free`, `out-of-bounds`, `overflow`, `race`, `refcount`, `privilege`, `exploit`, `Fixes:`, or `Cc: stable`
  - Android common kernel commits that match security keywords
- General patch or release activity:
  - new kernel stable releases
  - subsystem patch series
  - Android common kernel branch updates

## High-Level Architecture

```text
                +---------------------+
                |   Poll Scheduler    |
                |  (cron/APScheduler) |
                +----------+----------+
                           |
                           v
                 +---------+----------+
                 |   Source Adapters   |
                 | RSS | HTML | Gitiles|
                 | lore | JSON | git   |
                 +---------+----------+
                           |
                           v
                 +---------+----------+
                 |   Raw Ingest Store  |
                 | raw payload + hash  |
                 +---------+----------+
                           |
                           v
                 +---------+----------+
                 | Normalizer/Linker   |
                 | canonical item model|
                 +---------+----------+
                           |
                           v
                 +---------+----------+
                 | Classifier/Scorer   |
                 | confirmed/candidate |
                 +----+-----------+----+
                      |           |
          immediate   |           | digest
             alert    v           v
                 +----+--+     +--+-----+
                 | Mailer |     | Digest |
                 +----+--+     +--+-----+
                      |           |
                      +-----+-----+
                            v
                     SMTP / SES / Mailgun
```

## Components

### 1. Scheduler

Use one lightweight scheduler process.

Recommended options:

- `cron` or `systemd timers` if you want the simplest Linux deployment
- `APScheduler` if you want scheduling inside a Python service

Recommendation:

- MVP: `APScheduler` inside the app container
- later: move to `systemd timers` if you want very explicit OS-level jobs

### 2. Source Adapters

Each source should have its own adapter so the rest of the pipeline does not care whether the upstream is RSS, Atom, HTML, JSON, or git.

Adapters you likely need:

- `kernel_org_releases`
- `lore_list`
- `android_bulletin_index`
- `android_bulletin_page`
- `gitiles_log`
- `git_poll`

Each adapter returns the same normalized ingest shape:

```json
{
  "source_id": "linux_cve_announce",
  "external_id": "message-id-or-url-or-commit",
  "title": "subject or headline",
  "url": "canonical upstream URL",
  "published_at": "2026-03-24T01:23:45Z",
  "raw_type": "atom|html|json|git",
  "raw_payload": {}
}
```

### 3. Raw Ingest Store

Persist raw upstream data before classification.

Why:

- debugging parser failures becomes easy
- classification rules can be improved and replayed later
- you can re-run enrichment without losing the original source text

Store:

- fetch timestamp
- source ID
- raw payload
- content hash
- upstream published timestamp
- upstream URL

### 4. Normalizer And Linker

Turn different upstream formats into one internal item model.

Normalize to fields like:

- `family`: `linux` or `android`
- `kind`: `release`, `bulletin`, `patch`, `commit`, `cve`
- `title`
- `summary`
- `source_url`
- `canonical_key`
- `published_at`
- `subsystem`
- `branch`
- `commit_id`
- `message_id`
- `cve_ids`
- `keywords`

Linking rules:

- same `message-id` means same lore item
- same `commit_id` means same git item
- same `CVE ID` merges bulletin and patch references
- same canonical URL or content hash deduplicates repeated fetches

### 5. Classifier And Scorer

This is the most important part because "one-day" tracking is noisy if everything is mailed directly.

Use tiered scoring instead of binary matching.

Suggested levels:

- `confirmed_security`
- `security_candidate_high`
- `security_candidate_medium`
- `general_patch`
- `release_only`

Suggested scoring inputs:

- `+100` if source is `linux-cve-announce`
- `+100` if Android bulletin explicitly lists a CVE
- `+40` if title/body contains `CVE-`
- `+25` if title/body contains `use-after-free`, `out-of-bounds`, `overflow`, `type confusion`, `privilege escalation`, `arbitrary write`
- `+15` if mail contains `Fixes:`
- `+15` if mail contains `Cc: stable`
- `+10` if patch touches `mm`, `netfilter`, `binder`, `ashmem`, `drivers/android`, `fs`, `io_uring`, or credential-related paths
- `-20` if it is only a release announcement without patch detail

Recommended policy:

- score `>= 100`: immediate email
- score `60-99`: include in next digest, optionally immediate if tagged critical
- score `< 60`: digest only

## Suggested Upstream Sources

Start with a small set of official sources.

### Linux

1. Kernel releases
   - `https://www.kernel.org/feeds/kdist.xml`
   - `https://www.kernel.org/releases.json`
2. lore kernel list archives
   - base: `https://lore.kernel.org/`
   - start with:
     - `linux-cve-announce`
     - `stable`
     - `lkml`
3. Optional later
   - `patchwork.kernel.org`
   - subsystem lists such as `netdev`, `linux-mm`, `linux-fsdevel`

### Android

1. Android Security Bulletins
   - `https://source.android.com/docs/security/bulletin/asb-overview`
2. Monthly Android bulletin pages
   - follow links discovered from the overview page
3. Android common kernel sources
   - docs: `https://source.android.com/docs/setup/build/building-kernels`
   - repo family: `https://android.googlesource.com/kernel/common`

Recommendation:

- MVP Linux sources: `kernel.org` + `linux-cve-announce` + `stable`
- MVP Android sources: bulletin overview + bulletin pages
- Phase 2: Android common kernel commit tracking
- Phase 3: subsystem-specific Linux lists and vendor bulletin support

## Polling Schedule

Suggested polling intervals:

- `kernel.org` releases: every 10 minutes
- `linux-cve-announce`: every 10 minutes
- `stable`: every 20 minutes
- `lkml`: every 30 minutes
- Android bulletin overview: every 6 hours
- Android common kernel commit logs: every 60 minutes

Delivery schedule:

- immediate alerts: within 5 minutes of classification
- daily digest: 09:00 Asia/Seoul
- optional evening digest: 18:00 Asia/Seoul

## Email Delivery Model

Use two outbound email types:

### Immediate alert

Send only for:

- confirmed security items
- very high confidence one-day candidates

Template:

- source
- severity bucket
- title
- CVE ID if present
- subsystem or branch
- why it matched
- direct upstream links

### Daily digest

Group by:

- Linux confirmed security
- Linux security candidates
- Linux general patch activity
- Android bulletins
- Android common kernel changes

Add a one-line reason per item so the digest is scannable.

## Database Shape

Use PostgreSQL for server deployment.

If you want the smallest possible MVP, SQLite is acceptable at first, but PostgreSQL is the better default if the service will stay online.

Suggested tables:

- `sources`
- `raw_ingest_events`
- `items`
- `item_links`
- `classifications`
- `watch_rules`
- `email_deliveries`
- `poll_runs`

Minimal `items` fields:

- `id`
- `source_id`
- `family`
- `kind`
- `canonical_key`
- `title`
- `summary`
- `url`
- `published_at`
- `score`
- `severity_bucket`
- `branch`
- `subsystem`
- `commit_id`
- `message_id`
- `cve_ids`
- `status`

## Repository Layout

Suggested project layout:

```text
rss/
  apps/
    collector/
    normalizer/
    classifier/
    digest/
    mailer/
    api/
  config/
    sources.example.yaml
    rules.example.yaml
  db/
    migrations/
  docs/
    ARCHITECTURE.md
  tests/
    fixtures/
```

If you want to keep it even smaller:

```text
rss/
  app/
    collectors/
    parsers/
    rules/
    mail/
  config/
  docs/
```

## Implementation Recommendation

For this use case, the most practical stack is:

- Python 3.12
- FastAPI for a tiny admin API or health endpoints
- APScheduler for polling jobs
- PostgreSQL
- SQLAlchemy or SQLModel
- SMTP provider, AWS SES, or Mailgun for outbound email
- Docker Compose for deployment

Avoid these in MVP:

- Kafka
- Redis queues
- Celery workers
- inbound mail parsing
- multi-service orchestration unless you truly need it

## Alert Rules That Work Well In Practice

Recommended default rule set:

1. Send immediate email for `linux-cve-announce`.
2. Send immediate email for Android bulletin entries with CVE data.
3. Put all `stable` and `lkml` matches into digest unless score is very high.
4. Promote digest items to immediate alert only when:
   - CVE is present
   - multiple security keywords are present
   - the patch is backported to stable
   - the same issue appears in both a patch and a bulletin

This prevents alert fatigue while still surfacing likely one-day material quickly.

## Rollout Plan

### Phase 1: Low-risk MVP

Build only:

- `kernel.org` release watcher
- `linux-cve-announce` watcher
- Android Security Bulletin watcher
- daily digest + immediate mailer

This gets you useful signal fast with low parsing risk.

### Phase 2: Patch intelligence

Add:

- `stable` watcher
- `lkml` watcher
- keyword-based candidate scoring
- subsystem tagging

### Phase 3: Android kernel commits

Add:

- Android common kernel branch polling
- commit-to-bulletin linking
- branch-specific watch rules

### Phase 4: Operator tooling

Add:

- small web UI
- reclassify item action
- mute/whitelist rules
- custom per-branch digest filters

## Why Not Use Mailing List Subscription First

Subscribing a mailbox directly to kernel lists is possible, but not the best first design.

Problems it introduces early:

- mailbox rate limits
- spam and bounce handling
- parsing MIME edge cases
- duplicate mail routing
- more operational burden than public archive polling

If later you need the fastest possible delivery, add inbound mail as a second ingestion path, but keep the same downstream normalization and classification pipeline.

## Official References

- Kernel.org FAQ: `https://www.kernel.org/faq.html`
- Kernel release RSS: `https://www.kernel.org/feeds/kdist.xml`
- Kernel release JSON: `https://www.kernel.org/releases.json`
- lore archive web UI: `https://lore.kernel.org/`
- lore docs: `https://korg.docs.kernel.org/lore.html`
- Android Security Bulletins overview: `https://source.android.com/docs/security/bulletin/asb-overview`
- Android bulletins home: `https://source.android.com/docs/security/bulletin`
- Android kernel build/source docs: `https://source.android.com/docs/setup/build/building-kernels`
