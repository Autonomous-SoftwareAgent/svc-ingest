import json
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from ingest import normalize
from ingest.contract import ErrorCode, IngestError
from ingest.core import auth, catalog, schema, service
from ingest.core.cache import TtlCache
from tests.conftest import LIMITS, body, sample

TRACE = "11111111-1111-4111-8111-111111111111"


def accept(env, doc=None, trace=TRACE, channel="web", raw=None):
    raw = raw if raw is not None else body(doc if doc is not None else sample())
    sub = normalize.get("inventory-rates-json")(raw, LIMITS)
    import hashlib

    return service.accept(env.engine, env.cache, env.partner, trace, channel, hashlib.sha256(raw).hexdigest(), sub)


def count(engine, table):
    with engine.connect() as c:
        return c.execute(select(func.count()).select_from(table)).scalar_one()


def messages(engine):
    with engine.connect() as c:
        return c.execute(select(schema.outbox).order_by(schema.outbox.c.id)).all()


# --- xác thực ---------------------------------------------------------------------------------------------
def test_password_is_stored_hashed(env):
    with env.engine.connect() as c:
        stored = c.execute(select(schema.partner.c.password_hash)).scalar_one()
    assert stored.startswith("scrypt$") and "s3cret-pass" not in stored


def test_authenticate(env):
    assert auth.authenticate(env.engine, "acme-user", "s3cret-pass").id == env.partner_id
    assert auth.authenticate(env.engine, "acme-user", "sai") is None
    assert auth.authenticate(env.engine, "khong-co", "s3cret-pass") is None


def test_inactive_partner_cannot_authenticate(env):
    with env.engine.begin() as c:
        c.execute(schema.partner.update().values(active=False))
    assert auth.authenticate(env.engine, "acme-user", "s3cret-pass") is None


def test_register_partner_validations(env):
    with pytest.raises(IngestError) as e:
        catalog.register_partner(env.engine, "acme", "u2", "s3cret-pass", "inventory-rates-json")  # trùng tên
    assert e.value.code == ErrorCode.CONFLICT
    with pytest.raises(IngestError) as e:
        catalog.register_partner(env.engine, "x", "y", "ngan", "inventory-rates-json")
    assert e.value.code == ErrorCode.BAD_ARGUMENT


# --- nhận lần gửi -----------------------------------------------------------------------------------------
def test_accept_writes_submission_and_outbox_before_ack(env):
    ack = accept(env)
    assert ack.duplicate is False and ack.row_errors == [] and uuid.UUID(ack.ticket_id)
    assert count(env.engine, schema.submission) == 1
    rows = messages(env.engine)
    assert [r.kind for r in rows] == ["inventory", "restrictions", "rates"]
    assert all(r.sent_at_us is None for r in rows)  # chưa phát, nhưng đã nằm bền trong outbox


def test_message_shape_keys_and_internal_ids(env):
    accept(env, channel="kenh-a")
    inv, res, rat = messages(env.engine)
    assert inv.key == "h-1:r-dlx" and res.key == rat.key == "h-1:r-dlx:p-bar"
    p = json.loads(res.payload)
    assert p["hotelId"] == "h-1" and p["roomId"] == "r-dlx" and p["ratePlanId"] == "p-bar"
    assert (p["dateFrom"], p["dateTo"], p["channelId"], p["kind"]) == ("2026-11-14", "2026-11-16", "kenh-a", "restrictions")
    assert json.loads(inv.payload)["ratePlanId"] is None
    assert p["receivedAt"].endswith("+00:00")


def test_message_ids_are_stable_uuid5_of_ticket_and_position(env):
    ack = accept(env)
    ids = [r.message_id for r in messages(env.engine)]
    assert ids == [str(uuid.uuid5(uuid.UUID(ack.ticket_id), str(i))) for i in range(3)]


