from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select

from app.db.models import Item, PollRun, RawIngestEvent
from app.db.session import SessionLocal

router = APIRouter()


@router.get("/healthz")
async def healthz(request: Request) -> dict[str, object]:
    catalog = request.app.state.catalog
    scheduler = request.app.state.scheduler

    return {
        "status": "ok",
        "config_path": str(catalog.path),
        "enabled_sources": [source.id for source in catalog.enabled_sources()],
        "scheduler_running": scheduler.running,
    }


@router.get("/sources")
async def list_sources(request: Request) -> dict[str, object]:
    catalog = request.app.state.catalog
    return {
        "sources": [source.model_dump() for source in catalog.all_sources()],
    }


@router.post("/poll/{source_id}")
async def poll_source(source_id: str, request: Request) -> dict[str, object]:
    catalog = request.app.state.catalog
    collector_service = request.app.state.collector_service

    try:
        catalog.get(source_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown source: {source_id}") from exc

    result = await collector_service.poll_source(source_id)
    return {"result": result}


@router.get("/poll-runs/recent")
async def recent_poll_runs(limit: int = 20) -> dict[str, object]:
    with SessionLocal() as session:
        runs = session.scalars(
            select(PollRun).order_by(PollRun.started_at.desc()).limit(limit)
        ).all()

    return {
        "poll_runs": [
            {
                "source_id": run.source_id,
                "status": run.status,
                "items_seen": run.items_seen,
                "started_at": run.started_at.isoformat(),
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
                "error_message": run.error_message,
            }
            for run in runs
        ]
    }


@router.get("/items/recent")
async def recent_items(limit: int = 20) -> dict[str, object]:
    with SessionLocal() as session:
        items = session.scalars(
            select(Item).order_by(Item.updated_at.desc()).limit(limit)
        ).all()

    return {
        "items": [
            {
                "source_id": item.source_id,
                "kind": item.kind,
                "title": item.title,
                "score": item.score,
                "severity_bucket": item.severity_bucket,
                "url": item.url,
                "updated_at": item.updated_at.isoformat(),
            }
            for item in items
        ]
    }


@router.get("/raw-events/recent")
async def recent_raw_events(limit: int = 20) -> dict[str, object]:
    with SessionLocal() as session:
        events = session.scalars(
            select(RawIngestEvent).order_by(RawIngestEvent.fetched_at.desc()).limit(limit)
        ).all()

    return {
        "raw_events": [
            {
                "source_id": event.source_id,
                "external_id": event.external_id,
                "raw_type": event.raw_type,
                "fetched_at": event.fetched_at.isoformat(),
                "published_at": event.published_at.isoformat() if event.published_at else None,
                "canonical_key": event.canonical_key,
            }
            for event in events
        ]
    }
