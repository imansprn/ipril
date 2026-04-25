import pytest

from config import Settings


def test_settings_from_env_ok(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "t")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "k")
    s = Settings.from_env()
    assert s.bot_token == "t"
    assert s.deepseek_api_key == "k"


def test_settings_from_env_strips_whitespace(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "  abc  ")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "  xyz\n")
    s = Settings.from_env()
    assert s.bot_token == "abc"
    assert s.deepseek_api_key == "xyz"


@pytest.mark.parametrize(
    "token,key",
    [
        ("", "k"),
        ("t", ""),
        ("", ""),
    ],
)
def test_settings_from_env_missing(monkeypatch, token, key):
    monkeypatch.setenv("BOT_TOKEN", token)
    monkeypatch.setenv("DEEPSEEK_API_KEY", key)
    with pytest.raises(RuntimeError, match="Missing required environment variable"):
        Settings.from_env()