def test_same_trace_and_body_returns_same_ticket_without_new_messages(env):
    first = accept(env)
    again = accept(env)
    assert again.ticket_id == first.ticket_id and again.duplicate is True
    assert count(env.engine, schema.outbox) == 3 and count(env.engine, schema.submission) == 1


def test_duplicate_returns_same_row_errors(env):
    doc = sample()
    doc["room"].append({"roomid": "LẠ", "date": [{"value": "2026-11-20", "roomstosell": 1}]})
    first = accept(env, doc)
    again = accept(env, doc)
    assert again.row_errors == first.row_errors and first.row_errors[0].code == ErrorCode.UNKNOWN_CODE


def test_same_trace_different_body_is_conflict(env):
    accept(env)
    other = sample()
    other["room"][0]["date"][0]["roomstosell"] = 9
    with pytest.raises(IngestError) as e:
        accept(env, other)
    assert e.value.code == ErrorCode.IDEMPOTENCY_CONFLICT
    assert count(env.engine, schema.outbox) == 3


def test_same_trace_for_different_partners_is_independent(env):
    accept(env)
    pid2 = catalog.register_partner(env.engine, "beta", "beta-user", "another-secret", "inventory-rates-json")
    catalog.set_hotel(env.engine, env.cache, pid2, "HTL001", "h-9", None)
    catalog.set_room(env.engine, env.cache, pid2, "HTL001", "DLX", "r-9", None)
    catalog.set_rate_plan(env.engine, env.cache, pid2, "HTL001", "BAR", "p-9", None)
    from ingest.contract import PartnerInfo

    other = PartnerInfo(pid2, "beta", "inventory-rates-json")
    sub = normalize.get("inventory-rates-json")(body(sample()), LIMITS)
    ack = service.accept(env.engine, env.cache, other, TRACE, None, "h", sub)
    assert ack.duplicate is False


def test_unknown_room_is_dropped_others_go_with_code_10(env):
    doc = sample()
    doc["room"].append({"roomid": "LẠ", "date": [{"value": "2026-11-20", "roomstosell": 1}]})
    ack = accept(env, doc)
    assert [e.code for e in ack.row_errors] == [ErrorCode.UNKNOWN_CODE]
    assert count(env.engine, schema.outbox) == 3  # phần hợp lệ vẫn đi


def test_unknown_rate_plan_drops_restrictions_and_rates_but_keeps_inventory(env):
    doc = sample()
    doc["room"][0]["date"][0]["rate"] = [{"rateplanid": "LẠ"}]
    ack = accept(env, doc)
    assert [r.kind for r in messages(env.engine)] == ["inventory"]
    assert [e.code for e in ack.row_errors] == [ErrorCode.UNKNOWN_CODE]


def test_unknown_code_reported_once_even_if_used_many_times(env):
    doc = sample()
    doc["room"][0]["roomid"] = "LẠ"
    doc["room"][0]["date"].append({"value": "2026-12-01", "roomstosell": 1})
    with pytest.raises(IngestError) as e:
        accept(env, doc)
    assert e.value.code == ErrorCode.NO_VALID_DATA
    assert [x.code for x in e.value.errors].count(ErrorCode.UNKNOWN_CODE) == 1


def test_everything_invalid_rejects_and_stores_nothing_so_trace_can_be_reused(env):
    bad = sample()
    bad["room"][0]["roomid"] = "LẠ"
    with pytest.raises(IngestError) as e:
        accept(env, bad)
    assert e.value.code == ErrorCode.NO_VALID_DATA
    assert count(env.engine, schema.submission) == 0 and count(env.engine, schema.outbox) == 0
    assert accept(env).duplicate is False  # cùng X-Trace-Id, nội dung đã sửa: được nhận


def test_hotel_not_allowed(env):
    doc = sample()
    doc["hotelid"] = "KHAC"
    with pytest.raises(IngestError) as e:
        accept(env, doc)
    assert e.value.code == ErrorCode.HOTEL_NOT_ALLOWED


