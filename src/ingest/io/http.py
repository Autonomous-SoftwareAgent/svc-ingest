"""Lớp vào/ra HTTP. Chỉ lo giao thức: xác thực Basic, header, giới hạn kích thước, đổi mã lỗi sang trạng thái HTTP.

Không biết gì về nghiệp vụ hay định dạng của đối tác: xác thực, chuẩn hóa và ghi được tiêm từ main.py.

    POST /v1/inventory-rates          (đối tác)   Authorization: Basic, X-Trace-Id: UUID, X-Channel-Id
    /internal/v1/...                  (dịch vụ nội bộ, người vận hành)   Authorization: Bearer <token>

ACK (202 kèm ticketId) chỉ có nghĩa "đã nhận, đã kiểm sơ bộ, đã lưu an toàn để xử lý", chưa phải "đã cập nhật xong".
"""
from __future__ import annotations

import base64
import hmac
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from ingest.contract import AckResult, ErrorCode, IngestError, PartnerInfo, RowError

log = logging.getLogger("ingest.http")

_STATUS = {
    ErrorCode.INVALID_ROW: 400,
    ErrorCode.INVALID_PAYLOAD: 400,
    ErrorCode.INVALID_TRACE_ID: 400,
    ErrorCode.NO_VALID_DATA: 400,
    ErrorCode.BAD_ARGUMENT: 400,
    ErrorCode.BODY_TOO_LARGE: 413,
    ErrorCode.TOO_MANY_UPDATES: 413,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.HOTEL_NOT_ALLOWED: 401,  # theo mô tả của người dùng: sai quyền theo khách sạn trả 401
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.IDEMPOTENCY_CONFLICT: 409,
    ErrorCode.CONFLICT: 409,
    ErrorCode.SAVE_FAILED: 503,
}


@dataclass(frozen=True)
class AdminHooks:
    register_partner: Callable[[str, str, str, str], int]
    list_partners: Callable[[], list[dict[str, Any]]]
    set_hotel: Callable[[int, str, str, str | None], None]
    set_room: Callable[[int, str, str, str, str | None], None]
    set_rate_plan: Callable[[int, str, str, str, str | None], None]
    get_catalog: Callable[[int], dict[str, Any]]


@dataclass(frozen=True)
class Hooks:
    authenticate: Callable[[str, str], PartnerInfo | None]
    ingest: Callable[[PartnerInfo, str, str | None, bytes], AckResult]
    healthcheck: Callable[[], dict[str, Any]]
    admin: AdminHooks
    internal_token: str | None  # thiếu thì mọi API nội bộ bị từ chối (mặc định từ chối)
    max_body_bytes: int


class PartnerIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    username: str
    password: str
    format: str = "inventory-rates-json"


class HotelIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hotelId: str
    name: str | None = None


class RoomIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    roomId: str
    name: str | None = None


class RatePlanIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ratePlanId: str
    name: str | None = None


def _err(e: RowError | tuple[int, str]) -> dict[str, Any]:
    if isinstance(e, RowError):
        out: dict[str, Any] = {"code": e.code, "shortText": e.short_text}
        if e.path:
            out["path"] = e.path
        return out
    return {"code": e[0], "shortText": e[1]}


def _fail(code: int, text: str, extra: list[RowError] | None = None, headers: dict[str, str] | None = None) -> JSONResponse:
    return JSONResponse(
        {"status": "Fail", "errors": [_err((code, text))] + [_err(e) for e in extra or []]},
        status_code=_STATUS.get(code, 500),
        headers=headers,
    )


def _from_error(e: IngestError) -> JSONResponse:
    return _fail(e.code, e.short_text, e.errors)


def _basic(header: str | None) -> tuple[str, str] | None:
    if not header or header[:6].lower() != "basic ":
        return None
    try:
        raw = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    user, sep, password = raw.partition(":")
    return (user, password) if sep and user else None


