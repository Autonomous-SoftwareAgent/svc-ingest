import base64
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from ingest.config import Settings
from ingest.core import schema
from ingest.io.http import create_app
from ingest.main import build_hooks
from tests.conftest import body, sample

TRACE = "11111111-1111-4111-8111-111111111111"


def basic(user="acme-user", pw="s3cret-pass"):
    return "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


@pytest.fixture
def client(env):
    settings = Settings(database_url="sqlite://", publisher="log", internal_token="tok-noi-bo", max_body_bytes=4000)
    return TestClient(create_app(build_hooks(settings, env.engine, env.cache)))


def post(client, doc=None, *, auth=None, trace=TRACE, channel="web", raw=None):
    headers = {"Authorization": auth if auth is not None else basic()}
    if trace is not None:
        headers["X-Trace-Id"] = trace
    if channel:
        headers["X-Channel-Id"] = channel
    content = raw if raw is not None else body(doc if doc is not None else sample())
    return client.post("/v1/inventory-rates", content=content, headers=headers)


def outbox_count(engine):
    with engine.connect() as c:
        return c.execute(select(func.count()).select_from(schema.outbox)).scalar_one()


# --- xác thực ---------------------------------------------------------------------------------------------
@pytest.mark.parametrize("auth", ["", "Bearer abc", "Basic !!!", "Basic " + base64.b64encode(b"khong-co-dau-hai-cham").decode()])
def test_missing_or_malformed_basic_is_401(client, auth):
    r = client.post("/v1/inventory-rates", content=b"{}", headers={"Authorization": auth, "X-Trace-Id": TRACE})
    assert r.status_code == 401 and r.json()["status"] == "Fail" and r.headers["www-authenticate"] == "Basic"


@pytest.mark.parametrize("user,pw", [("acme-user", "sai"), ("khong-co", "s3cret-pass")])
def test_wrong_credentials_same_401(client, user, pw):
    r = post(client, auth=basic(user, pw))
    assert r.status_code == 401 and r.json()["errors"][0]["code"] == 30


def test_auth_is_checked_before_body_is_parsed(client):
    r = post(client, auth=basic("khong-co", "x"), raw=b"khong phai json")
    assert r.status_code == 401


# --- header, nội dung -------------------------------------------------------------------------------------
@pytest.mark.parametrize("trace", [None, "", "khong-phai-uuid", "1234"])
def test_trace_id_required_and_must_be_uuid(client, trace):
    r = post(client, trace=trace)
    assert r.status_code == 400 and r.json()["errors"][0]["code"] == 22


def test_unparseable_body_is_400(client):
    r = post(client, raw=b"not json")
    assert r.status_code == 400 and r.json() == {"status": "Fail", "errors": [{"code": 21, "shortText": "nội dung không phải JSON hợp lệ"}]}


def test_body_too_large_is_413(client):
    r = post(client, raw=b"x" * 5000)
    assert r.status_code == 413 and r.json()["errors"][0]["code"] == 23


# --- ACK --------------------------------------------------------------------------------------------------
def test_success_returns_202_with_ticket_after_data_is_stored(client, env):
    r = post(client)
    j = r.json()
    assert r.status_code == 202 and j["status"] == "Success" and j["errors"] == []
    assert j["data"]["duplicate"] is False and j["data"]["ticketId"]
    assert outbox_count(env.engine) == 3  # ACK chỉ có khi đã lưu


def test_resend_same_key_and_body_returns_same_ticket(client, env):
    first = post(client).json()["data"]["ticketId"]
    r = post(client)
    assert r.status_code == 202 and r.json()["data"] == {"ticketId": first, "duplicate": True}
    assert outbox_count(env.engine) == 3


def test_same_key_different_body_is_409(client):
    post(client)
    other = sample()
    other["room"][0]["date"][0]["roomstosell"] = 1
    r = post(client, other)
    assert r.status_code == 409 and r.json()["errors"][0]["code"] == 40


def test_unknown_room_row_dropped_with_code_10_rest_goes(client, env):
    doc = sample()
    doc["room"].append({"roomid": "LẠ", "date": [{"value": "2026-11-20", "roomstosell": 1}]})
    r = post(client, doc)
    assert r.status_code == 202
    assert [e["code"] for e in r.json()["errors"]] == [10]
    assert outbox_count(env.engine) == 3


def test_all_rows_invalid_rejects_whole_request(client, env):
    doc = sample()
    doc["room"][0]["roomid"] = "LẠ"
    r = post(client, doc)
    assert r.status_code == 400 and r.json()["status"] == "Fail"
    assert [e["code"] for e in r.json()["errors"]] == [12, 10]
    assert outbox_count(env.engine) == 0


