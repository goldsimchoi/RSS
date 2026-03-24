from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from app.api.routes import router
from app.collectors import CollectorRegistry
from app.core.logging import configure_logging
from app.core.scheduler import build_scheduler
from app.db.session import init_db
from app.mail import SmtpMailer
from app.services.classifier import ClassifierService
from app.services.collector import CollectorService
from app.services.digest import DigestService
from app.services.source_loader import load_sources_config
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(settings.debug)
    init_db()

    catalog = load_sources_config()
    http_client = httpx.AsyncClient(follow_redirects=True)
    registry = CollectorRegistry(http_client=http_client)
    classifier = ClassifierService(catalog=catalog)
    mailer = SmtpMailer()
    collector_service = CollectorService(
        catalog=catalog,
        registry=registry,
        classifier=classifier,
        mailer=mailer,
        immediate_score_min=catalog.delivery.immediate_score_min,
    )
    digest_service = DigestService(
        mailer=mailer,
        digest_score_min=catalog.delivery.digest_score_min,
    )
    scheduler = build_scheduler(
        collector_service=collector_service,
        digest_service=digest_service,
        catalog=catalog,
        timezone=settings.timezone,
    )

    app.state.catalog = catalog
    app.state.collector_service = collector_service
    app.state.scheduler = scheduler

    scheduler.start()
    if settings.poll_on_startup:
        for source in catalog.enabled_sources():
            await collector_service.poll_source(source.id)

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await http_client.aclose()


app = FastAPI(title="RSS Watcher", lifespan=lifespan)
app.include_router(router)
