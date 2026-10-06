---
module: catalog
---
# catalog - Implementation (tầng 3)

Đã code gì, ở đâu, lệch spec chỗ nào. Ghi qua tool `impl_link`.

## CATL-S-001: Danh mục chỉ là bản sao để đổi mã; nạp qua API nội bộ; cache 24 giờ theo tiến trình
- spec_hash: 515efc45
- status: done
- code: src/ingest/core/catalog.py, src/ingest/core/cache.py
- tests: tests/test_core.py, tests/test_http.py
- deviation:
- notes:
