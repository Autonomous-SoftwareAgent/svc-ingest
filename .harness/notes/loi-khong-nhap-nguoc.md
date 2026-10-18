---
paths:
  - "src/ingest/core/**"
---
Đây là lớp logic nội bộ của ingest. Không nhập `ingest.io`, `ingest.normalize`, `ingest.main` hay thư viện Kafka (`aiokafka`); chỉ biết dạng chuẩn ở `contract.py`. Số nghiệp vụ lấy từ cấu hình `INGEST_*`, không viết cứng. `tests/test_layers.py` sẽ đỏ nếu nhập sai chiều.
