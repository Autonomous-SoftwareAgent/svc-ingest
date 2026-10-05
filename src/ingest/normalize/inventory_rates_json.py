"""Định dạng JSON `inventory-rates-json` (InvResRateRequest) do nhà cung cấp khách sạn gửi.

    {"hotelid": "H1", "room": [{"roomid": "DLX", "date": [{
        "from": "2026-11-14", "to": "2026-11-16",          # hoặc "value": "2026-11-14" cho một ngày
        "rate": [{"rateplanid": "BAR"}],
        "roomstosell": 2,
        "price": [{"NumberOfGuests": 1, "value": 2150000}], "extraadultrate": 300000, "extrachildrate": 150000,
        "closed": "0", "closedonarrival": "0", "closedondeparture": "0",
        "minimumstay": 1, "maximumstay": 14, "dow": [1,2,3,4,5,6,7]}]}]}

Quy ước (theo mô tả của người dùng, chưa kiểm với nhà cung cấp thật):
- Trường không gửi (hoặc null) thì bỏ qua, KHÔNG hiểu là 0.
- Cờ đóng: chuỗi "0" là mở, giá trị khác là đóng, chuỗi rỗng thì bỏ qua.
- dow: 1 = Chủ nhật, 2 = Thứ hai ... 7 = Thứ bảy. Không đủ 7 ngày thì khoảng ngày bị cắt thành các đoạn liên tục.
- Ngày là yyyy-MM-dd; from và to tính cả hai đầu (giả định, chưa được người dùng xác nhận).
- Giá là giá đã gồm thuế, mã tuổi ADULT. Dữ liệu không có tiền tệ: ở đây KHÔNG gán tiền tệ.
- Một phần tử date tách thành tối đa ba loại update: tồn (mỗi phòng một lần), điều kiện bán và giá (mỗi gói giá).
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from ingest.contract import (
    ErrorCode,
    IngestError,
    Limits,
    MessageKind,
    NormalizedSubmission,
    RowError,
    Update,
)
from ingest.normalize.registry import register

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class _Row(Exception):
    """Một dòng sai cấu trúc: bỏ dòng, đi tiếp."""


def _str(v: Any, what: str) -> str:
    if not isinstance(v, str) or not v.strip():
        raise _Row(f"{what} phải là chuỗi không rỗng")
    return v.strip()


def _int(v: Any, what: str, minimum: int) -> int:
    if isinstance(v, bool) or not isinstance(v, int) or v < minimum:
        raise _Row(f"{what} phải là số nguyên >= {minimum}")
    return v


def _money(v: Any, what: str) -> Decimal:
    if isinstance(v, bool) or not isinstance(v, (int, float, str)):
        raise _Row(f"{what} phải là số")
    try:
        d = Decimal(str(v))
    except InvalidOperation:
        raise _Row(f"{what} không phải số") from None
    if not d.is_finite() or d < 0:
        raise _Row(f"{what} phải là số >= 0")
    return d


def _day(s: Any, what: str) -> date:
    if not isinstance(s, str) or not _DATE.match(s):
        raise _Row(f"{what} phải có dạng yyyy-MM-dd")
    try:
        return date.fromisoformat(s)
    except ValueError:
        raise _Row(f"{what} không phải ngày hợp lệ") from None


def _dow_code(d: date) -> int:
    return d.isoweekday() % 7 + 1  # Chủ nhật = 1 ... Thứ bảy = 7


def _segments(start: date, end: date, dow: Any) -> list[tuple[date, date]]:
    if dow is None:
        return [(start, end)]
    if (
        not isinstance(dow, list)
        or not dow
        or any(isinstance(x, bool) or not isinstance(x, int) or not 1 <= x <= 7 for x in dow)
    ):
        raise _Row("dow phải là danh sách không rỗng các số từ 1 đến 7")
    wanted = set(dow)
    if len(wanted) == 7:
        return [(start, end)]
    out: list[tuple[date, date]] = []
    run_start: date | None = None
    d = start
    while d <= end:
        if _dow_code(d) in wanted:
            if run_start is None:
                run_start = d
        elif run_start is not None:
            out.append((run_start, d - timedelta(days=1)))
            run_start = None
        d += timedelta(days=1)
    if run_start is not None:
        out.append((run_start, end))
    return out


def _flag(el: dict, key: str) -> bool | None:
    v = el.get(key)
    if v is None:
        return None
    if not isinstance(v, str):
        raise _Row(f"{key} phải là chuỗi")
    if not v.strip():
        return None
    return v.strip() != "0"  # "0" là mở, khác "0" là đóng


def _restrictions(el: dict) -> dict[str, Any]:
    data: dict[str, Any] = {}
    for src, dst in (
        ("closed", "closed"),
        ("closedonarrival", "closed_on_arrival"),
        ("closedondeparture", "closed_on_departure"),
    ):
        v = _flag(el, src)
        if v is not None:
            data[dst] = v
    for src, dst in (("minimumstay", "min_stay"), ("maximumstay", "max_stay")):
        if el.get(src) is not None:
            data[dst] = _int(el[src], src, 1)
    if "min_stay" in data and "max_stay" in data and data["max_stay"] < data["min_stay"]:
        raise _Row("maximumstay nhỏ hơn minimumstay")
    return data


def _rates(el: dict) -> dict[str, Any]:
    data: dict[str, Any] = {}
    prices = el.get("price")
    if prices is not None:
        if not isinstance(prices, list) or not prices:
            raise _Row("price phải là danh sách không rỗng")
        seen: set[int] = set()
        out = []
        for p in prices:
            if not isinstance(p, dict):
                raise _Row("phần tử price phải là object")
            guests = _int(p.get("NumberOfGuests"), "NumberOfGuests", 1)
            if guests in seen:
                raise _Row(f"NumberOfGuests {guests} bị lặp")
            seen.add(guests)
            out.append({"guests": guests, "amount": str(_money(p.get("value"), "value"))})
        data["prices"] = out
        data["price_basis"] = "after_tax"
        data["age_code"] = "ADULT"
    for src, dst in (("extraadultrate", "extra_adult"), ("extrachildrate", "extra_child")):
        if el.get(src) is not None:
            data[dst] = str(_money(el[src], src))
    return data


def _rate_codes(el: dict) -> list[str]:
    rate = el.get("rate")
    if rate is None:
        return []
    if not isinstance(rate, list):
        raise _Row("rate phải là danh sách")
    codes: list[str] = []
    for r in rate:
        code = _str(r.get("rateplanid") if isinstance(r, dict) else None, "rateplanid")
        if code not in codes:
            codes.append(code)
    return codes


def _date_element(room_code: str, el: Any, limits: Limits) -> list[Update]:
    if not isinstance(el, dict):
        raise _Row("phần tử date phải là object")
    if el.get("value") is not None:
        start = end = _day(el["value"], "value")
    else:
        start, end = _day(el.get("from"), "from"), _day(el.get("to"), "to")
    if end < start:
        raise _Row("to nhỏ hơn from")
    if (end - start).days + 1 > limits.max_span_days:
        raise _Row(f"khoảng ngày dài hơn {limits.max_span_days} ngày")
    segments = _segments(start, end, el.get("dow"))
    codes = _rate_codes(el)
    rooms = _int(el["roomstosell"], "roomstosell", 0) if el.get("roomstosell") is not None else None
    restrictions = _restrictions(el)
    rates = _rates(el)
    if rooms is None and not restrictions and not rates:
        raise _Row("không có dữ liệu nào để cập nhật")
    if (restrictions or rates) and not codes:
        raise _Row("điều kiện bán và giá cần rateplanid")
    out: list[Update] = []
    for s, e in segments:
        if rooms is not None:
            out.append(Update(MessageKind.INVENTORY, room_code, None, s, e, {"rooms_to_sell": rooms}))
        for code in codes:
            if restrictions:
                out.append(Update(MessageKind.RESTRICTIONS, room_code, code, s, e, dict(restrictions)))
            if rates:
                out.append(Update(MessageKind.RATES, room_code, code, s, e, dict(rates)))
    return out


@register("inventory-rates-json")
def parse(body: bytes, limits: Limits) -> NormalizedSubmission:
    try:
        doc = json.loads(body)
    except ValueError:
        raise IngestError(ErrorCode.INVALID_PAYLOAD, "nội dung không phải JSON hợp lệ") from None
    if not isinstance(doc, dict):
        raise IngestError(ErrorCode.INVALID_PAYLOAD, "nội dung phải là một object")
    hotel = doc.get("hotelid")
    rooms = doc.get("room")
    if not isinstance(hotel, str) or not hotel.strip():
        raise IngestError(ErrorCode.INVALID_PAYLOAD, "thiếu hotelid")
    if not isinstance(rooms, list) or not rooms:
        raise IngestError(ErrorCode.INVALID_PAYLOAD, "thiếu danh sách room")
    updates: list[Update] = []
    errors: list[RowError] = []
    for ri, room in enumerate(rooms):
        path = f"room[{ri}]"
        try:
            if not isinstance(room, dict):
                raise _Row("phần tử room phải là object")
            room_code = _str(room.get("roomid"), "roomid")
            dates = room.get("date")
            if not isinstance(dates, list) or not dates:
                raise _Row("room cần danh sách date")
        except _Row as e:
            errors.append(RowError(ErrorCode.INVALID_ROW, str(e), path))
            continue
        for di, el in enumerate(dates):
            try:
                updates.extend(_date_element(room_code, el, limits))
            except _Row as e:
                errors.append(RowError(ErrorCode.INVALID_ROW, str(e), f"{path}.date[{di}]"))
            if len(updates) > limits.max_updates:
                raise IngestError(ErrorCode.TOO_MANY_UPDATES, f"quá {limits.max_updates} update trong một lần gửi")
    return NormalizedSubmission(hotel.strip(), updates, errors)
