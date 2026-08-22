"""Tests for settings resolution: env vars win, config.py is a fallback."""

import builtins
import importlib
import types

import pytest

import settings

ENV_KEYS = [
    "TELEGRAM_TOKEN",
    "OWM_API_KEY",
    "EXCHANGERATE_API_KEY",
    "LASTFM_API_KEY",
    "ADMIN_IDS",
    "ADMIN_USERNAME",
]


@pytest.fixture
def fresh_settings(monkeypatch):
    """Reload settings with a clean environment; restore afterwards."""
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    def _reload():
        importlib.reload(settings)
        return settings

    yield _reload

    importlib.reload(settings)


def test_env_vars_win_over_everything(fresh_settings, monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "env-token")
    monkeypatch.setenv("OWM_API_KEY", "env-owm")
    monkeypatch.setenv("ADMIN_IDS", "111, 222")
    s = fresh_settings()
    assert s.TOKEN == "env-token"
    assert s.OWM == "env-owm"
    assert s.ADMIN_IDS == [111, 222]


def test_empty_env_var_treated_as_unset(fresh_settings, monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "")

    real_import = builtins.__import__

    def no_config(name, *args, **kwargs):
        if name == "config":
            raise ModuleNotFoundError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_config)

    s = fresh_settings()
    assert s.TOKEN == ""


def test_falls_back_to_config_module(fresh_settings, monkeypatch):
    fake = types.ModuleType("config")
    fake.TOKEN = "file-token"
    fake.OWM = "file-owm"
    fake.er_api_key = "file-er"
    fake.LASTFM_API_KEY = "file-lastfm"
    fake.ADMIN_IDS = [42]
    fake.ADMIN_USERNAME = "file-admin"
    monkeypatch.setitem(__import__("sys").modules, "config", fake)

    s = fresh_settings()
    assert s.TOKEN == "file-token"
    assert s.OWM == "file-owm"
    assert s.ER_API_KEY == "file-er"
    assert s.LASTFM_API_KEY == "file-lastfm"
    assert s.ADMIN_IDS == [42]
    assert s.ADMIN_USERNAME == "file-admin"


def test_defaults_without_config_module(fresh_settings, monkeypatch):
    real_import = builtins.__import__

    def no_config(name, *args, **kwargs):
        if name == "config":
            raise ModuleNotFoundError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_config)

    s = fresh_settings()
    assert s.TOKEN == ""
    assert s.ER_API_KEY == ""
    assert s.ADMIN_IDS == []
    assert s.ADMIN_USERNAME == "SL0RD"


def test_parse_admin_ids_accepts_list():
    assert settings.parse_admin_ids([1, 2, 3]) == [1, 2, 3]


def test_parse_admin_ids_parses_string():
    assert settings.parse_admin_ids("1, 2 ,3") == [1, 2, 3]
    assert settings.parse_admin_ids("") == []


def test_parse_admin_ids_rejects_garbage():
    with pytest.raises(ValueError, match="comma-separated integers"):
        settings.parse_admin_ids("abc,def")
