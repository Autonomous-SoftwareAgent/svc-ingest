"""Danh mục để đổi mã và kiểm quyền: đối tác, khách sạn được phép, phòng, gói giá.

Danh mục chỉ là bản sao để tra cứu, không phải dữ liệu gốc. Hiện nạp qua API nội bộ (chưa có nguồn khác).
"""
from __future__ import annotations

import time
from typing import Any, Callable

from sqlalchemy import insert, select, update
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import IntegrityError

from ingest.contract import ErrorCode, IngestError
from ingest.core.auth import hash_password
from ingest.core.cache import TtlCache
from ingest.core.schema import hotel_access, partner, rate_plan_map, room_map


def _need(value: Any, what: str, max_len: int = 128) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > max_len:
        raise IngestError(ErrorCode.BAD_ARGUMENT, f"{what} phải là chuỗi không rỗng, tối đa {max_len} ký tự")
    return value.strip()


def register_partner(engine: Engine, name: str, username: str, password: str, fmt: str) -> int:
    name, username, fmt = _need(name, "name"), _need(username, "username"), _need(fmt, "format")
    if not isinstance(password, str) or len(password) < 8:
        raise IngestError(ErrorCode.BAD_ARGUMENT, "password phải có ít nhất 8 ký tự")
    try:
        with engine.begin() as conn:
            res = conn.execute(
                insert(partner).values(
                    name=name,
                    username=username,
                    password_hash=hash_password(password),
                    format=fmt,
                    active=True,
                    created_at_us=int(time.time() * 1_000_000),
                )
            )
            return int(res.inserted_primary_key[0])
    except IntegrityError:
        raise IngestError(ErrorCode.CONFLICT, "name hoặc username đã tồn tại") from None


def list_partners(engine: Engine) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [
            {"id": r.id, "name": r.name, "username": r.username, "format": r.format, "active": r.active}
            for r in conn.execute(select(partner.c.id, partner.c.name, partner.c.username, partner.c.format, partner.c.active).order_by(partner.c.id))
        ]


def _partner_exists(conn: Connection, partner_id: int) -> None:
    if conn.execute(select(partner.c.id).where(partner.c.id == partner_id)).first() is None:
        raise IngestError(ErrorCode.NOT_FOUND, "không có đối tác này")


def _hotel_exists(conn: Connection, partner_id: int, hotel_code: str) -> None:
    _partner_exists(conn, partner_id)
    row = conn.execute(
        select(hotel_access.c.hotel_code).where(
            hotel_access.c.partner_id == partner_id, hotel_access.c.hotel_code == hotel_code
        )
    ).first()
    if row is None:
        raise IngestError(ErrorCode.NOT_FOUND, "đối tác chưa được cấp quyền khách sạn này")


def _upsert(engine: Engine, body: Callable[[Connection], None]) -> None:
    for attempt in range(2):
        try:
            with engine.begin() as conn:
                body(conn)
            return
        except IntegrityError:
            if attempt == 1:
                raise IngestError(ErrorCode.CONFLICT, "xung đột khi ghi danh mục, thử lại") from None


def _put(conn: Connection, table, keys: dict[str, Any], values: dict[str, Any]) -> None:
    where = [table.c[k] == v for k, v in keys.items()]
    if conn.execute(update(table).where(*where).values(**values)).rowcount == 0:
        conn.execute(insert(table).values(**keys, **values))


def set_hotel(engine: Engine, cache: TtlCache, partner_id: int, hotel_code: str, hotel_id: str, name: str | None) -> None:
    hotel_code, hotel_id = _need(hotel_code, "hotel_code"), _need(hotel_id, "hotelId")

    def body(conn: Connection) -> None:
        _partner_exists(conn, partner_id)
        _put(conn, hotel_access, {"partner_id": partner_id, "hotel_code": hotel_code}, {"hotel_id": hotel_id, "name": name})

    _upsert(engine, body)
    cache.invalidate_partner(partner_id)


def set_room(engine: Engine, cache: TtlCache, partner_id: int, hotel_code: str, room_code: str, room_id: str, name: str | None) -> None:
    room_code, room_id = _need(room_code, "room_code"), _need(room_id, "roomId")

    def body(conn: Connection) -> None:
        _hotel_exists(conn, partner_id, hotel_code)
        _put(conn, room_map, {"partner_id": partner_id, "hotel_code": hotel_code, "room_code": room_code}, {"room_id": room_id, "name": name})

    _upsert(engine, body)
    cache.invalidate_partner(partner_id)


def set_rate_plan(engine: Engine, cache: TtlCache, partner_id: int, hotel_code: str, code: str, rate_plan_id: str, name: str | None) -> None:
    code, rate_plan_id = _need(code, "rate_plan_code"), _need(rate_plan_id, "ratePlanId")

    def body(conn: Connection) -> None:
        _hotel_exists(conn, partner_id, hotel_code)
        _put(conn, rate_plan_map, {"partner_id": partner_id, "hotel_code": hotel_code, "rate_plan_code": code}, {"rate_plan_id": rate_plan_id, "name": name})

    _upsert(engine, body)
    cache.invalidate_partner(partner_id)


def get_catalog(engine: Engine, partner_id: int) -> dict[str, Any]:
    with engine.connect() as conn:
        _partner_exists(conn, partner_id)
        hotels: dict[str, dict[str, Any]] = {}
        for h in conn.execute(select(hotel_access).where(hotel_access.c.partner_id == partner_id).order_by(hotel_access.c.hotel_code)):
            hotels[h.hotel_code] = {"code": h.hotel_code, "id": h.hotel_id, "name": h.name, "rooms": [], "ratePlans": []}
        for r in conn.execute(select(room_map).where(room_map.c.partner_id == partner_id).order_by(room_map.c.room_code)):
            hotels[r.hotel_code]["rooms"].append({"code": r.room_code, "id": r.room_id, "name": r.name})
        for p in conn.execute(select(rate_plan_map).where(rate_plan_map.c.partner_id == partner_id).order_by(rate_plan_map.c.rate_plan_code)):
            hotels[p.hotel_code]["ratePlans"].append({"code": p.rate_plan_code, "id": p.rate_plan_id, "name": p.name})
    return {"partnerId": partner_id, "hotels": list(hotels.values())}
