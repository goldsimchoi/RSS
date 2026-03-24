from pathlib import Path

from app.services.source_loader import load_sources_config


def test_load_sources_config_from_example() -> None:
    catalog = load_sources_config(Path("config/sources.example.yaml"))
    assert catalog.config.timezone == "Asia/Seoul"
    assert any(source.id == "linux_cve_announce" for source in catalog.all_sources())
