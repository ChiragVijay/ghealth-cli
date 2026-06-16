import json
import time

from typer.testing import CliRunner

from ghealth.auth.token_store import save_tokens
from ghealth.cli import app
from ghealth.config import Config, save_config

runner = CliRunner()


def test_doctor_json_without_config(mock_keyring) -> None:
    _ = mock_keyring
    result = runner.invoke(app, ["--format", "json", "doctor"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["configured"] is False
    assert data["authenticated"] is False
    assert data["privacy"]["secrets_redacted"] is True
    assert "auth configure" in data["next_action"]


def test_doctor_json_redacts_secrets(mock_keyring) -> None:
    save_config(
        Config(
            client_id="1234567890abcdef.apps.googleusercontent.com",
            client_secret="client-secret-value",
            token_storage="keyring",
        ),
    )
    save_tokens(
        {
            "access_token": "access-secret-token",
            "refresh_token": "refresh-secret-token",
            "expires_at": int(time.time()) + 3600,
            "scope": "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
        },
    )

    result = runner.invoke(app, ["--format", "json", "doctor"])

    assert result.exit_code == 0
    stdout = result.stdout
    data = json.loads(stdout)
    assert data["configured"] is True
    assert data["authenticated"] is True
    assert data["config"]["client_id"].startswith("1234...")
    assert "client-secret-value" not in stdout
    assert "access-secret-token" not in stdout
    assert "refresh-secret-token" not in stdout


def test_examples_json_marks_destructive_commands() -> None:
    result = runner.invoke(app, ["--format", "json", "examples"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["default_format"] == "json"
    commands = [
        example
        for group in data["groups"]
        for example in group["examples"]
        if example["command"].startswith(("ghealth data-points batch-delete", "ghealth auth revoke"))
    ]
    assert commands
    assert all(example["requires_explicit_user_confirmation"] for example in commands)
    assert any("--limit" in example["command"] for group in data["groups"] for example in group["examples"])
    assert any(
        example["command"] == "ghealth --format json calories daily --last-days 5"
        for group in data["groups"]
        for example in group["examples"]
    )
