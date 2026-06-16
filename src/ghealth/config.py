import json
from pathlib import Path

from platformdirs import user_config_dir
from pydantic import BaseModel, ValidationError


class Config(BaseModel):
    client_id: str
    client_secret: str
    token_storage: str = "keyring"
    auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    token_uri: str = "https://oauth2.googleapis.com/token"
    user_email: str | None = None


def get_config_dir() -> Path:
    """Return the platform-specific user configuration directory for ghealth."""
    return Path(user_config_dir(appname="ghealth"))


def get_config_path() -> Path:
    """Return the path to config.json."""
    return get_config_dir() / "config.json"


def load_config() -> Config | None:
    """Load configuration from config.json. Return None if it doesn't exist or is invalid."""
    path = get_config_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Config(**data)
    except (json.JSONDecodeError, OSError, ValidationError):
        return None


def save_config(config: Config) -> None:
    """Save configuration to config.json, ensuring the directory exists."""
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def parse_credentials_json(filepath: Path) -> dict:
    """
    Parse a downloaded Google Cloud OAuth client credentials JSON file.

    Support both 'installed' and 'web' structures.
    """
    if not filepath.exists():
        msg = f"Credentials file not found at {filepath}"
        raise FileNotFoundError(msg)
    try:
        data = json.loads(filepath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON in credentials file: {e}"
        raise ValueError(msg) from e
    except OSError as e:
        msg = f"Could not read credentials file: {e}"
        raise ValueError(msg) from e

    # Check for root keys: 'installed' or 'web'
    client_data = data.get("installed") or data.get("web")
    if not client_data:
        msg = "Missing 'installed' or 'web' root key in Google credentials JSON file."
        raise ValueError(msg)

    required_keys = ["client_id", "client_secret"]
    for key in required_keys:
        if key not in client_data:
            msg = f"Missing required key '{key}' in Google credentials JSON file."
            raise ValueError(msg)

    return {
        "client_id": client_data["client_id"],
        "client_secret": client_data["client_secret"],
        "auth_uri": client_data.get("auth_uri", "https://accounts.google.com/o/oauth2/auth"),
        "token_uri": client_data.get("token_uri", "https://oauth2.googleapis.com/token"),
    }
