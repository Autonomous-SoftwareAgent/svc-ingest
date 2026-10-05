# CONVENTIONS: ingest

Mục nào chưa chốt thì để `TBD`, không tự đoán.

- Ngôn ngữ / framework: Python 3.11+ (đã chạy với 3.13), FastAPI, Pydantic v2, SQLAlchemy 2 Core, psycopg 3, aiokafka.
- Database: PostgreSQL (quy tắc chung của hệ). Bảng tạo bằng `create_all` lúc khởi động; công cụ migration: TBD.
- Message broker: Kafka qua cổng `Publisher`; broker production: TBD (D-002).
- Cách chạy test: `python -m pytest` (xem `CLAUDE.md` về PostgreSQL và Kafka thật).

## Ba lớp (ánh xạ vào mã)
| Lớp | Thư mục | Quy tắc import |
|---|---|---|
| Hợp đồng chuẩn | `src/ingest/contract.py` | không import module nào khác của dịch vụ |
| Vào/ra | `src/ingest/io/` | chỉ `contract` và `io` |
| Chuẩn hóa | `src/ingest/normalize/` | chỉ `contract` và `normalize.registry`; module định dạng không import nhau; không dùng thư viện web hay Kafka |
| Logic nội bộ | `src/ingest/core/` | chỉ `contract` và `core`; không dùng fastapi, starlette, uvicorn, httpx, aiokafka |
| Nối | `main.py`, `config.py` | được import mọi lớp; không lớp nào import ngược chúng |

- Không dùng import tương đối trong `src/ingest` (test quét import không bắt được nếu dùng).
- Nối lớp bằng tiêm hàm: `io/http.py` nhận `Hooks` (xác thực, nhận lô, kiểm sức khỏe, API nội bộ) từ `main.py`, nên không import hai lớp kia.
- Test giữ ranh giới: `tests/test_layers.py`.

## Quy ước dữ liệu và giao nhận
- Gói vào: JSON `inventory-rates-json`; header `Authorization: Basic`, `X-Trace-Id` (UUID, bắt buộc), `X-Channel-Id` (ghi vào nhật ký và message).
- Phản hồi: `{"status": "Success", "data": {"ticketId", "duplicate"}, "errors": [...]}` (202) hoặc `{"status": "Fail", "errors": [{"code", "shortText", "path"?}]}`.
- Mã lỗi (`ErrorCode`): 10 mã phòng/gói giá lạ (bỏ dòng), 12 không còn dữ liệu hợp lệ, 20 dòng sai cấu trúc, 21 không đọc được gói, 22 X-Trace-Id sai, 23 quá lớn, 24 quá nhiều update, 25 tham số API nội bộ sai, 30 sai đăng nhập, 31 khách sạn lạ hoặc không có quyền, 40 trùng khóa khác nội dung, 41 xung đột, 42 không thấy, 50 không lưu được. Chỉ mã 10 do nghiệp vụ quy định; còn lại do dịch vụ tự đặt.
- Trạng thái HTTP theo mã (`io/http.py`, `_STATUS`): 400 (12, 20, 21, 22, 25), 401 (30, 31), 404 (42), 409 (40, 41), 413 (23, 24), 503 (50).
- Message phát ra: JSON với `messageId`, `ticketId`, `kind`, `hotelId`, `roomId`, `ratePlanId` (null với tồn), `dateFrom`, `dateTo` (tính cả hai đầu), `receivedAt` (UTC), `channelId`, `data`. Header Kafka `message-id`. Tiền là chuỗi số thập phân, không dùng số thực.
- Khóa phân vùng: `<hotelId>:<roomId>` cho tồn; thêm `:<ratePlanId>` cho điều kiện bán và giá.
- Mật khẩu đối tác chỉ lưu dạng băm scrypt. API nội bộ cần `Authorization: Bearer` khớp `INGEST_INTERNAL_TOKEN`; thiếu cấu hình thì từ chối hết.
- Số nghiệp vụ (giới hạn kích thước, số ngày, số update, thời hạn cache, nhịp relay) là cấu hình `INGEST_*` ở `config.py`.

## Triển khai
- Theo skill `cicd` (build local, Docker Hub private, VM GCP). Chưa chỉnh skill đó cho ingest và chưa thử đường deploy.
- Image không chứa secret; secret chỉ ở `.env` trên VM (`.env.example` chỉ có tên biến).
