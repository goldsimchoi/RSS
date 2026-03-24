from pathlib import Path

import yaml

from app.models import PollSource, SourcesConfig
from app.settings import settings


class SourceCatalog:
    def __init__(self, config: SourcesConfig, path: Path) -> None:
        self.config = config
        self.path = path
        self._source_map = {source.id: source for source in config.sources}
        self.delivery = config.delivery

    def get(self, source_id: str) -> PollSource:
        return self._source_map[source_id]

    def all_sources(self) -> list[PollSource]:
        return list(self._source_map.values())

    def enabled_sources(self) -> list[PollSource]:
        return [source for source in self._source_map.values() if source.enabled]


def load_sources_config(path: Path | None = None) -> SourceCatalog:
    config_path = path or settings.effective_sources_config_path
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    config = SourcesConfig.model_validate(raw)
    return SourceCatalog(config=config, path=config_path)
