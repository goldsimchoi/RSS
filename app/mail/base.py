from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class MailMessage(BaseModel):
    subject: str
    body: str
    html_body: str | None = None
    recipients: list[str] = Field(default_factory=list)


class Mailer(ABC):
    @abstractmethod
    def send(self, message: MailMessage) -> None:
        raise NotImplementedError
