import contextlib
import json
import stat
from pathlib import Path

import keyring
from keyring.errors import KeyringError

from ghealth.config import get_config_dir, load_config


def get_token_path() -> Path:
    """Return the path to tokens.json when using file-based storage."""
    return get_config_dir() / "tokens.json"


def _load_from_file() -> dict | None:
    """Load tokens from the local file."""
    path = get_token_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _load_from_keyring() -> dict | None:
    """Load tokens from the OS keyring."""
    try:
        val = keyring.get_password("ghealth", "tokens")
        if val:
            return json.loads(val)
    except (json.JSONDecodeError, KeyringError):
        return None
    return None


def _save_to_file(tokens: dict) -> None:
    """Save tokens to a local file with restricted permissions (owner read/write only)."""
    get_config_dir().mkdir(parents=True, exist_ok=True)
    path = get_token_path()
    path.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    # owner read/write only (0600)
    with contextlib.suppress(OSError):
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _save_to_keyring(tokens: dict) -> None:
    """Save tokens to the OS keyring. Raises KeyringError on failure."""
    keyring.set_password("ghealth", "tokens", json.dumps(tokens))


def load_tokens() -> dict | None:
    """
    Load OAuth tokens.

    Uses the configured storage backend:
    - ``auto``: try keyring first, fall back to local file.
    - ``keyring``: keyring only.
    - ``plaintext``: local file only.
    """
    config = load_config()
    storage = "auto" if not config else config.token_storage

    if storage == "plaintext":
        return _load_from_file()

    if storage == "auto":
        # Try keyring first, fall back to file
        tokens = _load_from_keyring()
        if tokens is not None:
            return tokens
        return _load_from_file()

    # storage == "keyring"
    return _load_from_keyring()


def save_tokens(tokens: dict) -> None:
    """
    Save OAuth tokens.

    Uses the configured storage backend:
    - ``auto``: write to local file (0600 perms) AND keyring (best-effort).
    - ``keyring``: keyring only; raises RuntimeError on failure.
    - ``plaintext``: local file only (0600 perms).
    """
    config = load_config()
    storage = "auto" if not config else config.token_storage

    if storage == "plaintext":
        _save_to_file(tokens)
        return

    if storage == "auto":
        _save_to_file(tokens)
        with contextlib.suppress(KeyringError, Exception):
            _save_to_keyring(tokens)
        return

    get_config_dir().mkdir(parents=True, exist_ok=True)
    try:
        _save_to_keyring(tokens)
    except KeyringError as e:
        msg = (
            f"Failed to store tokens in OS keyring: {e}.\n"
            "Consider switching to 'auto' storage for automatic fallback:\n"
            "ghealth auth configure --token-storage auto"
        )
        raise RuntimeError(msg) from e


def delete_tokens() -> None:
    """Delete all local token information from both plaintext files and the OS keyring."""
    path = get_token_path()
    if path.exists():
        with contextlib.suppress(Exception):
            path.unlink()

    with contextlib.suppress(Exception):
        keyring.delete_password("ghealth", "tokens")
