---
module: normalize
---
# normalize - Implementation (tầng 3)

Đã code gì, ở đâu, lệch spec chỗ nào. Ghi qua tool `impl_link`.

## NORM-S-001: Mỗi định dạng của nhà cung cấp là một module tự đăng ký; lỗi một dòng khác lỗi cả gói
- spec_hash: 583d88fe
- status: deviated
- code: src/ingest/normalize/__init__.py, src/ingest/normalize/registry.py, src/ingest/normalize/inventory_rates_json.py
- tests: tests/test_normalize.py, tests/test_layers.py
- deviation: JSON lồng cực sâu làm json.loads ném RecursionError (không phải ValueError) nên lọt ra khỏi parse thay vì thành IngestError mã 21; lớp HTTP bắt và trả 503 mã 50. Đo bằng test bàn giao T-153 và T-355.
- notes:

## NORM-S-002: Quy ước đọc gói inventory-rates-json: bỏ trường không gửi, tách theo thứ trong tuần, giữ giá dạng chữ
- spec_hash: fc909552
- status: done
- code: src/ingest/normalize/inventory_rates_json.py
- tests: tests/test_normalize.py
- deviation:
- notes: Quy ước theo mô tả của người dùng, chưa kiểm với nhà cung cấp thật.