def test_hotel_not_allowed_is_401(client):
    doc = sample()
    doc["hotelid"] = "KHAC"
    r = post(client, doc)
    assert r.status_code == 401 and r.json()["errors"][0]["code"] == 31


def test_database_failure_is_never_acked(client, env, monkeypatch):
    def boom(*a, **k):
        raise OperationalError("insert", {}, Exception("db sập"))

    monkeypatch.setattr(env.engine, "begin", boom)
    r = post(client)
    assert r.status_code == 503 and r.json()["status"] == "Fail" and r.json()["errors"][0]["code"] == 50


def test_response_and_logs_do_not_echo_credentials(client, caplog):
    with caplog.at_level("INFO"):
        r = post(client)
    assert "s3cret-pass" not in r.text and "s3cret-pass" not in caplog.text and "acme-user" not in caplog.text


# --- API nội bộ -------------------------------------------------------------------------------------------
def internal(client, method, path, token="tok-noi-bo", **kw):
    headers = {"Authorization": f"Bearer {token}"} if token is not None else {}
    return client.request(method, "/internal/v1" + path, headers=headers, **kw)


@pytest.mark.parametrize("token", [None, "sai"])
def test_internal_api_requires_token(client, token):
    assert internal(client, "GET", "/partners", token=token).status_code == 401


def test_internal_api_denied_by_default_when_token_not_configured(env):
    settings = Settings(database_url="sqlite://", publisher="log")  # không đặt internal_token
    c = TestClient(create_app(build_hooks(settings, env.engine, env.cache)))
    assert c.get("/internal/v1/partners", headers={"Authorization": "Bearer "}).status_code == 401
    assert c.get("/internal/v1/partners", headers={"Authorization": "Bearer tok-noi-bo"}).status_code == 401


def test_internal_partner_and_catalog_flow(client):
    r = internal(client, "POST", "/partners", json={"name": "beta", "username": "beta-user", "password": "mat-khau-dai", "format": "inventory-rates-json"})
    assert r.status_code == 201
    pid = r.json()["data"]["id"]
    assert internal(client, "PUT", f"/partners/{pid}/hotels/H9", json={"hotelId": "h-9", "name": "H9"}).status_code == 200
    assert internal(client, "PUT", f"/partners/{pid}/hotels/H9/rooms/R1", json={"roomId": "r-1"}).status_code == 200
    assert internal(client, "PUT", f"/partners/{pid}/hotels/H9/rate-plans/P1", json={"ratePlanId": "p-1"}).status_code == 200
    cat = internal(client, "GET", f"/partners/{pid}/catalog").json()["data"]
    assert cat["hotels"][0]["rooms"] == [{"code": "R1", "id": "r-1", "name": None}]
    assert {p["username"] for p in internal(client, "GET", "/partners").json()["data"]} == {"acme-user", "beta-user"}
    # đối tác mới đăng ký xong gửi được ngay
    doc = {"hotelid": "H9", "room": [{"roomid": "R1", "date": [{"value": "2026-12-01", "roomstosell": 1}]}]}
    r = client.post("/v1/inventory-rates", content=body(doc), headers={"Authorization": basic("beta-user", "mat-khau-dai"), "X-Trace-Id": TRACE})
    assert r.status_code == 202


def test_internal_validation_and_errors(client):
    assert internal(client, "POST", "/partners", json={"name": "x"}).status_code == 400
    assert internal(client, "POST", "/partners", json={"name": "x", "username": "y", "password": "mat-khau-dai", "format": "khong-co"}).status_code == 400
    assert internal(client, "POST", "/partners", json={"name": "acme", "username": "u", "password": "mat-khau-dai"}).status_code == 409
    assert internal(client, "PUT", "/partners/999/hotels/H", json={"hotelId": "h"}).status_code == 404
    assert internal(client, "GET", "/partners/999/catalog").status_code == 404
    assert internal(client, "PUT", "/partners/1/hotels/H", json={"hotelId": "h", "la": 1}).status_code == 400


def test_healthz_reports_database_and_pending(client):
    post(client)
    r = client.get("/healthz")
    assert r.status_code == 200 and r.json()["data"] == {"database": "ok", "outboxPending": 3}


def test_healthz_503_when_database_down(client, env, monkeypatch):
    monkeypatch.setattr(env.engine, "connect", lambda: (_ for _ in ()).throw(OperationalError("x", {}, Exception("sập"))))
    assert client.get("/healthz").status_code == 503
