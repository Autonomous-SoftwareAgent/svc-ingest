"""Cổng phát ra Kafka bằng aiokafka. acks=all và producer idempotent; chỉ trả về khi broker đã xác nhận.

Producer được tạo lười ở lần phát đầu và tạo lại sau mỗi lỗi, nên Kafka chưa sẵn sàng lúc khởi động hay bị
tạm dừng giữa chừng thì lần thử sau (relay thử lại) vẫn nối lại được. Tạo sẵn topic là việc của vận hành.
"""
from __future__ import annotations

import asyncio
import logging

from aiokafka import AIOKafkaProducer

from ingest.contract import MessageKind

log = logging.getLogger("ingest.kafka")


class KafkaPublisher:
    def __init__(
        self,
        bootstrap_servers: str,
        topics: dict[MessageKind, str],
        client_id: str = "ingest",
        publish_timeout_seconds: float = 15.0,
    ) -> None:
        self._bootstrap = bootstrap_servers
        self._topics = topics
        self._client_id = client_id
        self._timeout = publish_timeout_seconds
        self._producer: AIOKafkaProducer | None = None
        self._lock = asyncio.Lock()

    async def _ensure(self) -> AIOKafkaProducer:
        async with self._lock:
            if self._producer is None:
                producer = AIOKafkaProducer(
                    bootstrap_servers=self._bootstrap,
                    client_id=self._client_id,
                    acks="all",
                    enable_idempotence=True,
                    request_timeout_ms=int(self._timeout * 1000),
                    linger_ms=0,
                )
                try:
                    await producer.start()
                except BaseException:
                    await self._quiet_stop(producer)
                    raise
                self._producer = producer
            return self._producer

    async def _quiet_stop(self, producer: AIOKafkaProducer | None) -> None:
        if producer is None:
            return
        try:
            await asyncio.wait_for(producer.stop(), timeout=5)
        except Exception:
            log.debug("dừng producer lỗi", exc_info=True)

    async def _reset(self) -> None:
        async with self._lock:
            producer, self._producer = self._producer, None
        await self._quiet_stop(producer)

    async def publish(self, kind: MessageKind, key: str, value: bytes, message_id: str) -> None:
        topic = self._topics[kind]
        try:
            async def send() -> None:
                producer = await self._ensure()
                await producer.send_and_wait(
                    topic, value=value, key=key.encode(), headers=[("message-id", message_id.encode())]
                )

            await asyncio.wait_for(send(), timeout=self._timeout)
        except Exception:
            await self._reset()
            raise

    async def close(self) -> None:
        await self._reset()
