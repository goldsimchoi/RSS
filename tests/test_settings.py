from app.settings import Settings


def test_settings_split_smtp_to_from_plain_string(monkeypatch) -> None:
    monkeypatch.setenv("RSS_SMTP_TO", "alpha@example.com,beta@example.com")
    settings = Settings()
    assert settings.smtp_to == ["alpha@example.com", "beta@example.com"]
