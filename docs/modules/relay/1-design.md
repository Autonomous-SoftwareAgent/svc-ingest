---
module: relay
prefix: RELY
---
# relay - Design (tầng 1)

Vì sao và cái gì: quyết định nghiệp vụ và kỹ thuật của module. Chỉ ghi qua tool `design_record` / `design_update`.

## RELY-D-001: Relay phát theo thứ tự id, chỉ đánh dấu đã gửi khi broker xác nhận, gặp lỗi thì dừng
- date: 2026-10-06
- status: accepted
- decision: drain_once lấy tối đa `limit` (mặc định 200) hàng chưa gửi (sent_at_us rỗng) sắp theo id tăng dần, phát từng hàng qua cổng Publisher, và chỉ sau khi publish trả về mới ghi sent_at_us. Gặp lỗi ở một hàng thì tăng attempts của hàng đó và DỪNG cả đợt, không bỏ qua để phát hàng sau. run_forever lặp drain_once, ngủ relay_interval_seconds (mặc định 0,5 giây) khi đợt không đầy; lỗi bất ngờ chỉ ghi log rồi thử lại, hủy tác vụ thì thoát. Giả định v1: CHỈ MỘT relay chạy.
- rationale: Bỏ qua message lỗi để phát tiếp sẽ đảo thứ tự trong cùng khóa phân vùng, nên chấp nhận một message lỗi chặn mọi message sau (đánh đổi đã ghi ở P-003). Đánh dấu sau khi broker xác nhận là yêu cầu RQM: chết giữa chừng thì lần sau gửi lại, không mất.
- impacts: Chưa có khoảng lùi dần, chưa giới hạn số lần thử, chưa có hàng chờ lỗi, chưa chọn leader khi chạy nhiều bản. id cấp lúc ghi chứ không phải lúc commit nên hai lần gửi đồng thời có thể phát theo thứ tự khác thứ tự commit.

## RELY-D-002: Giao nhận ít nhất một lần: phát lặp là chấp nhận được, bên nhận khử trùng theo messageId
- date: 2026-10-06
- status: accepted
- decision: Relay không đảm bảo đúng một lần. Message có thể tới bên nhận hai lần khi: relay chết sau khi broker nhận và trước khi ghi sent_at_us; ghi dấu lỗi; lần gửi hết giờ nhưng vẫn tới broker rồi relay gửi lại (đã đo với Kafka cục bộ). Lần gửi lại luôn dùng cùng messageId (cùng payload, cùng khóa). Bên nhận phải khử trùng theo messageId; worker tham chiếu trong tests/test_kafka_rqm.py dùng khóa chính message_id.
- rationale: Đúng một lần cần giao dịch bao cả DB và Kafka mà hạ tầng này không có. Ít nhất một lần cộng ID ổn định là cách rẻ nhất đạt tiêu chí nghiệm thu RQM (Kafka dừng, khởi động lại, tin lặp vẫn giao đủ, không cập nhật trùng).
- impacts: Chưa có bên nhận thật nên việc khử trùng của bên nhận CHƯA kiểm ngoài worker tham chiếu. Hai relay chạy cùng lúc không làm mất tin nhưng sẽ sinh nhiều tin lặp (đã đo).
