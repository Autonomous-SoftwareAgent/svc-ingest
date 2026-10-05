"""Hợp đồng chuẩn của Ingest: nơi ba lớp (vào/ra, chuẩn hóa, logic nội bộ) gặp nhau.

Không import module nào khác của dịch vụ. Mọi lớp chỉ biết dạng chuẩn ở đây.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol


class MessageKind(str, enum.Enum):
    """Ba loại message phát ra; mỗi loại một topic."""

    INVENTORY = "inventory"  # số phòng bán được
    RESTRICTIONS = "restrictions"  # điều kiện bán: đóng bán, đóng nhận/trả phòng, số đêm
    RATES = "rates"  # giá theo số khách và phụ thu


class ErrorCode:
    """Mã lỗi chuẩn. Chỉ UNKNOWN_CODE (10) do nghiệp vụ quy định; các mã còn lại do dịch vụ tự đặt."""

    UNKNOWN_CODE = 10  # mã phòng hoặc gói giá lạ: bỏ dòng đó, các dòng còn lại vẫn đi
    NO_VALID_DATA = 12  # không còn dữ liệu hợp lệ nào: từ chối cả lần gửi
    INVALID_ROW = 20  # một dòng sai cấu trúc: bỏ dòng đó
    INVALID_PAYLOAD = 21  # không đọc được, sai định dạng
    INVALID_TRACE_ID = 22  # thiếu hoặc sai X-Trace-Id (phải là UUID)
    BODY_TOO_LARGE = 23
    TOO_MANY_UPDATES = 24
    BAD_ARGUMENT = 25  # tham số API nội bộ sai
    UNAUTHORIZED = 30  # sai tên đăng nhập hoặc mật khẩu
    HOTEL_NOT_ALLOWED = 31  # mã khách sạn lạ hoặc đối tác không có quyền (không phân biệt, tránh dò mã)
    IDEMPOTENCY_CONFLICT = 40  # cùng khóa chống trùng nhưng nội dung khác
    CONFLICT = 41
    NOT_FOUND = 42
    SAVE_FAILED = 50  # không lưu bền được: không ACK


@dataclass(frozen=True)
class RowError:
    code: int
    short_text: str
    path: str = ""


class IngestError(Exception):
    """Lỗi nghiệp vụ có mã chuẩn. Lớp vào/ra tự đổi mã sang trạng thái HTTP."""

    def __init__(self, code: int, short_text: str, errors: list[RowError] | None = None):
        super().__init__(short_text)
        self.code = code
        self.short_text = short_text
        self.errors = errors or []


@dataclass(frozen=True)
class Limits:
    max_span_days: int  # một dòng date không được kéo dài hơn số ngày này
    max_updates: int  # số update tối đa sau khi tách trong một lần gửi


@dataclass(frozen=True)
class Update:
    """Một thay đổi theo mã của đối tác, đã tách theo thứ trong tuần. date_from, date_to tính cả hai đầu."""

    kind: MessageKind
    room_code: str
    rate_plan_code: str | None
    date_from: date
    date_to: date
    data: dict[str, Any]


@dataclass(frozen=True)
class NormalizedSubmission:
    hotel_code: str
    updates: list[Update] = field(default_factory=list)
    row_errors: list[RowError] = field(default_factory=list)


@dataclass(frozen=True)
class PartnerInfo:
    id: int
    name: str
    format: str


@dataclass(frozen=True)
class AckResult:
    ticket_id: str
    duplicate: bool
    row_errors: list[RowError] = field(default_factory=list)


class Publisher(Protocol):
    """Cổng phát ra broker. Phải ném ngoại lệ khi chưa được broker xác nhận.

    `key` là khóa phân vùng: mọi message của một phòng (và gói giá) cùng key để giữ thứ tự.
    `message_id` ổn định qua các lần gửi lại để bên nhận khử trùng.
    """

    async def publish(self, kind: MessageKind, key: str, value: bytes, message_id: str) -> None: ...
