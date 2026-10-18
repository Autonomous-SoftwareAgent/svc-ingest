---
name: lam-viec-trong-ingest
description: "Dùng trước khi sửa mã trong ingest: đọc gì, đặt mã đúng lớp nào, quy tắc ACK và outbox, chạy test nào, cập nhật tài liệu thế nào"
harness-files: ["^src/"]
harness-reads: ["docs/agent/CONVENTIONS.md"]
---
## Trước khi sửa
1. Đọc `CLAUDE.md` và `docs/agent/STATUS.md` (hook bắt buộc), rồi `docs/agent/CONVENTIONS.md` trước khi viết mã.
2. Việc đụng dịch vụ khác thì ghi tờ vào `docs/handoff/`, không tự sửa.

## Đặt mã đúng lớp (`src/ingest/`)
- `io/`: giao thức, xác thực, đổi mã lỗi sang HTTP, phát Kafka. Không có nghiệp vụ, không biết định dạng của đối tác.
- `normalize/`: mỗi định dạng của đối tác MỘT module tự đăng ký bằng `@register("<tên>")`. Thêm định dạng là thêm một tệp, không sửa tệp đang có.
- `contract.py`: hợp đồng chuẩn (`Update`, `NormalizedSubmission`, `ErrorCode`, `IngestError`...).
- `core/`: nghiệp vụ (kiểm quyền, đổi mã, chống trùng, outbox, relay). Không nhập `io/` hay `normalize/`, không nhập thư viện Kafka.
- Chỉ `main.py` và `config.py` nối ba lớp. Số nghiệp vụ và giới hạn là cấu hình `INGEST_*`, không viết cứng.

## Quy tắc đã chốt (không đổi khi chưa hỏi người dùng)
- ACK (202 kèm `ticketId`) chỉ trả SAU KHI dữ liệu đã nằm bền trong outbox và transaction đã commit. Lưu lỗi thì trả lỗi, không ACK.
- Phát ít nhất một lần: relay chỉ đánh dấu đã gửi khi Kafka xác nhận; message có ID ổn định để bên nhận khử trùng.
- Trường nhà cung cấp không gửi thì bỏ qua, không hiểu là 0. Mã phòng hoặc gói giá lạ: bỏ dòng đó, ghi lỗi mã 10, phần hợp lệ vẫn đi. Không còn dữ liệu hợp lệ nào: từ chối cả lần gửi.
- Không giữ tồn hay giá hiện tại; không tự gán tiền tệ. Log chỉ ghi số đếm và mã, không ghi nội dung gói, mật khẩu, token.
- Điều chưa kiểm với nhà cung cấp thật hay Kafka production phải ghi là chưa kiểm.

## Kiểm
- `pip install -e ".[dev]"` rồi `python -m pytest`. Có `INGEST_TEST_DATABASE_URL` thì chạy trên PostgreSQL; thiếu thì SQLite và test đồng thời bị bỏ qua có nêu lý do.
- `tests/test_layers.py` giữ ranh giới ba lớp bằng quét import: đừng sửa test cho qua.
- Tài liệu: `node .claude/modules/core/cli/cli.js --service ingest check` (từ `BSN_/`). Ba tầng, `service.yaml`, sơ đồ chỉ ghi bằng công cụ MCP với `service="ingest"`.
- Cuối việc thêm một dòng nhật ký vào `docs/agent/STATUS.md`. Commit ở repo ingest; không `git push` khi người dùng chưa bảo.
