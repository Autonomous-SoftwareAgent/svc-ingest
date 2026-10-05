"""Tiêu chí nghiệm thu RQM với Kafka thật: Kafka tạm ngừng, dịch vụ khởi động lại, message bị gửi lặp.

Dữ liệu đã ACK vẫn phải tới worker sau khi hệ thống phục hồi và không gây cập nhật trùng.

Cần: INGEST_TEST_KAFKA_BOOTSTRAP (vd 127.0.0.1:29094) và INGEST_TEST_KAFKA_CONTAINER (tên container Kafka,
để `docker pause`). Kafka ở đây là broker CỤC BỘ một nút, chưa phải broker production.
"""
import asyncio
import hashlib
import json
import os
import subprocess
import time
import uuid

import pytest
from aiokafka import AIOKafkaConsumer
from sqlalchemy import Column, MetaData, String, Table, create_engine, func, insert, select
from sqlalchemy.exc import IntegrityError

from ingest import normalize
from ingest.contract import MessageKind
from ingest.core import relay, service
from ingest.io.kafka import KafkaPublisher
from tests.conftest import LIMITS, body, sample

BOOT = os.environ.get("INGEST_TEST_KAFKA_BOOTSTRAP")
CONTAINER = os.environ.get("INGEST_TEST_KAFKA_CONTAINER")

pytestmark = [
    pytest.mark.kafka,
    pytest.mark.skipif(not (BOOT and CONTAINER), reason="cần INGEST_TEST_KAFKA_BOOTSTRAP và INGEST_TEST_KAFKA_CONTAINER"),
]

# Worker tham chiếu (chỉ để test): ghi "đã xử lý" cùng lúc với cập nhật dữ liệu, khóa chính là message_id.
_meta = MetaData()
applied = Table("worker_applied", _meta, Column("message_id", String(36), primary_key=True), Column("room_key", String(300)))


def _topics():
    sfx = uuid.uuid4().hex[:8]
    return {k: f"test.{sfx}.{k.value}" for k in MessageKind}


def _accept(env, i):
    doc = sample()
    doc["room"][0]["date"][0]["roomstosell"] = i + 1
    raw = body(doc)
    sub = normalize.get("inventory-rates-json")(raw, LIMITS)
    return service.accept(
        env.engine, env.cache, env.partner, f"00000000-0000-4000-8000-{i:012d}", "web", hashlib.sha256(raw).hexdigest(), sub
    )


def _docker(cmd):
    subprocess.run(["docker", cmd, CONTAINER], check=True, capture_output=True)


async def _drain_until_empty(engine, pub, tries=40):
    for _ in range(tries):
        await relay.drain_once(engine, pub)
        if relay.pending(engine) == 0:
            return
        await asyncio.sleep(1)
    raise AssertionError("outbox chưa rỗng sau khi Kafka phục hồi")


async def _consume(topics, expected, settle=3.0, timeout=60.0):
    c = AIOKafkaConsumer(
        *topics.values(), bootstrap_servers=BOOT, group_id=f"t-{uuid.uuid4().hex}",
        auto_offset_reset="earliest", enable_auto_commit=False,
    )
    await c.start()
    got = []
    try:
        deadline = time.monotonic() + timeout
        while len(got) < expected and time.monotonic() < deadline:
            for msgs in (await c.getmany(timeout_ms=1000)).values():
                got.extend(json.loads(m.value) for m in msgs)
        end = time.monotonic() + settle  # chờ thêm để thấy cả message thừa nếu có
        while time.monotonic() < end:
            for msgs in (await c.getmany(timeout_ms=500)).values():
                got.extend(json.loads(m.value) for m in msgs)
    finally:
        await c.stop()
    return got


def _apply_all(engine, received):
    """Worker: mỗi message áp dụng đúng một lần nhờ khóa chính message_id. Trả (số áp dụng, số bị bỏ vì trùng)."""
    _meta.drop_all(engine)  # cô lập giữa các test (PostgreSQL giữ bảng lại giữa các lần chạy)
    _meta.create_all(engine)
    done = dup = 0
    for m in received:
        try:
            with engine.begin() as c:
                c.execute(insert(applied).values(message_id=m["messageId"], room_key=m["roomId"]))
            done += 1
        except IntegrityError:
            dup += 1
    return done, dup


