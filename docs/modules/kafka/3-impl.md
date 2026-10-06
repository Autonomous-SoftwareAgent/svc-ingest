---
module: kafka
---
# kafka - Implementation (tầng 3)

Đã code gì, ở đâu, lệch spec chỗ nào. Ghi qua tool `impl_link`.

## KAFK-S-001: KafkaPublisher: acks=all, producer idempotent, tạo lười và tạo lại sau lỗi
- spec_hash: 78ba4fd2
- status: done
- code: src/ingest/io/kafka.py, src/ingest/io/publishers.py
- tests: tests/test_kafka_rqm.py
- deviation:
- notes: Chỉ kiểm với broker một nút cục bộ.
