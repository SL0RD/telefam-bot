"""Runtime configuration.

Values are resolved from environment variables first (Docker/CI deployments),
then from an optional local ``config.py`` (local development). Missing values
fall back to safe defaults so the app can at least import cleanly.
"""

import os

# Environment variable name -> legacy attribute name in config.py
_ENV_MAP = {
    "TELEGRAM_TOKEN": "TOKEN",
    "OWM_API_KEY": "OWM",
    "EXCHANGERATE_API_KEY": "er_api_key",
    "LASTFM_API_KEY": "LASTFM_API_KEY",
    "ADMIN_IDS": "ADMIN_IDS",
    "ADMIN_USERNAME": "ADMIN_USERNAME",
}


def _file_config():
    """Return the optional config.py module, or None if it doesn't exist."""
    try:
        import config
    except ModuleNotFoundError:
        return None
    return config


def _get(env_name: str, default=None):
    """Resolve a setting: environment variable wins, then config.py, then default."""
    value = os.environ.get(env_name)
    if value:  # treat empty string as unset
        return value
    file_cfg = _file_config()
    if file_cfg is not None:
        return getattr(file_cfg, _ENV_MAP[env_name], default)
    return default


def parse_admin_ids(value) -> list[int]:
    """Accept either an iterable of IDs or a comma-separated string of integers."""
    if isinstance(value, str):
        try:
            return [int(part.strip()) for part in value.split(",") if part.strip()]
        except ValueError as e:
            raise ValueError(
                f"ADMIN_IDS must be comma-separated integers, got: {value!r}"
            ) from e
    return [int(v) for v in value or []]


TOKEN = _get("TELEGRAM_TOKEN", "")
OWM = _get("OWM_API_KEY", "")
ER_API_KEY = _get("EXCHANGERATE_API_KEY", "")
LASTFM_API_KEY = _get("LASTFM_API_KEY", "")
ADMIN_USERNAME = _get("ADMIN_USERNAME", "SL0RD")
ADMIN_IDS = parse_admin_ids(_get("ADMIN_IDS", []))
