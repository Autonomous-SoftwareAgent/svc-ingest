import asyncio
import json

from ingest.contract import MessageKind
from ingest.core import relay
from ingest.io.publishers import MemoryPublisher
from tests.test_core import accept, sample


def run(coro):
    return asyncio.run(coro)


def test_drain_publishes_in_outbox_order_and_marks_sent(env):
    accept(env)
    pub = MemoryPublisher()
    assert relay.pending(env.engine) == 3
    assert run(relay.drain_once(env.engine, pub)) == 3
    assert [k for k, *_ in pub.sent] == [MessageKind.INVENTORY, MessageKind.RESTRICTIONS, MessageKind.RATES]
    assert relay.pending(env.engine) == 0
    assert run(relay.drain_once(env.engine, pub)) == 0  # đã gửi thì không gửi lại


def test_failure_stops_keeps_order_and_resumes_without_loss(env):
    accept(env)
    doc = sample()
    doc["room"][0]["date"][0]["roomstosell"] = 7
    accept(env, doc, trace="22222222-2222-4222-8222-222222222222")
    pub = MemoryPublisher()
    pub.fail = True
    assert run(relay.drain_once(env.engine, pub)) == 0 and pub.sent == []
    assert relay.pending(env.engine) == 6  # chưa gửi được cái nào: không mất cái nào
    pub.fail = False
    assert run(relay.drain_once(env.engine, pub)) == 6
    assert [json.loads(v)["ticketId"] for _, _, v, _ in pub.sent][:3] == [json.loads(pub.sent[0][2])["ticketId"]] * 3
    assert len({m for *_, m in pub.sent}) == 6


def test_failure_in_the_middle_does_not_skip_later_messages(env):
    accept(env)

    class FailSecondOnce(MemoryPublisher):
        failed = False

        async def publish(self, kind, key, value, message_id):
            if len(self.sent) == 1 and not self.failed:
                self.failed = True  # chỉ lỗi đúng một lần, ở message thứ hai
                raise ConnectionError("broker chớp lỗi")
            return await super().publish(kind, key, value, message_id)

    pub = FailSecondOnce()
    assert run(relay.drain_once(env.engine, pub)) == 1
    assert len(pub.sent) == 1 and relay.pending(env.engine) == 2  # message sau không bị vượt lên
    assert run(relay.drain_once(env.engine, pub)) == 2
    assert [k for k, *_ in pub.sent] == [MessageKind.INVENTORY, MessageKind.RESTRICTIONS, MessageKind.RATES]


def test_crash_after_publish_before_mark_resends_same_message_id(env):
    """Chết giữa lúc gửi xong và đánh dấu: lần sau gửi lại cùng message_id (ít nhất một lần)."""
    accept(env)

    class CrashAfterFirst(MemoryPublisher):
        async def publish(self, kind, key, value, message_id):
            await super().publish(kind, key, value, message_id)
            if len(self.sent) == 1:
                raise ConnectionError("chết sau khi gửi, trước khi biết kết quả")

    pub = CrashAfterFirst()
    run(relay.drain_once(env.engine, pub))
    run(relay.drain_once(env.engine, pub))
    ids = [m for *_, m in pub.sent]
    assert ids[0] == ids[1]  # trùng, cùng ID: bên nhận khử trùng được
    assert len(set(ids)) == 3 and relay.pending(env.engine) == 0


def test_attempts_counter_increases_on_failure(env):
    from sqlalchemy import select

    from ingest.core import schema

    accept(env)
    pub = MemoryPublisher()
    pub.fail = True
    run(relay.drain_once(env.engine, pub))
    run(relay.drain_once(env.engine, pub))
    with env.engine.connect() as c:
        first = c.execute(select(schema.outbox.c.attempts).order_by(schema.outbox.c.id)).first()
    assert first[0] == 2


def test_run_forever_drains_and_can_be_cancelled(env):
    accept(env)
    pub = MemoryPublisher()

    async def main():
        task = asyncio.create_task(relay.run_forever(env.engine, pub, 0.01, 10))
        for _ in range(100):
            if relay.pending(env.engine) == 0:
                break
            await asyncio.sleep(0.02)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    run(main())
    assert len(pub.sent) == 3
