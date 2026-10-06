---
module: kafka
---
# kafka - Spec (tầng 2)

Design được tách thành yêu cầu, contract, tiêu chí nghiệm thu và task. Khung tự sinh từ design; điền qua tool `spec_fill`.

## KAFK-S-001: KafkaPublisher: acks=all, producer idempotent, tạo lười và tạo lại sau lỗi
- from: KAFK-D-001
- derived_from: a69c9e99
- status: ready
- requirement: Chỉ trả về khi broker xác nhận; lỗi hoặc hết giờ thì ném và lần sau tạo lại producer; Kafka chưa sẵn sàng lúc khởi động hay tạm dừng giữa chừng không làm dịch vụ phải khởi động lại.
- contract: KafkaPublisher(bootstrap_servers, topics: dict[MessageKind, str], client_id="ingest", publish_timeout_seconds=15.0). publish(kind, key, value, message_id): gửi tới topics[kind], khóa = key (utf-8), header ("message-id", id). Producer: acks="all", enable_idempotence=True, linger_ms=0. Lỗi (kể cả asyncio.TimeoutError) -> dừng producer rồi ném lại. close() dừng producer. Topic mặc định: ingest.ari.inventory, ingest.ari.restrictions, ingest.ari.rates; không tự tạo topic.
- acceptance: test_kafka_rqm.py (cần broker thật và container để docker pause): ba kịch bản tạm dừng, khởi động lại, tin lặp đều giao đủ tin đã ACK và worker tham chiếu không áp dụng trùng.
- tasks:
  - [x] Phát qua aiokafka và kiểm với Kafka một nút cục bộ
  - [ ] Redpanda, cụm nhiều nút, bảo mật, tạo topic: chưa kiểm
  - [ ] Chưa có test đơn vị không cần broker (producer giả) trong bản gốc
