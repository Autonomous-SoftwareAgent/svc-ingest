"""Các cổng phát đơn giản: ghi log (chạy thử cục bộ) và giữ trong bộ nhớ (test)."""
from __future__ import annotations

import logging

from ingest.contract import MessageKind

log = logging.getLogger("ingest.publisher")


class LogPublisher:
    """Ghi message ra log thay vì broker thật. Chỉ dùng khi chạy thử cục bộ."""

    async def publish(self, kind: MessageKind, key: str, value: bytes, message_id: str) -> None:
        log.info("publish kind=%s key=%s id=%s bytes=%d", kind.value, key, message_id, len(value))


class MemoryPublisher:
    """Giữ message trong bộ nhớ; `fail` bật thì ném lỗi như broker hỏng."""

    def __init__(self) -> None:
        self.sent: list[tuple[MessageKind, str, bytes, str]] = []
        self.fail = False

    async def publish(self, kind: MessageKind, key: str, value: bytes, message_id: str) -> None:
        if self.fail:
            raise ConnectionError("broker không sẵn sàng")
        self.sent.append((kind, key, value, message_id))
