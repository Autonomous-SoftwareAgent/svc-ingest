"""Tranh chấp đồng thời. Chỉ có nghĩa trên PostgreSQL (SQLite khóa cả DB), nên bỏ qua nếu thiếu."""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import func, select

from ingest.core import schema
from tests.test_core import accept, count

pytestmark = pytest.mark.skipif(
    not os.environ.get("INGEST_TEST_DATABASE_URL"),
    reason="cần INGEST_TEST_DATABASE_URL trỏ tới PostgreSQL",
)

TRACE = "11111111-1111-4111-8111-111111111111"


def test_same_trace_sent_concurrently_gets_one_ticket_and_one_set_of_messages(env):
    with ThreadPoolExecutor(max_workers=12) as pool:
        acks = list(pool.map(lambda _: accept(env), range(12)))
    assert len({a.ticket_id for a in acks}) == 1
    assert sum(not a.duplicate for a in acks) == 1
    assert count(env.engine, schema.outbox) == 3 and count(env.engine, schema.submission) == 1


def test_many_distinct_requests_concurrently_all_acked_with_unique_message_ids(env):
    def run(i):
        return accept(env, trace=f"00000000-0000-4000-8000-{i:012d}")

    with ThreadPoolExecutor(max_workers=12) as pool:
        acks = list(pool.map(run, range(30)))
    assert len({a.ticket_id for a in acks}) == 30
    with env.engine.connect() as c:
        total = c.execute(select(func.count()).select_from(schema.outbox)).scalar_one()
        ids = c.execute(select(func.count(func.distinct(schema.outbox.c.message_id)))).scalar_one()
    assert total == ids == 90
