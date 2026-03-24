from abc import ABC, abstractmethod

from httpx import AsyncClient

from app.models import CollectedRecord, PollSource


class SourceAdapter(ABC):
    def __init__(self, http_client: AsyncClient) -> None:
        self.http_client = http_client

    @abstractmethod
    async def collect(self, source: PollSource) -> list[CollectedRecord]:
        raise NotImplementedError
