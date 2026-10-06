---
module: intake
---
# intake - Implementation (tầng 3)

Đã code gì, ở đâu, lệch spec chỗ nào. Ghi qua tool `impl_link`.

## INTK-S-001: ACK chỉ sau khi commit: ghi lần gửi và outbox trong một transaction
- spec_hash: 197ef364
- status: deviated
- code: src/ingest/core/service.py, src/ingest/core/schema.py
- tests: tests/test_core.py, tests/test_http.py
- deviation: Các bước đọc trước transaction (_find_existing, _maps) nằm ngoài try của accept: kết nối DB chết ở đó làm SQLAlchemyError lọt ra thô thay vì IngestError 50 (lớp HTTP vẫn trả 503 mã 50 và không ACK). Đo trên PostgreSQL thật bằng test bàn giao T-414.
- notes:

## INTK-S-002: Chống trùng theo (đối tác, X-Trace-Id) kèm mã băm nội dung
- spec_hash: 59b9a3d2
- status: done
- code: src/ingest/core/service.py, src/ingest/core/schema.py
- tests: tests/test_core.py, tests/test_http.py, tests/test_concurrency.py
- deviation:
- notes:

## INTK-S-003: Đổi mã sang mã nội bộ, bỏ dòng mã lạ, messageId ổn định, khóa phân vùng theo phòng và gói giá
- spec_hash: d340e407
- status: done
- code: src/ingest/core/service.py
- tests: tests/test_core.py
- deviation:
- notes:
