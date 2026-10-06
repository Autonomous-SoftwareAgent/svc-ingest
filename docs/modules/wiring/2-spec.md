---
module: wiring
---
# wiring - Spec (tầng 2)

Design được tách thành yêu cầu, contract, tiêu chí nghiệm thu và task. Khung tự sinh từ design; điền qua tool `spec_fill`.

## WIRE-S-001: main.py là điểm nối duy nhất; relay chạy nền trong cùng tiến trình; cấu hình từ biến INGEST_*
- from: WIRE-D-001
- derived_from: 5e9dd106
- status: ready
- requirement: main.py là điểm nối duy nhất của ba lớp; cấu hình hoàn toàn từ biến môi trường INGEST_*; relay là tác vụ nền cùng tiến trình có thể tắt bằng cấu hình; khởi động tạo bảng, tắt thì dọn sạch.
- contract: build_app(settings=None, publisher=None, engine=None) -> FastAPI; build_hooks(settings, engine, cache) -> Hooks. Biến: INGEST_DATABASE_URL (bắt buộc), INGEST_PUBLISHER (kafka mặc định, log), INGEST_KAFKA_BOOTSTRAP_SERVERS (localhost:9092), INGEST_KAFKA_PUBLISH_TIMEOUT_SECONDS (15), INGEST_TOPIC_INVENTORY/RESTRICTIONS/RATES, INGEST_INTERNAL_TOKEN (trống = từ chối mọi API nội bộ), INGEST_MAX_BODY_BYTES (1048576), INGEST_MAX_DATE_SPAN_DAYS (730), INGEST_MAX_UPDATES_PER_REQUEST (10000), INGEST_CATALOG_CACHE_TTL_SECONDS (86400), INGEST_RELAY_ENABLED (true), INGEST_RELAY_INTERVAL_SECONDS (0.5), INGEST_RELAY_BATCH_SIZE (200). Chạy: uvicorn ingest.main:build_app --factory --port 8080.
- acceptance: tests/test_layers.py::test_nothing_imports_main_or_config_except_wiring; chạy thật bằng uvicorn và docker compose với nhà cung cấp mô phỏng (đã làm tay, xem STATUS).
- tasks:
  - [x] Nối và vòng đời
  - [ ] Công cụ migration (hiện create_all), chọn leader cho relay, chỉ số và giám sát
  - [ ] Chưa có test tự động cho vòng đời (lifespan) và kiểm cấu hình --check-config