def test_save_failure_raises_and_never_acks(env, monkeypatch):
    def boom(*a, **k):
        raise OperationalError("insert", {}, Exception("db sập"))

    monkeypatch.setattr(env.engine, "begin", boom)
    with pytest.raises(IngestError) as e:
        accept(env)
    assert e.value.code == ErrorCode.SAVE_FAILED


def test_outbox_and_submission_commit_together(env, monkeypatch):
    """Nếu ghi outbox lỗi thì không được còn lại submission (không ACK, không nửa vời)."""
    from sqlalchemy.engine import Connection

    orig_exec = Connection.execute

    def exec_(self, stmt, *a, **k):
        if getattr(stmt, "table", None) is schema.outbox:
            raise OperationalError("insert", {}, Exception("hết đĩa"))
        return orig_exec(self, stmt, *a, **k)

    monkeypatch.setattr(Connection, "execute", exec_)
    with pytest.raises(IngestError):
        accept(env)
    monkeypatch.undo()
    assert count(env.engine, schema.submission) == 0


# --- danh mục và cache ------------------------------------------------------------------------------------
def test_catalog_upserts_and_lookup(env):
    catalog.set_room(env.engine, env.cache, env.partner_id, "HTL001", "DLX", "r-moi", "Deluxe")
    cat = catalog.get_catalog(env.engine, env.partner_id)
    h = cat["hotels"][0]
    assert h["code"] == "HTL001" and h["id"] == "h-1"
    assert {r["code"]: r["id"] for r in h["rooms"]} == {"DLX": "r-moi", "STD": "r-std"}
    assert {p["code"] for p in h["ratePlans"]} == {"BAR", "NR"}


def test_catalog_not_found_errors(env):
    with pytest.raises(IngestError) as e:
        catalog.set_room(env.engine, env.cache, env.partner_id, "KHONG", "X", "y", None)
    assert e.value.code == ErrorCode.NOT_FOUND
    with pytest.raises(IngestError) as e:
        catalog.get_catalog(env.engine, 999)
    assert e.value.code == ErrorCode.NOT_FOUND


def test_catalog_change_is_visible_immediately_in_this_process(env):
    doc = sample()
    doc["room"][0]["roomid"] = "MOI"
    with pytest.raises(IngestError):
        accept(env, doc, trace="22222222-2222-4222-8222-222222222222")
    catalog.set_room(env.engine, env.cache, env.partner_id, "HTL001", "MOI", "r-moi", None)
    assert accept(env, doc, trace="33333333-3333-4333-8333-333333333333").duplicate is False


def test_cache_serves_stale_catalog_until_ttl_when_changed_elsewhere(env):
    """Cache 24 giờ: sửa danh mục ở tiến trình khác thì tiến trình này chỉ thấy sau khi hết hạn."""
    t = {"now": 0.0}
    env.cache = TtlCache(100, clock=lambda: t["now"])
    accept(env, trace="44444444-4444-4444-8444-444444444444")  # nạp cache
    with env.engine.begin() as c:  # "tiến trình khác" xóa phòng DLX khỏi danh mục
        c.execute(schema.room_map.delete().where(schema.room_map.c.room_code == "DLX"))
    assert accept(env, trace="55555555-5555-4555-8555-555555555555").row_errors == []  # vẫn dùng bản cache
    t["now"] = 101.0
    with pytest.raises(IngestError):
        accept(env, trace="66666666-6666-4666-8666-666666666666")  # hết hạn: đọc lại, thấy mất phòng


def test_ttl_cache_basics():
    t = {"now": 0.0}
    c = TtlCache(10, clock=lambda: t["now"])
    c.set((1, "a"), "x")
    c.set((2, "a"), "y")
    assert c.get((1, "a")) == "x"
    c.invalidate_partner(1)
    assert c.get((1, "a")) is None and c.get((2, "a")) == "y"
    t["now"] = 10
    assert c.get((2, "a")) is None
