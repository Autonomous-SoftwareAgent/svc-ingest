---
module: kafka
prefix: KAFK
---
# kafka - Design (tầng 1)

Vì sao và cái gì: quyết định nghiệp vụ và kỹ thuật của module. Chỉ ghi qua tool `design_record` / `design_update`.

## KAFK-D-001: KafkaPublisher: acks=all, producer idempotent, tạo lười và tạo lại sau lỗi
- date: 2026-10-06
- status: accepted
- decision: io/kafka.py dùng aiokafka với acks="all", enable_idempotence=True, linger_ms=0, request_timeout bằng kafka_publish_timeout_seconds (mặc định 15). Producer được tạo ở lần phát đầu (có khóa asyncio), mỗi lần phát gói trong asyncio.wait_for với cùng thời hạn; MỌI lỗi (kể cả hết giờ) làm dừng và bỏ producer để lần sau tạo lại. publish gửi tới topic theo MessageKind (ingest.ari.inventory, ingest.ari.restrictions, ingest.ari.rates, đổi bằng INGEST_TOPIC_*), khóa = khóa phân vùng, header message-id. Không tạo topic: việc đó là của vận hành. LogPublisher (ghi log) và MemoryPublisher (test) là hai cổng phụ.
- rationale: Kafka chưa sẵn sàng lúc khởi động hay bị tạm dừng giữa chừng thì lần thử sau của relay vẫn nối lại được mà không cần khởi động lại dịch vụ. acks=all và idempotent để broker xác nhận là xác nhận thật. Chưa chọn broker production; chỉ kiểm với Kafka và Redpanda một nút cục bộ.
- impacts: Hết giờ không có nghĩa là broker chưa nhận: lần gửi đó vẫn có thể tới broker rồi bị gửi lại (phát lặp). Cụm nhiều nút, bảo mật và số phân vùng tối đa của broker chưa kiểm; trên Redpanda một nút nhỏ, topic của test phải được xóa vì có giới hạn số phân vùng.