async def _read_capped(request: Request, limit: int) -> bytes | None:
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > limit:
        return None
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def create_app(hooks: Hooks, lifespan: Any = None) -> FastAPI:
    app = FastAPI(title="BSN Ingest", lifespan=lifespan)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return _fail(ErrorCode.BAD_ARGUMENT, "tham số không hợp lệ: " + "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()))  # chỉ lấy vị trí và lý do, không đưa giá trị đầu vào (có thể là mật khẩu)

    @app.get("/healthz")
    def healthz() -> JSONResponse:
        # Kiểm phụ thuộc thật (DB), không chỉ kiểm tiến trình còn sống.
        try:
            return JSONResponse({"status": "Success", "data": hooks.healthcheck()})
        except Exception:
            log.exception("healthcheck lỗi")
            return JSONResponse({"status": "Fail", "errors": [_err((ErrorCode.SAVE_FAILED, "không kết nối được cơ sở dữ liệu"))]}, status_code=503)

    @app.post("/v1/inventory-rates", status_code=202)
    async def inventory_rates(request: Request) -> JSONResponse:
        creds = _basic(request.headers.get("authorization"))
        www = {"WWW-Authenticate": "Basic"}
        if creds is None:
            return _fail(ErrorCode.UNAUTHORIZED, "thiếu hoặc sai Authorization Basic", headers=www)
        partner = await run_in_threadpool(hooks.authenticate, *creds)
        if partner is None:
            return _fail(ErrorCode.UNAUTHORIZED, "sai tên đăng nhập hoặc mật khẩu", headers=www)
        try:
            trace_id = str(uuid.UUID(request.headers.get("x-trace-id", "")))
        except ValueError:
            return _fail(ErrorCode.INVALID_TRACE_ID, "X-Trace-Id là bắt buộc và phải là UUID")
        body = await _read_capped(request, hooks.max_body_bytes)
        if body is None:
            return _fail(ErrorCode.BODY_TOO_LARGE, "nội dung quá lớn")
        channel = (request.headers.get("x-channel-id") or "").strip()[:128] or None
        try:
            ack = await run_in_threadpool(hooks.ingest, partner, trace_id, channel, body)
        except IngestError as e:
            return _from_error(e)
        except Exception:
            log.exception("lỗi không dự kiến khi nhận lần gửi")
            return _fail(ErrorCode.SAVE_FAILED, "không lưu được, hãy gửi lại")
        # Chỉ ghi số đếm và mã, không ghi nội dung hay thông tin xác thực.
        log.info("ack partner=%s ticket=%s duplicate=%s row_errors=%d", partner.name, ack.ticket_id, ack.duplicate, len(ack.row_errors))
        return JSONResponse(
            {
                "status": "Success",
                "data": {"ticketId": ack.ticket_id, "duplicate": ack.duplicate},
                "errors": [_err(e) for e in ack.row_errors],
            },
            status_code=202,
        )

    def _internal_ok(request: Request) -> bool:
        token = hooks.internal_token
        header = request.headers.get("authorization", "")
        if not token or header[:7].lower() != "bearer ":
            return False
        return hmac.compare_digest(header[7:].strip().encode(), token.encode())

    async def _admin(request: Request, fn: Callable[[], Any], status: int = 200) -> JSONResponse:
        if not _internal_ok(request):
            return _fail(ErrorCode.UNAUTHORIZED, "API nội bộ cần token hợp lệ", headers={"WWW-Authenticate": "Bearer"})
        try:
            data = await run_in_threadpool(fn)
        except IngestError as e:
            return _from_error(e)
        return JSONResponse({"status": "Success", "data": data}, status_code=status)

    a = hooks.admin

    @app.post("/internal/v1/partners")
    async def create_partner(request: Request, body: PartnerIn) -> JSONResponse:
        return await _admin(request, lambda: {"id": a.register_partner(body.name, body.username, body.password, body.format)}, 201)

    @app.get("/internal/v1/partners")
    async def partners(request: Request) -> JSONResponse:
        return await _admin(request, a.list_partners)

    @app.put("/internal/v1/partners/{partner_id}/hotels/{hotel_code}")
    async def put_hotel(request: Request, partner_id: int, hotel_code: str, body: HotelIn) -> JSONResponse:
        return await _admin(request, lambda: a.set_hotel(partner_id, hotel_code, body.hotelId, body.name))

    @app.put("/internal/v1/partners/{partner_id}/hotels/{hotel_code}/rooms/{room_code}")
    async def put_room(request: Request, partner_id: int, hotel_code: str, room_code: str, body: RoomIn) -> JSONResponse:
        return await _admin(request, lambda: a.set_room(partner_id, hotel_code, room_code, body.roomId, body.name))

    @app.put("/internal/v1/partners/{partner_id}/hotels/{hotel_code}/rate-plans/{code}")
    async def put_rate_plan(request: Request, partner_id: int, hotel_code: str, code: str, body: RatePlanIn) -> JSONResponse:
        return await _admin(request, lambda: a.set_rate_plan(partner_id, hotel_code, code, body.ratePlanId, body.name))

    @app.get("/internal/v1/partners/{partner_id}/catalog")
    async def catalog(request: Request, partner_id: int) -> JSONResponse:
        return await _admin(request, lambda: a.get_catalog(partner_id))

    return app
