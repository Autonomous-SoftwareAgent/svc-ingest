"""Bảng PostgreSQL của Ingest (SQLAlchemy Core). v1 tạo bảng bằng create_all; chưa có công cụ migration.

Ingest KHÔNG giữ số phòng còn lại hay giá hiện tại: chỉ giữ danh mục để đổi mã, nhật ký lần gửi và outbox.
"""
from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.engine import Engine

metadata = MetaData()

# SQLite (test mặc định) không tự tăng với BigInteger; PostgreSQL dùng BigInteger thật.
_ID = BigInteger().with_variant(Integer, "sqlite")

partner = Table(
    "partner",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(128), nullable=False, unique=True),
    Column("username", String(128), nullable=False, unique=True),
    Column("password_hash", String(256), nullable=False),  # scrypt, không lưu mật khẩu thô
    Column("format", String(64), nullable=False),  # tên định dạng đã đăng ký ở lớp chuẩn hóa
    Column("active", Boolean, nullable=False, default=True),
    Column("created_at_us", BigInteger, nullable=False),
)

# Đối tác được gửi cho khách sạn nào, và mã nội bộ của khách sạn đó.
hotel_access = Table(
    "hotel_access",
    metadata,
    Column("partner_id", Integer, ForeignKey("partner.id"), primary_key=True),
    Column("hotel_code", String(128), primary_key=True),  # mã do đối tác biết
    Column("hotel_id", String(128), nullable=False),  # mã nội bộ
    Column("name", String(256)),
)

room_map = Table(
    "room_map",
    metadata,
    Column("partner_id", Integer, primary_key=True),
    Column("hotel_code", String(128), primary_key=True),
    Column("room_code", String(128), primary_key=True),
    Column("room_id", String(128), nullable=False),
    Column("name", String(256)),
    ForeignKeyConstraint(
        ["partner_id", "hotel_code"], ["hotel_access.partner_id", "hotel_access.hotel_code"]
    ),
)

rate_plan_map = Table(
    "rate_plan_map",
    metadata,
    Column("partner_id", Integer, primary_key=True),
    Column("hotel_code", String(128), primary_key=True),
    Column("rate_plan_code", String(128), primary_key=True),
    Column("rate_plan_id", String(128), nullable=False),
    Column("name", String(256)),
    ForeignKeyConstraint(
        ["partner_id", "hotel_code"], ["hotel_access.partner_id", "hotel_access.hotel_code"]
    ),
)

# Nhật ký lần gửi đã được ACK. (partner_id, trace_id) là khóa chống trùng.
submission = Table(
    "submission",
    metadata,
    Column("ticket_id", String(36), primary_key=True),
    Column("partner_id", Integer, ForeignKey("partner.id"), nullable=False),
    Column("trace_id", String(36), nullable=False),
    Column("body_hash", String(64), nullable=False),
    Column("channel_id", String(128)),
    Column("hotel_code", String(128), nullable=False),
    Column("received_at_us", BigInteger, nullable=False),
    Column("messages", Integer, nullable=False),
    Column("row_errors", Text, nullable=False),  # JSON: các dòng bị bỏ và lý do
    UniqueConstraint("partner_id", "trace_id", name="uq_submission_partner_trace"),
)

# Hộp thư đi: ghi cùng transaction với submission, relay phát sau. id tăng dần = thứ tự phát.
outbox = Table(
    "outbox",
    metadata,
    Column("id", _ID, primary_key=True, autoincrement=True),
    Column("message_id", String(36), nullable=False, unique=True),
    Column("ticket_id", String(36), nullable=False),
    Column("kind", String(16), nullable=False),
    Column("key", String(400), nullable=False),
    Column("payload", Text, nullable=False),
    Column("created_at_us", BigInteger, nullable=False),
    Column("sent_at_us", BigInteger, nullable=True),
    Column("attempts", Integer, nullable=False, default=0),
)
Index("ix_outbox_unsent", outbox.c.sent_at_us, outbox.c.id)


def create_all(engine: Engine) -> None:
    metadata.create_all(engine)
