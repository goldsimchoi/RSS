from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collectors import CollectorRegistry
from app.db.models import EmailDelivery, Item, PollRun, RawIngestEvent
from app.db.session import SessionLocal
from app.mail import Mailer
from app.mail.renderers import render_immediate_alert_email
from app.models import CollectedRecord
from app.services.classifier import ClassificationResult, ClassifierService
from app.services.source_loader import SourceCatalog
from app.settings import settings

logger = logging.getLogger(__name__)


class CollectorService:
    def __init__(
        self,
        catalog: SourceCatalog,
        registry: CollectorRegistry,
        classifier: ClassifierService,
        mailer: Mailer,
        immediate_score_min: int,
    ) -> None:
        self.catalog = catalog
        self.registry = registry
        self.classifier = classifier
        self.mailer = mailer
        self.immediate_score_min = immediate_score_min

    async def poll_source(self, source_id: str) -> dict[str, int | str]:
        source = self.catalog.get(source_id)
        poll_run = PollRun(source_id=source.id, status="started")

        with SessionLocal() as session:
            session.add(poll_run)
            session.commit()
            session.refresh(poll_run)

        try:
            adapter = self.registry.get(source.adapter)
            records = await adapter.collect(source)
            inserted, seen = self._upsert_records(records)
            self._finish_poll_run(poll_run.id, "success", seen, None)
            logger.info("Polling finished source=%s inserted=%s seen=%s", source.id, inserted, seen)
            return {"source_id": source.id, "inserted": inserted, "seen": seen, "status": "success"}
        except Exception as exc:
            logger.exception("Polling failed for source=%s", source.id)
            self._finish_poll_run(poll_run.id, "failed", 0, str(exc))
            return {"source_id": source.id, "inserted": 0, "seen": 0, "status": "failed"}

    def _upsert_records(self, records: list[CollectedRecord]) -> tuple[int, int]:
        inserted = 0
        seen = len(records)

        with SessionLocal() as session:
            for record in records:
                self._store_raw_event(session, record)
                existing = session.scalar(select(Item).where(Item.canonical_key == record.canonical_key))
                classified = self.classifier.classify(record)

                if existing:
                    existing.updated_at = datetime.now(timezone.utc)
                    existing.score = classified.score
                    existing.severity_bucket = classified.severity_bucket
                    existing.title = record.title
                    existing.summary = record.summary
                    existing.url = record.url
                    existing.keywords = ",".join(record.keywords)
                    existing.cve_ids = ",".join(record.cve_ids)
                    existing.subsystem = record.subsystem
                    existing.branch = record.branch
                    existing.published_at = record.published_at
                    continue

                session.add(
                    Item(
                        source_id=record.source_id,
                        family=record.family,
                        kind=record.kind,
                        canonical_key=record.canonical_key,
                        external_id=record.external_id,
                        title=record.title,
                        summary=record.summary,
                        url=record.url,
                        score=classified.score,
                        severity_bucket=classified.severity_bucket,
                        cve_ids=",".join(record.cve_ids),
                        keywords=",".join(record.keywords),
                        subsystem=record.subsystem,
                        branch=record.branch,
                        published_at=record.published_at,
                    )
                )
                inserted += 1

                if classified.score >= self.immediate_score_min:
                    self._send_immediate_alert(session, record, classified)

            session.commit()

        return inserted, seen

    def _store_raw_event(self, session: Session, record: CollectedRecord) -> None:
        payload = json.dumps(record.raw_payload, ensure_ascii=False, sort_keys=True)
        content_hash = sha256(
            f"{record.source_id}|{record.external_id}|{record.raw_type}|{payload}".encode("utf-8")
        ).hexdigest()
        existing = session.scalar(select(RawIngestEvent).where(RawIngestEvent.content_hash == content_hash))
        if existing:
            return

        session.add(
            RawIngestEvent(
                source_id=record.source_id,
                external_id=record.external_id,
                canonical_key=record.canonical_key,
                raw_type=record.raw_type,
                content_hash=content_hash,
                payload=payload,
                published_at=record.published_at,
            )
        )

    def _finish_poll_run(self, poll_run_id: int, status: str, items_seen: int, error_message: str | None) -> None:
        with SessionLocal() as session:
            poll_run = session.get(PollRun, poll_run_id)
            if not poll_run:
                return
            poll_run.status = status
            poll_run.items_seen = items_seen
            poll_run.error_message = error_message
            poll_run.finished_at = datetime.now(timezone.utc)
            session.commit()

    def _send_immediate_alert(
        self,
        session: Session,
        record: CollectedRecord,
        classified: ClassificationResult,
    ) -> None:
        recipients = settings.smtp_to
        self.mailer.send(
            render_immediate_alert_email(
                record=record,
                severity_bucket=classified.severity_bucket,
                score=classified.score,
                reasons=classified.reasons,
            )
        )
        for recipient in recipients:
            session.add(
                EmailDelivery(
                    item_key=record.canonical_key,
                    delivery_type="immediate",
                    recipient=recipient,
                    status="sent",
                    sent_at=datetime.now(timezone.utc),
                )
            )
