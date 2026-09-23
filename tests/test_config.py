"""Invalid bearer-token configuration is rejected before accepting requests."""

import pytest

from backend.config import Settings


@pytest.mark.parametrize("token", ["", " ", " leading", "trailing ", "two parts", "line\nbreak"])
def test_hr_token_rejects_empty_and_whitespace_values(token):
    with pytest.raises(ValueError, match="HR_API_TOKEN"):
        Settings(hr_token=token, runtime_state_path=None)


def test_hr_and_employee_credentials_cannot_share_one_token():
    with pytest.raises(ValueError, match="must be different"):
        Settings(hr_token="shared-token", employee_tokens={"shared-token": "person-alpha"}, runtime_state_path=None)


@pytest.mark.parametrize("url", ["https://project.supabase.co", "postgresql://", "sqlite:///data.db"])
def test_database_url_requires_a_postgresql_host(url):
    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(database_url=url)


def test_database_url_is_loaded_without_exposing_credentials_in_repr(monkeypatch):
    url = "postgresql://postgres:private-password@db.example.com/postgres?sslmode=require"
    monkeypatch.setenv("DATABASE_URL", url)
    settings = Settings.from_env()
    assert settings.database_url == url
    assert "private-password" not in repr(settings)
