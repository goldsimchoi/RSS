# Build Plan

## Current State

The repository already has:

- app startup and health endpoint
- source configuration loading
- scheduler registration
- collector adapter registry
- item and poll run persistence
- classification scaffolding
- immediate mail and daily digest interfaces

## Recommended Next Steps

### Step 1. Finish `kernel_org_releases`

Goal:

- reliably ingest kernel release JSON
- normalize release version, release type, and links
- persist only new release keys

Files:

- `app/collectors/kernel_org.py`
- `tests/`

Done when:

- recent kernel release entries appear in `/items/recent`
- duplicate polling does not create duplicate rows

### Step 2. Implement `lore_list`

Goal:

- fetch list pages from `linux-cve-announce`, `stable`, and `lkml`
- extract message URL, title, timestamp, and message ID
- normalize into patch or CVE items

Files:

- `app/collectors/lore.py`
- `config/sources.example.yaml`
- `tests/fixtures/`

Done when:

- `linux-cve-announce` produces confirmed security items
- `stable` and `lkml` entries show up as digest candidates

### Step 3. Implement Android bulletin parsing

Goal:

- fetch bulletin overview page
- discover the latest monthly bulletin links
- parse bulletin pages for CVE IDs, component, severity, and fix level

Files:

- `app/collectors/android.py`
- `tests/fixtures/`

Done when:

- Android bulletin items persist with `cve_ids`
- bulletin entries score into `confirmed_security`

### Step 4. Improve classification

Goal:

- move score weights fully into config
- add subsystem and branch tagging
- promote high-confidence items to immediate mail only

Files:

- `app/services/classifier.py`
- `config/rules.example.yaml`

Done when:

- the same source item can be reclassified without code edits
- alert fatigue is lower than sending all patches directly

### Step 5. Improve delivery

Goal:

- add HTML digest template
- track email delivery rows
- avoid sending duplicate immediate alerts

Files:

- `app/services/digest.py`
- `app/mail/smtp.py`
- `app/db/models.py`

Done when:

- one item only sends one immediate alert per recipient
- digests group items by severity and family

### Step 6. Add operator endpoints

Goal:

- recent poll run status
- muted rules
- reclassify item
- trigger manual poll per source

Files:

- `app/api/routes.py`

Done when:

- you can operate the service without touching the database directly

## Practical Development Order

Implement in this exact order:

1. `kernel_org_releases`
2. `lore_list`
3. Android bulletin parser
4. classification config externalization
5. mail templates and delivery tracking
6. admin endpoints

## Suggested First Production Rollout

Enable only:

- `kernel_releases`
- `linux_cve_announce`
- `android_bulletin_overview`

Keep these disabled until parsing quality is good:

- `linux_stable`
- `linux_lkml`
- `android_common_kernel`

This keeps the signal strong while the scoring model matures.
