---
module: relay
---
# relay - Implementation (tầng 3)

Đã code gì, ở đâu, lệch spec chỗ nào. Ghi qua tool `impl_link`.

## RELY-S-001: Relay phát theo thứ tự id, chỉ đánh dấu đã gửi khi broker xác nhận, gặp lỗi thì dừng
- spec_hash: 87caa46e
- status: done
- code: src/ingest/core/relay.py
- tests: tests/test_relay.py, tests/test_kafka_rqm.py
- deviation:
- notes: Giả định một relay; xem P-003.

## RELY-S-002: Giao nhận ít nhất một lần: phát lặp là chấp nhận được, bên nhận khử trùng theo messageId
- spec_hash: 396d1264
- status: done
- code: src/ingest/core/relay.py, src/ingest/core/service.py
- tests: tests/test_relay.py, tests/test_kafka_rqm.py
- deviation:
- notes:
