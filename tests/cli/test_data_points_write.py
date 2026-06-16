import json
import time

import httpx
from typer.testing import CliRunner

import ghealth.cli
from ghealth.api import GHealthApiClient
from ghealth.auth.token_store import save_tokens
from ghealth.cli import app
from ghealth.config import Config, save_config

runner = CliRunner()


def _setup_auth(
    mock_keyring,
    *,
    scope: str = "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",
) -> None:
    config = Config(client_id="id", client_secret="secret", token_storage="keyring")
    save_config(config)
    save_tokens(
        {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_at": int(time.time()) + 3600,
            "scope": scope,
        },
    )


def _patch_api_client(monkeypatch, handler: httpx.MockTransport) -> GHealthApiClient:
    http_client = httpx.Client(transport=handler, base_url="https://health.googleapis.com")
    config = Config(client_id="id", client_secret="secret", token_storage="keyring")
    tokens = {
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "expires_at": int(time.time()) + 3600,
    }
    api_client = GHealthApiClient(config, tokens, client=http_client)

    def factory(*, client=None):
        if client is not None:
            return GHealthApiClient(config, tokens, client=client)
        return api_client

    monkeypatch.setattr(ghealth.cli, "create_authenticated_client", factory)
    return api_client


def test_data_points_create_posts_body_with_yes(tmp_path, mock_keyring, monkeypatch) -> None:
    _setup_auth(
        mock_keyring,
        scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    )
    body_file = tmp_path / "weight.json"
    body_file.write_text(json.dumps({"weight": {"kg": 72}}), encoding="utf-8")
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = request.read()
        return httpx.Response(200, json={"name": "operations/create-1", "done": False})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        ["--format", "json", "data-points", "create", "weight", "--body", str(body_file), "--yes"],
    )

    assert result.exit_code == 0
    assert json.loads(captured_body) == {"weight": {"kg": 72}}
    data = json.loads(result.stdout)
    assert data["name"] == "operations/create-1"


def test_data_points_create_requires_write_scope(tmp_path, mock_keyring) -> None:
    _setup_auth(mock_keyring)
    body_file = tmp_path / "weight.json"
    body_file.write_text(json.dumps({"weight": {"kg": 72}}), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--format", "json", "data-points", "create", "weight", "--body", str(body_file), "--yes"],
    )

    assert result.exit_code == 3
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "write_scope_required"
    assert "health_metrics_and_measurements.writeonly" in data["error"]["details"]["suggested_scope"]


def test_data_points_create_requires_yes_in_json_mode(tmp_path, mock_keyring) -> None:
    _setup_auth(
        mock_keyring,
        scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    )
    body_file = tmp_path / "weight.json"
    body_file.write_text(json.dumps({"weight": {"kg": 72}}), encoding="utf-8")

    result = runner.invoke(
        app, ["--format", "json", "data-points", "create", "weight", "--body", str(body_file)]
    )

    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "confirmation_required"


def test_data_points_create_requires_yes_in_noninteractive_mode(tmp_path, mock_keyring, monkeypatch) -> None:
    _setup_auth(
        mock_keyring,
        scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    )
    monkeypatch.setenv("GHEALTH_NONINTERACTIVE", "1")
    body_file = tmp_path / "weight.json"
    body_file.write_text(json.dumps({"weight": {"kg": 72}}), encoding="utf-8")

    result = runner.invoke(app, ["data-points", "create", "weight", "--body", str(body_file)])

    assert result.exit_code == 2
    assert "requires explicit confirmation" in result.stdout


def test_data_points_update_derives_data_type_from_full_name(tmp_path, mock_keyring, monkeypatch) -> None:
    _setup_auth(
        mock_keyring,
        scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    )
    body_file = tmp_path / "weight.json"
    body_file.write_text(json.dumps({"weight": {"kg": 73}}), encoding="utf-8")
    captured = {"path": "", "mask": "", "body": b""}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["mask"] = request.url.params.get("updateMask", "")
        captured["body"] = request.read()
        return httpx.Response(200, json={"name": "operations/update-1"})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "update",
            "users/me/dataTypes/weight/dataPoints/point-1",
            "--body",
            str(body_file),
            "--update-mask",
            "weight.kg",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert captured["path"] == "/v4/users/me/dataTypes/weight/dataPoints/point-1"
    assert captured["mask"] == "weight.kg"
    assert json.loads(captured["body"]) == {"weight": {"kg": 73}}


def test_data_points_update_short_name_requires_data_type(tmp_path, mock_keyring) -> None:
    _setup_auth(
        mock_keyring,
        scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    )
    body_file = tmp_path / "weight.json"
    body_file.write_text(json.dumps({"weight": {"kg": 73}}), encoding="utf-8")

    result = runner.invoke(
        app,
        ["--format", "json", "data-points", "update", "point-1", "--body", str(body_file), "--yes"],
    )

    assert result.exit_code == 2
    data = json.loads(result.stdout)
    assert data["error"]["code"] == "data_type_required"


def test_data_points_batch_delete_reads_names_file(tmp_path, mock_keyring, monkeypatch) -> None:
    _setup_auth(
        mock_keyring,
        scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.writeonly",
    )
    names_file = tmp_path / "names.txt"
    names_file.write_text("users/me/dataTypes/weight/dataPoints/point-1\n", encoding="utf-8")
    captured_body: bytes = b""

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = request.read()
        return httpx.Response(200, json={"name": "operations/delete-1"})

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "batch-delete",
            "weight",
            "--names-file",
            str(names_file),
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert json.loads(captured_body) == {"names": ["users/me/dataTypes/weight/dataPoints/point-1"]}


def test_data_points_export_exercise_tcx_writes_output(tmp_path, mock_keyring, monkeypatch) -> None:
    _setup_auth(
        mock_keyring,
        scope=(
            "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly "
            "https://www.googleapis.com/auth/googlehealth.location.readonly"
        ),
    )
    output = tmp_path / "exercise.tcx"
    captured_params: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_params.update(dict(request.url.params))
        return httpx.Response(200, text="<TrainingCenterDatabase />")

    _patch_api_client(monkeypatch, httpx.MockTransport(handler))
    result = runner.invoke(
        app,
        [
            "--format",
            "json",
            "data-points",
            "export-exercise-tcx",
            "exercise-1",
            "--partial-data",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0
    assert captured_params == {"alt": "media", "partialData": "true"}
    assert output.read_text(encoding="utf-8") == "<TrainingCenterDatabase />"
    data = json.loads(result.stdout)
    assert data["exported"] is True
