"""Nhận một lần gửi đã chuẩn hóa: kiểm quyền khách sạn, đổi mã, chống trùng, ghi nhật ký và outbox.

ACK (trả về AckResult) chỉ xảy ra SAU KHI transaction đã commit. Không gọi broker hay mạng khi đang giữ
transaction; việc phát nằm ở relay.py. ACK chỉ có nghĩa "đã nhận, đã kiểm sơ bộ, đã lưu an toàn để xử lý".
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from ingest.contract import (
    AckResult,
    ErrorCode,
    IngestError,
    MessageKind,
    NormalizedSubmission,
    PartnerInfo,
    RowError,
)
from ingest.core.cache import TtlCache
from ingest.core.schema import hotel_access, outbox, rate_plan_map, room_map, submission

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
_ATTEMPTS = 3


@dataclass(frozen=True)
class HotelMaps:
    hotel_id: str
    rooms: dict[str, str]
    plans: dict[str, str]


def _us(dt: datetime) -> int:
    return (dt - _EPOCH) // timedelta(microseconds=1)


def _load_maps(engine: Engine, partner_id: int, hotel_code: str) -> HotelMaps | None:
    with engine.connect() as conn:
        h = conn.execute(
            select(hotel_access.c.hotel_id).where(
                hotel_access.c.partner_id == partner_id, hotel_access.c.hotel_code == hotel_code
            )
        ).first()
        if h is None:
            return None
        rooms = {
            r.room_code: r.room_id
            for r in conn.execute(
                select(room_map.c.room_code, room_map.c.room_id).where(
                    room_map.c.partner_id == partner_id, room_map.c.hotel_code == hotel_code
                )
            )
        }
        plans = {
            r.rate_plan_code: r.rate_plan_id
            for r in conn.execute(
                select(rate_plan_map.c.rate_plan_code, rate_plan_map.c.rate_plan_id).where(
                    rate_plan_map.c.partner_id == partner_id, rate_plan_map.c.hotel_code == hotel_code
                )
            )
        }
    return HotelMaps(h[0], rooms, plans)


def _maps(engine: Engine, cache: TtlCache, partner_id: int, hotel_code: str) -> HotelMaps | None:
    key = (partner_id, hotel_code)
    maps = cache.get(key)
    if maps is None:
        maps = _load_maps(engine, partner_id, hotel_code)
        if maps is not None:  # không nhớ "không có quyền", để quyền mới có hiệu lực ngay
            cache.set(key, maps)
    return maps


def _errors_json(errors: list[RowError]) -> str:
    return json.dumps([{"code": e.code, "shortText": e.short_text, "path": e.path} for e in errors])


def _errors_from_json(text: str) -> list[RowError]:
    return [RowError(e["code"], e["shortText"], e.get("path", "")) for e in json.loads(text)]


def _find_existing(engine: Engine, partner_id: int, trace_id: str):
    with engine.connect() as conn:
        return conn.execute(
            select(submission.c.ticket_id, submission.c.body_hash, submission.c.row_errors).where(
                submission.c.partner_id == partner_id, submission.c.trace_id == trace_id
            )
        ).first()


def _replay(existing: Any, body_hash: str) -> AckResult:
    if existing.body_hash != body_hash:
        raise IngestError(
            ErrorCode.IDEMPOTENCY_CONFLICT, "X-Trace-Id này đã dùng cho một nội dung khác"
        )
    return AckResult(existing.ticket_id, True, _errors_from_json(existing.row_errors))


def _build(
    maps: HotelMaps,
    sub: NormalizedSubmission,
    ticket_id: str,
    channel_id: str | None,
    received_at: datetime,
) -> tuple[list[dict[str, Any]], list[RowError]]:
    errors = list(sub.row_errors)
    unknown: set[str] = set()
    ticket = uuid.UUID(ticket_id)
    rows: list[dict[str, Any]] = []
    now = _us(received_at)

    def unknown_once(what: str, code: str) -> None:
        if f"{what}:{code}" not in unknown:
            unknown.add(f"{what}:{code}")
            errors.append(RowError(ErrorCode.UNKNOWN_CODE, f"mã {what} lạ: {code}", f"{what}={code}"))

    for idx, u in enumerate(sub.updates):
        room_id = maps.rooms.get(u.room_code)
        if room_id is None:
            unknown_once("phòng", u.room_code)
            continue
        plan_id = None
        if u.rate_plan_code is not None:
            plan_id = maps.plans.get(u.rate_plan_code)
            if plan_id is None:
                unknown_once("gói giá", u.rate_plan_code)
                continue
        message_id = str(uuid.uuid5(ticket, str(idx)))  # ổn định: cùng lần gửi, cùng vị trí, cùng ID
        key = f"{maps.hotel_id}:{room_id}" + (f":{plan_id}" if plan_id else "")
        payload = {
            "messageId": message_id,
            "ticketId": ticket_id,
            "kind": u.kind.value,
            "hotelId": maps.hotel_id,
            "roomId": room_id,
            "ratePlanId": plan_id,
            "dateFrom": u.date_from.isoformat(),
            "dateTo": u.date_to.isoformat(),
            "receivedAt": received_at.isoformat(),
            "channelId": channel_id,
            "data": u.data,
        }
        rows.append(
            {
                "message_id": message_id,
                "ticket_id": ticket_id,
                "kind": u.kind.value,
                "key": key,
                "payload": json.dumps(payload, separators=(",", ":")),
                "created_at_us": now,
                "attempts": 0,
            }
        )
    return rows, errors


def accept(
    engine: Engine,
    cache: TtlCache,
    partner: PartnerInfo,
    trace_id: str,
    channel_id: str | None,
    body_hash: str,
    sub: NormalizedSubmission,
    received_at: datetime | None = None,
) -> AckResult:
    """Nhận một lần gửi. Cùng (đối tác, trace_id) và cùng nội dung thì trả lại đúng TicketId cũ."""
    existing = _find_existing(engine, partner.id, trace_id)
    if existing is not None:
        return _replay(existing, body_hash)
    maps = _maps(engine, cache, partner.id, sub.hotel_code)
    if maps is None:
        raise IngestError(ErrorCode.HOTEL_NOT_ALLOWED, "mã khách sạn lạ hoặc không có quyền")
    received_at = received_at or datetime.now(timezone.utc)
    ticket_id = str(uuid.uuid4())
    rows, errors = _build(maps, sub, ticket_id, channel_id, received_at)
    if not rows:
        raise IngestError(ErrorCode.NO_VALID_DATA, "không còn dữ liệu hợp lệ nào", errors)
    for attempt in range(_ATTEMPTS):
        try:
            with engine.begin() as conn:
                conn.execute(
                    insert(submission).values(
                        ticket_id=ticket_id,
                        partner_id=partner.id,
                        trace_id=trace_id,
                        body_hash=body_hash,
                        channel_id=channel_id,
                        hotel_code=sub.hotel_code,
                        received_at_us=_us(received_at),
                        messages=len(rows),
                        row_errors=_errors_json(errors),
                    )
                )
                conn.execute(insert(outbox), rows)
            return AckResult(ticket_id, False, errors)  # chỉ tới đây khi đã commit
        except IntegrityError:
            existing = _find_existing(engine, partner.id, trace_id)  # hai yêu cầu cùng khóa đua nhau
            if existing is not None:
                return _replay(existing, body_hash)
            if attempt == _ATTEMPTS - 1:
                raise IngestError(ErrorCode.SAVE_FAILED, "không lưu được, hãy gửi lại") from None
        except SQLAlchemyError:
            raise IngestError(ErrorCode.SAVE_FAILED, "không lưu được, hãy gửi lại") from None
    raise AssertionError("unreachable")
