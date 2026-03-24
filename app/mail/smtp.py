import logging
import smtplib
from email.message import EmailMessage

from app.mail.base import MailMessage, Mailer
from app.settings import settings

logger = logging.getLogger(__name__)


class SmtpMailer(Mailer):
    def send(self, message: MailMessage) -> None:
        recipients = message.recipients or settings.smtp_to
        if not settings.smtp_host:
            logger.info("SMTP host is not configured. Mail preview subject=%s", message.subject)
            logger.debug("Mail recipients=%s", recipients)
            logger.debug("Mail body:\n%s", message.body)
            if message.html_body:
                logger.debug("Mail html body:\n%s", message.html_body)
            return

        email_message = EmailMessage()
        email_message["Subject"] = message.subject
        email_message["From"] = settings.smtp_from
        email_message["To"] = ", ".join(recipients)
        email_message.set_content(message.body)
        if message.html_body:
            email_message.add_alternative(message.html_body, subtype="html")

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
            smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(email_message)
