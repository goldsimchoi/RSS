import logging
import re
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.services.collector import CollectorService
from app.services.digest import DigestService
from app.services.source_loader import SourceCatalog

logger = logging.getLogger(__name__)

INTERVAL_PATTERN = re.compile(r"^(?P<value>\d+)(?P<unit>[smhd])$")


def parse_interval(spec: str) -> IntervalTrigger:
    match = INTERVAL_PATTERN.match(spec.strip())
    if not match:
        raise ValueError(f"Unsupported poll interval: {spec}")

    value = int(match.group("value"))
    unit = match.group("unit")
    kwargs = {
        "seconds": 0,
        "minutes": 0,
        "hours": 0,
        "days": 0,
    }

    if unit == "s":
        kwargs["seconds"] = value
    elif unit == "m":
        kwargs["minutes"] = value
    elif unit == "h":
        kwargs["hours"] = value
    elif unit == "d":
        kwargs["days"] = value

    return IntervalTrigger(**kwargs)


def build_scheduler(
    collector_service: CollectorService,
    digest_service: DigestService,
    catalog: SourceCatalog,
    timezone: str,
) -> AsyncIOScheduler:
    tzinfo = ZoneInfo(timezone)
    scheduler = AsyncIOScheduler(timezone=tzinfo)

    for source in catalog.enabled_sources():
        scheduler.add_job(
            collector_service.poll_source,
            trigger=parse_interval(source.poll_every),
            args=[source.id],
            id=f"poll-{source.id}",
            replace_existing=True,
        )
        logger.info("Registered polling job for source=%s interval=%s", source.id, source.poll_every)

    scheduler.add_job(
        digest_service.send_daily_digest,
        trigger=CronTrigger.from_crontab(catalog.delivery.digest_cron, timezone=tzinfo),
        id="daily-digest",
        replace_existing=True,
    )
    logger.info("Registered daily digest cron=%s", catalog.delivery.digest_cron)
    return scheduler
