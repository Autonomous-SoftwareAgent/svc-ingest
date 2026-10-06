---
module: relay
---
# relay - Spec (tầng 2)

Design được tách thành yêu cầu, contract, tiêu chí nghiệm thu và task. Khung tự sinh từ design; điền qua tool `spec_fill`.

## RELY-S-001: Relay phát theo thứ tự id, chỉ đánh dấu đã gửi khi broker xác nhận, gặp lỗi thì dừng
- from: RELY-D-001
- derived_from: 29ff4cc5
- status: ready
- requirement: Relay phát outbox theo id tăng dần, chỉ ghi sent_at_us sau khi broker xác nhận, gặp lỗi thì tăng attempts của hàng lỗi và dừng đợt; lần sau thử lại từ hàng đó.
- contract: drain_once(engine, publisher, limit=200) -> số hàng đã được xác nhận; pending(engine) -> số hàng chưa gửi; run_forever(engine, publisher, interval, limit) chạy tới khi bị hủy, nuốt lỗi bất ngờ (ghi log) và ngủ interval khi đợt chưa đầy. Chọn hàng: sent_at_us IS NULL ORDER BY id LIMIT limit (chỉ hàng đã commit).
- acceptance: test_relay.py: test_drain_publishes_in_outbox_order_and_marks_sent, test_failure_stops_keeps_order_and_resumes_without_loss, test_failure_in_the_middle_does_not_skip_later_messages, test_attempts_counter_increases_on_failure, test_run_forever_drains_and_can_be_cancelled; test_kafka_rqm.py::test_kafka_paused_then_resumed_delivers_everything_acked.
- tasks:
  - [x] Relay cơ bản
  - [ ] Khoảng lùi dần, giới hạn số lần thử, hàng chờ lỗi, chọn leader khi nhiều bản (xem P-003)
  - [ ] Chưa có trong bản gốc: relay không thấy hàng của transaction chưa commit (PostgreSQL); relay sống sót lỗi DB tạm thời trong run_forever

## RELY-S-002: Giao nhận ít nhất một lần: phát lặp là chấp nhận được, bên nhận khử trùng theo messageId
- from: RELY-D-002
- derived_from: cdc5578f
- status: ready
- requirement: Giao nhận ít nhất một lần: khi phát lặp, lần gửi lại mang cùng messageId, cùng khóa và cùng nội dung; không có tình huống nào làm mất message đã ACK.
- contract: Hàng outbox giữ nguyên message_id và payload qua mọi lần thử. Phát lặp xảy ra khi chết sau xác nhận trước khi đánh dấu, khi ghi dấu lỗi, hoặc khi lần gửi hết giờ vẫn tới broker. Bên nhận khử trùng theo messageId (khóa chính).
- acceptance: test_relay.py::test_crash_after_publish_before_mark_resends_same_message_id; test_kafka_rqm.py: test_service_restart_with_unsent_outbox_still_delivers, test_duplicate_delivery_does_not_apply_twice (worker tham chiếu: áp dụng đúng một lần).
- tasks:
  - [x] Kịch bản RQM với Kafka cục bộ
  - [ ] Redpanda: chỉ chạy bằng tay (xem STATUS)
  - [ ] Bên nhận thật chưa có
