"""Tests for the backend skeleton: health, session create, spec read."""

import json
import re

import pytest
from fastapi.testclient import TestClient

from server.main import create_app


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path))


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_session_returns_id_and_empty_draft(client):
    r = client.post("/session")
    assert r.status_code == 201
    body = r.json()
    assert re.fullmatch(r"s_\d{8}_[0-9a-f]{6}", body["id"])
    spec = body["spec"]
    assert spec["id"] == body["id"]
    assert spec["segments"] == []
    assert spec["status"] == "draft"
    assert spec["approved_by"] is None
    assert spec["approved_at"] is None


def test_two_sessions_have_different_ids(client):
    a = client.post("/session").json()["id"]
    b = client.post("/session").json()["id"]
    assert a != b


def test_get_spec_returns_the_stored_spec(client):
    sid = client.post("/session").json()["id"]
    r = client.get(f"/session/{sid}/spec")
    assert r.status_code == 200
    assert r.json()["spec"]["id"] == sid
    assert r.json()["spec"]["title"] == "Shaft"


def test_get_spec_unknown_session_is_404(client):
    r = client.get("/session/s_20261123_ffffff/spec")
    assert r.status_code == 404


def test_bad_session_id_is_rejected(client):
    # Ids become file names. Anything that does not look like an id is refused.
    r = client.get("/session/..%5C..%5Csecret/spec")
    assert r.status_code in (404, 422)


def test_session_is_saved_as_json_file(client, tmp_path):
    sid = client.post("/session").json()["id"]
    path = tmp_path / "sessions" / f"{sid}.json"
    assert path.exists()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["spec"]["id"] == sid
    assert saved["history"] == []


def test_session_survives_a_restart(tmp_path):
    sid = TestClient(create_app(data_dir=tmp_path)).post("/session").json()["id"]
    fresh = TestClient(create_app(data_dir=tmp_path))
    assert fresh.get(f"/session/{sid}/spec").status_code == 200


def test_cors_preflight_is_answered(client):
    # The glasses WebView sends a preflight for JSON POSTs (docs/sdk-notes.md, section 5).
    r = client.options(
        "/session",
        headers={
            "Origin": "http://example.test",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "*"
