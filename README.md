# RSS Watcher

Small self-hosted watcher for Linux kernel and Android kernel/security updates.

## Current Scope

This repository now contains a runnable MVP skeleton with:

- FastAPI app
- APScheduler-based polling jobs
- source configuration loader
- SQLAlchemy models for collected items and poll runs
- scoring service for security candidates
- SMTP mailer interface
- example source configuration for kernel and Android sources

## Project Layout

```text
rss/
  app/
    api/
    collectors/
    core/
    db/
    mail/
    models/
    services/
  config/
  docs/
  tests/
```

## Run Locally

```bash
py -3.10 -m venv .venv
. .venv/Scripts/activate
pip install -e .[dev]
uvicorn app.main:app --reload
```

The app starts with SQLite by default and reads source definitions from `config/sources.yaml` if it exists, otherwise `config/sources.example.yaml`.

On Windows, prefer official CPython 3.10 to 3.13 or Docker. The MSYS2 Python 3.14 environment in this workspace does not currently have wheels for every dependency.

## Main Endpoints

- `GET /healthz`
- `GET /sources`
- `POST /poll/{source_id}`
- `GET /poll-runs/recent`
- `GET /items/recent`
- `GET /raw-events/recent`

## Recommended Build Order

1. Implement the first real collector: `kernel_org_releases`.
2. Implement `lore_list` message discovery and message body fetch.
3. Implement Android bulletin index parsing.
4. Add richer deduplication and digest email templates.
5. Add admin endpoints for muting or promoting rules.

## Deployment

`docker-compose.yml` provides a minimal PostgreSQL-backed starting point.
