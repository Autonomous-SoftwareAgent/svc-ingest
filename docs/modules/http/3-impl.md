---
module: http
---
# http - Implementation (tầng 3)

Đã code gì, ở đâu, lệch spec chỗ nào. Ghi qua tool `impl_link`.

## HTTP-S-001: POST /v1/inventory-rates: thứ tự kiểm, giới hạn kích thước và bảng đổi mã lỗi sang HTTP
- spec_hash: aec5fb9f
- status: done
- code: src/ingest/io/http.py
- tests: tests/test_http.py
- deviation:
- notes:

## HTTP-S-002: API nội bộ mặc định từ chối, và /healthz kiểm cơ sở dữ liệu thật
- spec_hash: a620c138
- status: deviated
- code: src/ingest/io/http.py, src/ingest/main.py
- tests: tests/test_http.py
- deviation: FastAPI kiểm thân (pydantic) trước khi chạy hàm kiểm token nên POST hay PUT /internal/v1/... với thân sai và không có token nhận 400 mã 25 thay vì 401. Đo bằng test bàn giao T-370.
- notes:
