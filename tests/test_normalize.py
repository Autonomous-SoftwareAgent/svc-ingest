from datetime import date

import pytest

from ingest import normalize
from ingest.contract import ErrorCode, IngestError, Limits, MessageKind
from tests.conftest import LIMITS, body, sample

parse = normalize.get("inventory-rates-json")


def _el(doc):
    return doc["room"][0]["date"][0]


def test_registered_and_discoverable():
    assert "inventory-rates-json" in normalize.names()


def test_full_example_splits_into_three_kinds():
    sub = parse(body(sample()), LIMITS)
    assert sub.hotel_code == "HTL001" and sub.row_errors == []
    kinds = [u.kind for u in sub.updates]
    assert kinds == [MessageKind.INVENTORY, MessageKind.RESTRICTIONS, MessageKind.RATES]
    inv, res, rat = sub.updates
    assert (inv.date_from, inv.date_to) == (date(2026, 11, 14), date(2026, 11, 16))  # cả hai đầu
    assert inv.room_code == "DLX" and inv.rate_plan_code is None and inv.data == {"rooms_to_sell": 2}
    assert res.rate_plan_code == "BAR"
    assert res.data == {
        "closed": False, "closed_on_arrival": False, "closed_on_departure": False, "min_stay": 1, "max_stay": 14,
    }
    assert rat.data == {
        "prices": [{"guests": 1, "amount": "2150000"}, {"guests": 2, "amount": "2150000"}],
        "price_basis": "after_tax",
        "age_code": "ADULT",
        "extra_adult": "300000",
        "extra_child": "150000",
    }
    assert "currency" not in rat.data  # dữ liệu không có tiền tệ: không tự gán


def test_single_day_uses_value():
    doc = sample()
    el = _el(doc)
    del el["from"], el["to"]
    el["value"] = "2026-11-20"
    inv = parse(body(doc), LIMITS).updates[0]
    assert (inv.date_from, inv.date_to) == (date(2026, 11, 20), date(2026, 11, 20))


def test_dow_cuts_range_into_continuous_segments():
    # 2026-11-14 là Thứ bảy. Thứ hai đến thứ sáu = 2..6.
    doc = sample()
    el = _el(doc)
    el.update({"from": "2026-11-14", "to": "2026-11-27", "dow": [2, 3, 4, 5, 6]})
    inv = [u for u in parse(body(doc), LIMITS).updates if u.kind is MessageKind.INVENTORY]
    assert [(u.date_from, u.date_to) for u in inv] == [
        (date(2026, 11, 16), date(2026, 11, 20)),
        (date(2026, 11, 23), date(2026, 11, 27)),
    ]


def test_dow_one_is_sunday_seven_is_saturday():
    doc = sample()
    el = _el(doc)
    el.update({"from": "2026-11-14", "to": "2026-11-22", "dow": [1, 7]})  # Chủ nhật và Thứ bảy
    inv = [u for u in parse(body(doc), LIMITS).updates if u.kind is MessageKind.INVENTORY]
    assert [(u.date_from, u.date_to) for u in inv] == [
        (date(2026, 11, 14), date(2026, 11, 15)),
        (date(2026, 11, 21), date(2026, 11, 22)),
    ]


def test_absent_fields_are_skipped_not_zero():
    doc = sample()
    el = _el(doc)
    for k in ("roomstosell", "closed", "closedonarrival", "closedondeparture", "minimumstay", "maximumstay"):
        del el[k]
    sub = parse(body(doc), LIMITS)
    assert [u.kind for u in sub.updates] == [MessageKind.RATES]  # không có tồn, không có điều kiện bán


def test_zero_rooms_is_a_real_value():
    doc = sample()
    _el(doc)["roomstosell"] = 0
    inv = parse(body(doc), LIMITS).updates[0]
    assert inv.data == {"rooms_to_sell": 0}


@pytest.mark.parametrize("raw,expected", [("0", False), ("1", True), ("Y", True), ("false", True)])
def test_closed_flag_zero_is_open_anything_else_closed(raw, expected):
    doc = sample()
    _el(doc)["closed"] = raw
    res = [u for u in parse(body(doc), LIMITS).updates if u.kind is MessageKind.RESTRICTIONS][0]
    assert res.data["closed"] is expected


