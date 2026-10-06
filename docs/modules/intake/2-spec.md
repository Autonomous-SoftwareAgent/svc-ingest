---
module: intake
---
# intake - Spec (tầng 2)

Design được tách thành yêu cầu, contract, tiêu chí nghiệm thu và task. Khung tự sinh từ design; điền qua tool `spec_fill`.

## INTK-S-001: ACK chỉ sau khi commit: ghi lần gửi và outbox trong một transaction
- from: INTK-D-001
- derived_from: 87d7534b
- status: ready
- requirement: Chỉ trả ACK sau khi lần gửi và outbox đã commit trong một transaction; lưu lỗi thì không ACK; không gọi broker khi giữ transaction; không còn dữ liệu hợp lệ thì từ chối và không lưu gì.
- contract: service.accept(engine, cache, partner, trace_id, channel_id, body_hash, sub, received_at=None) -> AckResult(ticket_id, duplicate, row_errors). Ném IngestError: 31 (khách sạn lạ hoặc không có quyền), 12 (không có message nào, kèm lỗi từng mã lạ), 40 (xem INTK-S-002), 50 (SQLAlchemyError trong transaction hoặc hết 3 lần đua khóa). Bảng ghi: submission(ticket_id, partner_id, trace_id, body_hash, channel_id, hotel_code, received_at_us, messages, row_errors JSON) và outbox (message_id, ticket_id, kind, key, payload, created_at_us, attempts=0, sent_at_us=null).
- acceptance: test_core.py: test_accept_writes_submission_and_outbox_before_ack, test_everything_invalid_rejects_and_stores_nothing_so_trace_can_be_reused, test_hotel_not_allowed, test_save_failure_raises_and_never_acks, test_outbox_and_submission_commit_together; test_http.py::test_database_failure_is_never_acked.
- tasks:
  - [x] accept và transaction
  - [ ] Bọc lỗi DB ở các bước đọc trước transaction thành IngestError 50 (hiện lọt SQLAlchemyError thô, lớp HTTP vẫn trả 503)
  - [ ] Ca chưa có trong bản gốc: tiến trình chết giữa lúc ghi submission và outbox; mất kết nối DB giữa chừng trên PostgreSQL thật

## INTK-S-002: Chống trùng theo (đối tác, X-Trace-Id) kèm mã băm nội dung
- from: INTK-D-002
- derived_from: ceadda53
- status: ready
- requirement: Gửi lại cùng (đối tác, X-Trace-Id) và cùng nội dung thì trả đúng TicketId cũ, duplicate=true, không ghi thêm; khác nội dung thì từ chối mã 40; hai yêu cầu cùng khóa đồng thời chỉ một bên ghi.
- contract: Khóa duy nhất uq_submission_partner_trace (partner_id, trace_id); body_hash = sha256 của thân thô. Trùng cùng mã băm: AckResult(ticket cũ, True, row_errors cũ). Khác mã băm: IngestError(40) (HTTP 409). Đua khóa: bắt IntegrityError, đọc lại hàng của bên thắng rồi xử lý như trên, tối đa 3 lần rồi 50. Khóa tính riêng từng đối tác.
- acceptance: test_core.py: test_same_trace_and_body_returns_same_ticket_without_new_messages, test_duplicate_returns_same_row_errors, test_same_trace_different_body_is_conflict, test_same_trace_for_different_partners_is_independent; test_http.py: test_resend_same_key_and_body_returns_same_ticket, test_same_key_different_body_is_409; test_concurrency.py::test_same_trace_sent_concurrently_gets_one_ticket_and_one_set_of_messages (cần PostgreSQL).
- tasks:
  - [x] Chống trùng và đua khóa
  - [ ] Xác nhận khóa chống trùng với nhà cung cấp thật và ai thêm X-Trace-Id
  - [ ] Chưa có trong bản gốc: hai thân khác nhau cùng trace đồng thời; dạng UUID khác nhau (hoa, không gạch, ngoặc) cùng một khóa

## INTK-S-003: Đổi mã sang mã nội bộ, bỏ dòng mã lạ, messageId ổn định, khóa phân vùng theo phòng và gói giá
- from: INTK-D-003
- derived_from: 8fa5f56a
- status: ready
- requirement: Đổi mã sang mã nội bộ bằng danh mục; phòng lạ bỏ mọi update của phòng; gói giá lạ bỏ restrictions và rates nhưng giữ inventory; mỗi mã lạ báo một lần mã 10; messageId ổn định; khóa phân vùng theo phòng (và gói giá).
- contract: messageId = uuid5(TicketId, vị trí trong danh sách update); key = "{hotelId}:{roomId}" (inventory) hoặc "{hotelId}:{roomId}:{ratePlanId}" (restrictions, rates). Payload JSON gọn: messageId, ticketId, kind, hotelId, roomId, ratePlanId|null, dateFrom, dateTo, receivedAt (ISO, UTC), channelId|null, data. RowError mã 10: shortText "mã phòng lạ: X" hoặc "mã gói giá lạ: X", path "phòng=X" hoặc "gói giá=X".
- acceptance: test_core.py: test_message_shape_keys_and_internal_ids, test_message_ids_are_stable_uuid5_of_ticket_and_position, test_unknown_room_is_dropped_others_go_with_code_10, test_unknown_rate_plan_drops_restrictions_and_rates_but_keeps_inventory, test_unknown_code_reported_once_even_if_used_many_times.
- tasks:
  - [x] Đổi mã và dựng message
  - [ ] Hợp đồng message thật với bên nhận (Inventory, worker) chưa có; định dạng hiện do dịch vụ tự đặt
