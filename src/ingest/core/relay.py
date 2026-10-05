"""Relay: đọc outbox theo thứ tự id, phát lên broker, chỉ đánh dấu "đã gửi" khi broker đã xác nhận.

Phát ít nhất một lần: gửi xong mà chưa kịp đánh dấu (chết giữa chừng) thì lần sau gửi lại cùng message_id,
bên nhận khử trùng theo message_id. Gặp lỗi phát thì DỪNG, không bỏ qua để phát message sau, vì như vậy
sẽ đảo thứ tự trong cùng khóa phân vùng. Giả định v1: chỉ MỘT relay chạy tại một thời điểm.
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import func, select, update
from sqlalchemy.engine import Engine

from ingest.contract import MessageKind, Publisher
from ingest.core.schema import outbox

log = logging.getLogger("ingest.relay")


def _fetch(engine: Engine, limit: int):
    with engine.connect() as conn:
        return conn.execute(
            select(outbox.c.id, outbox.c.message_id, outbox.c.kind, outbox.c.key, outbox.c.payload)
            .where(outbox.c.sent_at_us.is_(None))
            .order_by(outbox.c.id)
            .limit(limit)
        ).all()


def _mark_sent(engine: Engine, row_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(
            update(outbox).where(outbox.c.id == row_id).values(sent_at_us=int(time.time() * 1_000_000))
        )


def _bump_attempts(engine: Engine, row_id: int) -> None:
    with engine.begin() as conn:
        conn.execute(update(outbox).where(outbox.c.id == row_id).values(attempts=outbox.c.attempts + 1))


def pending(engine: Engine) -> int:
    with engine.connect() as conn:
        return conn.execute(select(func.count()).select_from(outbox).where(outbox.c.sent_at_us.is_(None))).scalar_one()


async def drain_once(engine: Engine, publisher: Publisher, limit: int = 200) -> int:
    """Phát tối đa `limit` message chưa gửi, theo thứ tự. Trả số message đã được broker xác nhận."""
    rows = await asyncio.to_thread(_fetch, engine, limit)
    sent = 0
    for row in rows:
        try:
            await publisher.publish(MessageKind(row.kind), row.key, row.payload.encode(), row.message_id)
        except Exception:
            log.exception("phát outbox id=%s lỗi; dừng để giữ thứ tự", row.id)
            await asyncio.to_thread(_bump_attempts, engine, row.id)
            break
        await asyncio.to_thread(_mark_sent, engine, row.id)
        sent += 1
    return sent


async def run_forever(engine: Engine, publisher: Publisher, interval: float, limit: int) -> None:
    while True:
        try:
            sent = await drain_once(engine, publisher, limit)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("relay lỗi")
            sent = 0
        if sent < limit:
            await asyncio.sleep(interval)
