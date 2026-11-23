"""Session token: the session id alone is not enough to read or change a session."""

import pytest
from fastapi.testclient import TestClient

from server.core.ops import InterpreterResult
from server.main import create_app


class Fake:
    def interpret(self, spec, utterance):
        return InterpreterResult.model_validate({"ops": [{"op": "finish"}], "ask": None})


@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(data_dir=tmp_path, interpreter=Fake(), drive=None))


@pytest.fixture
def made(client):
    st = client.post("/session").json()
    return st["id"], st["token"]


def test_create_gives_a_token_once(client, made):
    sid, token = made
    assert len(token) >= 20
    st = client.get(f"/session/{sid}/spec", headers={"X-Session-Token": token}).json()
    assert "token" not in st and st["id"] == sid


@pytest.mark.parametrize("method, path, body", [
    ("get", "/session/{sid}/spec", None),
    ("post", "/session/{sid}/utterance", {"text": "30"}),
    ("post", "/session/{sid}/undo", None),
    ("post", "/session/{sid}/finish", None),
    ("get", "/session/{sid}/render", None),
    ("get", "/session/{sid}/files/pdf", None),
    ("post", "/session/{sid}/approve", {"name": "Kis Anna"}),
    ("post", "/session/{sid}/audio", None),
    ("get", "/s/{sid}", None),
])
def test_every_session_route_needs_the_token(client, made, method, path, body):
    sid, token = made
    url = path.format(sid=sid)
    kwargs = {"json": body} if body else {}
    assert getattr(client, method)(url, **kwargs).status_code == 401
    assert getattr(client, method)(url, headers={"X-Session-Token": "wrong"}, **kwargs).status_code == 401
    assert getattr(client, method)(url, params={"k": token[:-1]}, **kwargs).status_code == 401
    assert getattr(client, method)(url, headers={"X-Session-Token": token}, **kwargs).status_code != 401


def test_one_token_does_not_open_another_session(client, made):
    sid, token = made
    other = client.post("/session").json()
    assert client.get(f"/session/{other['id']}/spec", headers={"X-Session-Token": token}).status_code == 401


def test_unknown_session_is_404_and_health_is_open(client):
    assert client.get("/session/s_20261123_ffffff/spec").status_code == 404
    assert client.get("/health").status_code == 200


def test_links_carry_the_token_so_the_phone_page_works(client, made):
    sid, token = made
    h = {"X-Session-Token": token}
    for text in ("30", "40"):
        client.post(f"/session/{sid}/utterance", json={"text": text}, headers=h)
    st = client.post(f"/session/{sid}/finish", headers=h).json()
    assert st["finished"] and st["phone_page"] == f"/s/{sid}?k={token}"
    page = client.get(st["phone_page"])  # no header: the link alone must work on the phone
    assert page.status_code == 200
    assert f'src="/session/{sid}/render?k={token}"' in page.text and "X-Session-Token" in page.text
    for url in st["files"].values():
        assert client.get(url).status_code == 200


def test_cors_preflight_allows_the_token_header(client, made):
    sid, _ = made
    r = client.options(f"/session/{sid}/undo", headers={
        "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-session-token",
    })
    assert r.status_code == 200 and "x-session-token" in r.headers["access-control-allow-headers"].lower()


def test_a_refused_call_still_has_cors_headers(client, made):
    sid, _ = made
    r = client.get(f"/session/{sid}/spec", headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 401 and r.headers.get("access-control-allow-origin") == "*"