def _applied_count(engine):
    with engine.connect() as c:
        return c.execute(select(func.count()).select_from(applied)).scalar_one()


def test_kafka_paused_then_resumed_delivers_everything_acked(env):
    topics = _topics()
    n = 4
    expected = n * 3

    async def scenario():
        pub = KafkaPublisher(BOOT, topics, publish_timeout_seconds=3)
        try:
            acks = [_accept(env, 0)]
            assert await relay.drain_once(env.engine, pub) == 3  # Kafka sống: phát bình thường, producer đã nối
            _docker("pause")
            try:
                acks += [_accept(env, i) for i in range(1, n)]  # vẫn ACK được: ACK chỉ cần DB, không cần Kafka
                assert all(not a.duplicate for a in acks)
                assert await relay.drain_once(env.engine, pub) == 0  # Kafka đứng hình: không gửi được, không đánh dấu
                assert relay.pending(env.engine) == expected - 3  # không mất, không đánh dấu nhầm
            finally:
                _docker("unpause")
            await _drain_until_empty(env.engine, pub)
        finally:
            await pub.close()
        return acks

    acks = asyncio.run(scenario())
    received = asyncio.run(_consume(topics, expected))
    # Ít nhất một lần: lần gửi hết giờ lúc Kafka đứng hình có thể vẫn tới broker rồi bị relay gửi lại, nên có thể
    # có message lặp. Điều bắt buộc là: không thiếu cái nào, và worker không áp dụng trùng.
    assert len({m["messageId"] for m in received}) == expected and len(received) >= expected
    assert {m["ticketId"] for m in received} == {a.ticket_id for a in acks}  # mọi lần gửi đã ACK đều tới nơi
    done, dup = _apply_all(env.engine, received)
    assert (done, dup) == (expected, len(received) - expected) and _applied_count(env.engine) == expected


def test_service_restart_with_unsent_outbox_still_delivers(env):
    topics = _topics()
    acks = [_accept(env, i) for i in range(3)]  # đã ACK, chưa phát gì
    assert relay.pending(env.engine) == 9
    url = env.engine.url
    env.engine.dispose()  # "tiến trình chết": mất hết trạng thái trong bộ nhớ (kết nối, cache, producer)

    async def scenario():
        engine2 = create_engine(url)  # "khởi động lại": kết nối mới, publisher mới, không nhớ gì
        pub = KafkaPublisher(BOOT, topics, publish_timeout_seconds=10)
        try:
            await _drain_until_empty(engine2, pub)
        finally:
            await pub.close()
            engine2.dispose()

    asyncio.run(scenario())
    received = asyncio.run(_consume(topics, 9))
    assert len({m["messageId"] for m in received}) == 9 and {m["ticketId"] for m in received} == {a.ticket_id for a in acks}
    done, dup = _apply_all(create_engine(url), received)
    assert (done, dup) == (9, len(received) - 9)


def test_duplicate_delivery_does_not_apply_twice(env):
    """Gửi xong chưa kịp đánh dấu rồi chết: Kafka nhận trùng một message, worker vẫn chỉ áp dụng một lần."""
    topics = _topics()
    _accept(env, 0)

    class CrashAfterFirstPublish(KafkaPublisher):
        crashed = False

        async def publish(self, kind, key, value, message_id):
            await super().publish(kind, key, value, message_id)  # Kafka đã xác nhận
            if not self.crashed:
                self.crashed = True
                raise ConnectionError("chết sau khi Kafka xác nhận, trước khi đánh dấu đã gửi")

    async def scenario():
        pub = CrashAfterFirstPublish(BOOT, topics, publish_timeout_seconds=10)
        try:
            await relay.drain_once(env.engine, pub)  # chết giữa chừng
            assert relay.pending(env.engine) == 3  # chưa đánh dấu cái nào
            await _drain_until_empty(env.engine, pub)  # chạy lại: gửi lại cả ba, trong đó một cái là gửi lặp
        finally:
            await pub.close()

    asyncio.run(scenario())
    received = asyncio.run(_consume(topics, 4))
    ids = [m["messageId"] for m in received]
    assert len(ids) == 4 and len(set(ids)) == 3  # Kafka có một message lặp, cùng messageId
    done, dup = _apply_all(env.engine, received)
    assert (done, dup) == (3, 1) and _applied_count(env.engine) == 3
