---
module: wiring
prefix: WIRE
---
# wiring - Design (tầng 1)

Vì sao và cái gì: quyết định nghiệp vụ và kỹ thuật của module. Chỉ ghi qua tool `design_record` / `design_update`.

## WIRE-D-001: main.py là điểm nối duy nhất; relay chạy nền trong cùng tiến trình; cấu hình từ biến INGEST_*
- date: 2026-10-06
- status: accepted
- decision: main.build_app dựng Settings (pydantic-settings, tiền tố INGEST_, đọc .env), engine (pool_pre_ping), TtlCache, các hook (build_hooks) rồi create_app. Lớp vào/ra không nhập lõi: ingest hook (chọn hàm chuẩn hóa theo định dạng của đối tác, rồi service.accept với sha256 của thân), authenticate, healthcheck và AdminHooks đều do main.py tiêm bằng functools.partial. Lúc khởi động (lifespan) gọi schema.create_all (chưa có công cụ migration) và, nếu INGEST_RELAY_ENABLED, tạo tác vụ asyncio chạy relay.run_forever; lúc tắt hủy tác vụ, đóng publisher, dispose engine. INGEST_PUBLISHER chọn "kafka" hay "log". Đối tác có định dạng chưa đăng ký thì hook ném RuntimeError (HTTP trả 503). python -m ingest.main --check-config kiểm cấu hình.
- rationale: Một điểm nối giữ cho ba lớp một chiều (test_layers cho phép main và config nhập mọi lớp, cấm lớp khác nhập ngược). Relay cùng tiến trình cho đơn giản ở bản đầu; hệ quả là mỗi bản dịch vụ chạy thêm sẽ chạy thêm một relay.
- impacts: Chạy nhiều bản dịch vụ sẽ có nhiều relay cùng đọc outbox (sinh tin lặp, chưa chọn leader). create_all không đổi cấu trúc bảng đã có. Biến môi trường: INGEST_DATABASE_URL (bắt buộc), INGEST_PUBLISHER, INGEST_KAFKA_BOOTSTRAP_SERVERS, INGEST_KAFKA_PUBLISH_TIMEOUT_SECONDS, INGEST_TOPIC_INVENTORY/RESTRICTIONS/RATES, INGEST_INTERNAL_TOKEN, INGEST_MAX_BODY_BYTES, INGEST_MAX_DATE_SPAN_DAYS, INGEST_MAX_UPDATES_PER_REQUEST, INGEST_CATALOG_CACHE_TTL_SECONDS, INGEST_RELAY_ENABLED, INGEST_RELAY_INTERVAL_SECONDS, INGEST_RELAY_BATCH_SIZE.
