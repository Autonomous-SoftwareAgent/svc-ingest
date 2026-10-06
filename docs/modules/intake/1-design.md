---
module: intake
prefix: INTK
---
# intake - Design (tầng 1)

Vì sao và cái gì: quyết định nghiệp vụ và kỹ thuật của module. Chỉ ghi qua tool `design_record` / `design_update`.

## INTK-D-001: ACK chỉ sau khi commit: ghi lần gửi và outbox trong một transaction
- date: 2026-10-06
- status: accepted
- decision: core/service.accept làm theo thứ tự: tìm lần gửi cũ theo (đối tác, trace_id); kiểm quyền khách sạn và đổi mã qua cache; dựng message (_build); nếu không còn message nào thì ném mã 12 và KHÔNG lưu gì; rồi trong MỘT transaction insert submission và insert outbox; chỉ khi commit xong mới trả AckResult. Không gọi broker hay mạng khi đang giữ transaction. Lỗi lưu (SQLAlchemyError) ném IngestError mã 50, không ACK. Mã khách sạn lạ hoặc không có quyền cùng trả mã 31 (không phân biệt để khỏi dò mã).
- rationale: Yêu cầu RQM: ACK chỉ nghĩa là đã nhận, đã kiểm sơ bộ, đã lưu an toàn. Ghi hai bảng cùng transaction để không có ACK mà thiếu message, hay message mà thiếu lần gửi. Phương án đã bỏ: phát thẳng lên Kafka trong request (mất dữ liệu đã ACK khi Kafka chết).
- impacts: Các bước đọc trước transaction (tìm lần gửi cũ, đọc danh mục) nằm NGOÀI try của accept: lỗi kết nối DB ở đó lọt ra dạng SQLAlchemyError thô; lớp HTTP vẫn đổi thành 503 mã 50 (đã đo).

## INTK-D-002: Chống trùng theo (đối tác, X-Trace-Id) kèm mã băm nội dung
- date: 2026-10-06
- status: accepted
- decision: Khóa chống trùng là (partner_id, trace_id), ràng buộc duy nhất uq_submission_partner_trace; kèm sha256 của thân yêu cầu thô (body_hash). Cùng khóa cùng mã băm: trả đúng TicketId và row_errors cũ, duplicate=true, không ghi thêm. Cùng khóa khác mã băm: IngestError mã 40 (HTTP 409), không ghi gì. Hai yêu cầu cùng khóa chạy đồng thời: bên thua gặp IntegrityError, đọc lại lần gửi của bên thắng rồi trả lại như gửi trùng; thử tối đa 3 lần. Lần gửi bị từ chối (mã 12, 31...) không để lại hàng nào nên cùng trace dùng lại được. Khóa tính theo từng đối tác: hai đối tác dùng cùng trace không đụng nhau.
- rationale: Nhà cung cấp gửi lại khi không nhận được ACK; gửi lại không được nhân đôi cập nhật. Mã băm phân biệt gửi lại thật với dùng nhầm khóa cho nội dung khác. Giả định: khóa chống trùng là X-Trace-Id kèm đối tác, CHƯA xác nhận với nhà cung cấp thật.
- impacts: Đổi một khoảng trắng trong thân cũng là nội dung khác (băm trên byte thô). Ai thêm X-Trace-Id (nhà cung cấp hay cổng) chưa chốt.

## INTK-D-003: Đổi mã sang mã nội bộ, bỏ dòng mã lạ, messageId ổn định, khóa phân vùng theo phòng và gói giá
- date: 2026-10-06
- status: accepted
- decision: Mã khách sạn, phòng, gói giá của đối tác được đổi sang mã nội bộ bằng bản sao danh mục (cache 24 giờ theo (đối tác, khách sạn); không nhớ trường hợp "không có quyền"). Phòng lạ: bỏ mọi update của phòng đó; gói giá lạ: bỏ restrictions và rates nhưng GIỮ inventory; mỗi mã lạ báo một lần với mã 10 kèm đường dẫn "phòng=..." hoặc "gói giá=...". messageId = uuid5(TicketId, vị trí update) nên cùng lần gửi, cùng vị trí thì cùng ID. Khóa phân vùng = "hotelId:roomId" (inventory) hoặc "hotelId:roomId:ratePlanId" (restrictions, rates). Payload gồm messageId, ticketId, kind, hotelId, roomId, ratePlanId, dateFrom, dateTo, receivedAt, channelId, data. Ingest không giữ tồn hay giá hiện tại.
- rationale: Theo mô tả: mã lạ thì bỏ dòng (mã 10), khách sạn lạ thì từ chối cả yêu cầu. Khóa phân vùng theo phòng để giữ thứ tự các cập nhật của cùng một phòng. messageId ổn định để bên nhận khử trùng khi phát lặp. Định dạng message do dịch vụ tự đặt, CHƯA có hợp đồng thật với bên nhận.
- impacts: Sửa danh mục ở tiến trình khác thì tiến trình này thấy muộn tới hết hạn cache (tới 24 giờ). Khóa phân vùng khác nhau giữa inventory và restrictions/rates nên không có thứ tự giữa các loại.
