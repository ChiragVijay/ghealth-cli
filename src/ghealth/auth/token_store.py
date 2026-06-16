import contextlib
import json
from pathlib import Path

import keyring
from keyring.errors import KeyringError

from ghealth.config import get_config_dir, load_config


def get_token_path() -> Path:
    """Return the path to tokens.json when using plaintext storage."""
    return get_config_dir() / "tokens.json"


def load_tokens() -> dict | None:
    """
    Load OAuth tokens.

    Decide between keyring or plaintext depending on the local configuration.
    """
    config = load_config()
    storage = "keyring" if not config else config.token_storage

    if storage == "plaintext":
        path = get_token_path()
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
        return None
    try:
        val = keyring.get_password("ghealth", "tokens")
        if val:
            return json.loads(val)
    except (json.JSONDecodeError, KeyringError):
        # keyrings might fail or raise exception if not initialized
        return None
    return None


def save_tokens(tokens: dict) -> None:
    """
    Save OAuth tokens.

    Decide between keyring or plaintext. Raise RuntimeError if keyring storage fails.
    """
    config = load_config()
    storage = "keyring" if not config else config.token_storage

    # Ensure config directory exists
    get_config_dir().mkdir(parents=True, exist_ok=True)

    if storage == "plaintext":
        path = get_token_path()
        path.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    else:
        try:
            keyring.set_password("ghealth", "tokens", json.dumps(tokens))
        except KeyringError as e:
            msg = (
                f"Failed to store tokens in OS keyring: {e}.\n"
                "Please configure plaintext storage if a keyring service is not available:\n"
                "ghealth auth configure --token-storage plaintext --i-understand-health-data-risk"
            )
            raise RuntimeError(msg) from e


def delete_tokens() -> None:
    """Delete all local token information from both plaintext files and the OS keyring."""
    # Delete from plaintext path
    path = get_token_path()
    if path.exists():
        with contextlib.suppress(Exception):
            path.unlink()

    # Delete from keyring
    with contextlib.suppress(Exception):
        keyring.delete_password("ghealth", "tokens")
