---
module: wiring
---
# wiring - Implementation (tầng 3)

Đã code gì, ở đâu, lệch spec chỗ nào. Ghi qua tool `impl_link`.

## WIRE-S-001: main.py là điểm nối duy nhất; relay chạy nền trong cùng tiến trình; cấu hình từ biến INGEST_*
- spec_hash: 6f3644a2
- status: done
- code: src/ingest/main.py, src/ingest/config.py
- tests: tests/test_layers.py
- deviation:
- notes:
