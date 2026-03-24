from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.db.models import EmailDelivery, Item
from app.db.session import SessionLocal
from app.mail import Mailer
from app.mail.renderers import render_daily_digest_email
from app.settings import settings


class DigestService:
    def __init__(self, mailer: Mailer, digest_score_min: int) -> None:
        self.mailer = mailer
        self.digest_score_min = digest_score_min

    async def send_daily_digest(self) -> None:
        since = datetime.now(timezone.utc) - timedelta(days=1)

        with SessionLocal() as session:
            items = session.scalars(
                select(Item)
                .where(Item.updated_at >= since)
                .where(Item.score >= self.digest_score_min)
                .order_by(Item.score.desc(), Item.updated_at.desc())
            ).all()

        if not items:
            return

        self.mailer.send(render_daily_digest_email(items=items[:50], since=since))

        with SessionLocal() as session:
            for recipient in settings.smtp_to:
                session.add(
                    EmailDelivery(
                        item_key=f"digest:{since.date().isoformat()}",
                        delivery_type="digest",
                        recipient=recipient,
                        status="sent",
                        sent_at=datetime.now(timezone.utc),
                    )
                )
            session.commit()
