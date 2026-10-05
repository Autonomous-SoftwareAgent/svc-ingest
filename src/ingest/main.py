"""Nối ba lớp lại với nhau. Chỉ tệp này (và config.py) được import mọi lớp.

Chạy: uvicorn ingest.main:build_app --factory --host 0.0.0.0 --port 8080
Kiểm cấu hình: python -m ingest.main --check-config
"""
from __future__ import annotations

import asyncio
import contextlib
import hashlib
import logging
import sys
from datetime import datetime
from functools import partial
from typing import Any

from fastapi import FastAPI
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from ingest import normalize
from ingest.config import Settings
from ingest.contract import AckResult, ErrorCode, IngestError, Limits, MessageKind, PartnerInfo, Publisher
from ingest.core import auth, catalog, relay, schema, service
from ingest.core.cache import TtlCache
from ingest.io.http import AdminHooks, Hooks, create_app
from ingest.io.kafka import KafkaPublisher
from ingest.io.publishers import LogPublisher

log = logging.getLogger("ingest")


def make_publisher(settings: Settings) -> Publisher:
    if settings.publisher == "log":
        return LogPublisher()
    return KafkaPublisher(
        settings.kafka_bootstrap_servers,
        {
            MessageKind.INVENTORY: settings.topic_inventory,
            MessageKind.RESTRICTIONS: settings.topic_restrictions,
            MessageKind.RATES: settings.topic_rates,
        },
        publish_timeout_seconds=settings.kafka_publish_timeout_seconds,
    )


def build_hooks(settings: Settings, engine: Engine, cache: TtlCache) -> Hooks:
    limits = Limits(settings.max_date_span_days, settings.max_updates_per_request)

    def ingest(partner: PartnerInfo, trace_id: str, channel_id: str | None, body: bytes) -> AckResult:
        parse = normalize.get(partner.format)
        if parse is None:
            raise RuntimeError(f"đối tác {partner.name!r} dùng định dạng chưa đăng ký: {partner.format!r}")
        sub = parse(body, limits)
        return service.accept(engine, cache, partner, trace_id, channel_id, hashlib.sha256(body).hexdigest(), sub)

    def register_partner(name: str, username: str, password: str, fmt: str) -> int:
        if fmt not in normalize.names():
            raise IngestError(ErrorCode.BAD_ARGUMENT, f"format phải là một trong {normalize.names()}")
        return catalog.register_partner(engine, name, username, password, fmt)

    def healthcheck() -> dict[str, Any]:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"database": "ok", "outboxPending": relay.pending(engine)}

    return Hooks(
        authenticate=partial(auth.authenticate, engine),
        ingest=ingest,
        healthcheck=healthcheck,
        admin=AdminHooks(
            register_partner=register_partner,
            list_partners=partial(catalog.list_partners, engine),
            set_hotel=partial(catalog.set_hotel, engine, cache),
            set_room=partial(catalog.set_room, engine, cache),
            set_rate_plan=partial(catalog.set_rate_plan, engine, cache),
            get_catalog=partial(catalog.get_catalog, engine),
        ),
        internal_token=settings.internal_token,
        max_body_bytes=settings.max_body_bytes,
    )


def build_app(settings: Settings | None = None, publisher: Publisher | None = None, engine: Engine | None = None) -> FastAPI:
    logging.basicConfig(level=logging.INFO)  # không làm gì nếu đã cấu hình
    settings = settings or Settings()  # type: ignore[call-arg]
    publisher = publisher or make_publisher(settings)
    engine = engine or create_engine(settings.database_url, pool_pre_ping=True)
    cache = TtlCache(settings.catalog_cache_ttl_seconds)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI):
        schema.create_all(engine)
        task = (
            asyncio.create_task(
                relay.run_forever(engine, publisher, settings.relay_interval_seconds, settings.relay_batch_size)
            )
            if settings.relay_enabled
            else None
        )
        try:
            yield
        finally:
            if task:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            close = getattr(publisher, "close", None)
            if close:
                await close()
            engine.dispose()

    return create_app(build_hooks(settings, engine, cache), lifespan=lifespan)


if __name__ == "__main__":
    if "--check-config" in sys.argv:
        s = Settings()  # type: ignore[call-arg]
        print(
            f"OK: publisher={s.publisher} relay_enabled={s.relay_enabled} "
            f"internal_api={'bật' if s.internal_token else 'tắt (thiếu INGEST_INTERNAL_TOKEN)'}"
        )
        sys.exit(0)
    import uvicorn

    uvicorn.run("ingest.main:build_app", factory=True, host="0.0.0.0", port=8080)