def test_empty_flag_is_skipped():
    doc = sample()
    _el(doc)["closed"] = ""
    res = [u for u in parse(body(doc), LIMITS).updates if u.kind is MessageKind.RESTRICTIONS][0]
    assert "closed" not in res.data


def test_two_rate_plans_one_inventory_two_each_of_others():
    doc = sample()
    _el(doc)["rate"] = [{"rateplanid": "BAR"}, {"rateplanid": "NR"}]
    kinds = [u.kind for u in parse(body(doc), LIMITS).updates]
    assert kinds.count(MessageKind.INVENTORY) == 1
    assert kinds.count(MessageKind.RESTRICTIONS) == 2 and kinds.count(MessageKind.RATES) == 2


def test_decimal_amounts_keep_exact_text():
    doc = sample()
    _el(doc)["price"] = [{"NumberOfGuests": 1, "value": "1234.50"}]
    rat = [u for u in parse(body(doc), LIMITS).updates if u.kind is MessageKind.RATES][0]
    assert rat.data["prices"] == [{"guests": 1, "amount": "1234.50"}]


@pytest.mark.parametrize(
    "patch",
    [
        {"from": "14/11/2026"},  # sai dạng ngày
        {"from": "2026-02-30"},  # không phải ngày thật
        {"from": "2026-11-17"},  # to nhỏ hơn from
        {"to": "2030-01-01"},  # dài quá giới hạn
        {"dow": []},
        {"dow": [0]},
        {"dow": [8]},
        {"roomstosell": -1},
        {"roomstosell": True},
        {"price": [{"NumberOfGuests": 1, "value": 1}, {"NumberOfGuests": 1, "value": 2}]},  # lặp số khách
        {"price": [{"NumberOfGuests": 1, "value": -5}]},
        {"price": [{"NumberOfGuests": 1, "value": "NaN"}]},
        {"price": []},
        {"minimumstay": 5, "maximumstay": 2},
        {"closed": 0},  # cờ phải là chuỗi
        {"rate": []},  # có điều kiện bán và giá nhưng không có gói giá
    ],
)
def test_bad_row_is_dropped_with_error_and_others_survive(patch):
    doc = sample()
    good = {"from": "2026-12-01", "to": "2026-12-02", "roomstosell": 3}
    _el(doc).update(patch)
    doc["room"][0]["date"].append(good)
    sub = parse(body(doc), LIMITS)
    assert len(sub.row_errors) == 1 and sub.row_errors[0].code == ErrorCode.INVALID_ROW
    assert sub.row_errors[0].path == "room[0].date[0]"
    assert [(u.date_from, u.data) for u in sub.updates] == [(date(2026, 12, 1), {"rooms_to_sell": 3})]


def test_element_with_nothing_to_update_is_an_error():
    doc = sample()
    doc["room"][0]["date"] = [{"from": "2026-11-14", "to": "2026-11-16"}]
    sub = parse(body(doc), LIMITS)
    assert sub.updates == [] and sub.row_errors[0].code == ErrorCode.INVALID_ROW


def test_bad_room_entry_does_not_stop_next_room():
    doc = sample()
    doc["room"].insert(0, {"roomid": "", "date": []})
    sub = parse(body(doc), LIMITS)
    assert sub.row_errors[0].path == "room[0]" and len(sub.updates) == 3


@pytest.mark.parametrize(
    "raw",
    [b"not json", b"[]", b'{"room": [{}]}', b'{"hotelid": "", "room": [{}]}', b'{"hotelid": "H"}', b'{"hotelid": "H", "room": []}'],
)
def test_payload_errors_reject_whole_request(raw):
    with pytest.raises(IngestError) as e:
        parse(raw, LIMITS)
    assert e.value.code == ErrorCode.INVALID_PAYLOAD


def test_too_many_updates_rejects_whole_request():
    with pytest.raises(IngestError) as e:
        parse(body(sample()), Limits(max_span_days=730, max_updates=2))
    assert e.value.code == ErrorCode.TOO_MANY_UPDATES


def test_registry_rejects_duplicate_names():
    from ingest.normalize.registry import register

    with pytest.raises(RuntimeError):
        register("inventory-rates-json")(lambda b, l: None)
