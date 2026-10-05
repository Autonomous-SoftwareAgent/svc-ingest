"""Test chạy trên PostgreSQL nếu có INGEST_TEST_DATABASE_URL, ngược lại trên SQLite tạm.

SQLite KHÔNG chứng minh hành vi tranh chấp đồng thời của PostgreSQL: chỉ kiểm logic.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from ingest.contract import Limits, PartnerInfo
from ingest.core import catalog, schema
from ingest.core.cache import TtlCache

LIMITS = Limits(max_span_days=730, max_updates=10_000)

SAMPLE = {
    "hotelid": "HTL001",
    "room": [
        {
            "roomid": "DLX",
            "date": [
                {
                    "from": "2026-11-14",
                    "to": "2026-11-16",
                    "rate": [{"rateplanid": "BAR"}],
                    "roomstosell": 2,
                    "price": [{"NumberOfGuests": 1, "value": 2150000}, {"NumberOfGuests": 2, "value": 2150000}],
                    "extraadultrate": 300000,
                    "extrachildrate": 150000,
                    "closed": "0",
                    "closedonarrival": "0",
                    "closedondeparture": "0",
                    "minimumstay": 1,
                    "maximumstay": 14,
                    "dow": [1, 2, 3, 4, 5, 6, 7],
                }
            ],
        }
    ],
}


def sample() -> dict:
    return copy.deepcopy(SAMPLE)


def body(doc: dict) -> bytes:
    return json.dumps(doc).encode()


@pytest.fixture
def engine():
    # Không dùng tmp_path: thư mục gốc tạm của pytest có thể không ghi được trên một số máy.
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        url = os.environ.get("INGEST_TEST_DATABASE_URL") or f"sqlite:///{Path(d) / 'ingest.db'}"
        eng = create_engine(url)
        schema.metadata.drop_all(eng)
        schema.create_all(eng)
        yield eng
        schema.metadata.drop_all(eng)
        eng.dispose()


@dataclass
class Env:
    engine: object
    cache: TtlCache
    partner_id: int
    partner: PartnerInfo


@pytest.fixture
def env(engine) -> Env:
    cache = TtlCache(86_400)
    pid = catalog.register_partner(engine, "acme", "acme-user", "s3cret-pass", "inventory-rates-json")
    catalog.set_hotel(engine, cache, pid, "HTL001", "h-1", "Khách sạn 1")
    for code, rid in (("DLX", "r-dlx"), ("STD", "r-std")):
        catalog.set_room(engine, cache, pid, "HTL001", code, rid, None)
    for code, plan in (("BAR", "p-bar"), ("NR", "p-nr")):
        catalog.set_rate_plan(engine, cache, pid, "HTL001", code, plan, None)
    return Env(engine, cache, pid, PartnerInfo(pid, "acme", "inventory-rates-json"))
