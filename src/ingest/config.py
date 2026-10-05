"""Cấu hình từ biến môi trường (tiền tố INGEST_). Chỉ main.py dùng; secret chỉ đến từ môi trường."""
from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INGEST_", env_file=".env", extra="ignore")

    # postgresql+psycopg://user:pass@host:5432/db
    database_url: str

    publisher: Literal["kafka", "log"] = "kafka"
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_publish_timeout_seconds: float = 15.0
    topic_inventory: str = "ingest.ari.inventory"
    topic_restrictions: str = "ingest.ari.restrictions"
    topic_rates: str = "ingest.ari.rates"

    # Token cho API nội bộ. Để trống thì mọi API nội bộ bị từ chối.
    internal_token: str | None = None

    # Số nghiệp vụ và giới hạn: cấu hình có tên, không viết cứng trong mã.
    max_body_bytes: int = 1_048_576
    max_date_span_days: int = 730
    max_updates_per_request: int = 10_000
    catalog_cache_ttl_seconds: float = 86_400.0  # tra cứu danh mục nhớ tạm 24 giờ

    relay_enabled: bool = True
    relay_interval_seconds: float = 0.5
    relay_batch_size: int = 200
