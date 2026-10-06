---
module: http
prefix: HTTP
---
# http - Design (tầng 1)

Vì sao và cái gì: quyết định nghiệp vụ và kỹ thuật của module. Chỉ ghi qua tool `design_record` / `design_update`.

## HTTP-D-001: POST /v1/inventory-rates: thứ tự kiểm, giới hạn kích thước và bảng đổi mã lỗi sang HTTP
- date: 2026-10-06
- status: accepted
- decision: Thứ tự: xác thực Basic (thiếu hoặc sai dạng 401 mã 30, sai mật khẩu 401 mã 30, kèm WWW-Authenticate: Basic) -> X-Trace-Id phải là UUID (400 mã 22; mọi dạng UUID hợp lệ được chuẩn về dạng gạch ngang chữ thường) -> đọc thân có giới hạn max_body_bytes (mặc định 1 MiB; vượt thì 413 mã 23, tính cả khi không có Content-Length) -> X-Channel-Id tùy chọn (cắt khoảng trắng, tối đa 128 ký tự) -> hook ingest. Thành công: 202 {"status":"Success","data":{"ticketId","duplicate"},"errors":[...lỗi từng dòng]}. Lỗi: {"status":"Fail","errors":[{code,shortText,path?}]}. Bảng đổi: 20,21,22,12,25 -> 400; 23,24 -> 413; 30,31 -> 401; 42 -> 404; 40,41 -> 409; 50 -> 503; lỗi bất ngờ -> 503 mã 50 kèm "không lưu được, hãy gửi lại" (không lộ chi tiết). Log chỉ ghi tên đối tác, TicketId, duplicate và số lỗi dòng, không ghi nội dung hay thông tin xác thực.
- rationale: Xác thực trước khi đọc thân để người lạ không bắt dịch vụ đọc và phân tích thân lớn. Mã HTTP theo mô tả: sai quyền theo khách sạn trả 401, sai đóng gói trả 400. Lớp vào/ra không biết nghiệp vụ nên mọi việc nghiệp vụ đi qua hook do main.py tiêm.
- impacts: Trả 401 cho khách sạn lạ là theo mô tả của người dùng, chưa xác nhận với nhà cung cấp (P-006). Thân JSON lồng cực sâu làm lọt RecursionError và bị trả 503 thay vì 400.

## HTTP-D-002: API nội bộ mặc định từ chối, và /healthz kiểm cơ sở dữ liệu thật
- date: 2026-10-06
- status: accepted
- decision: /internal/v1/... cần Authorization: Bearer khớp đúng INGEST_INTERNAL_TOKEN (so bằng hmac.compare_digest); chưa đặt biến đó thì mọi lời gọi bị 401 mã 30 (kèm WWW-Authenticate: Bearer). Gồm: POST /partners (201), GET /partners, PUT /partners/{id}/hotels/{hotel_code}, PUT .../rooms/{room_code}, PUT .../rate-plans/{code}, GET /partners/{id}/catalog. Thân là mô hình pydantic cấm trường lạ; sai thì 400 mã 25 và thông báo chỉ nêu vị trí và lý do, không lặp lại giá trị (có thể là mật khẩu). GET /healthz chạy SELECT 1 và trả {"database":"ok","outboxPending":n} (200), lỗi DB thì 503 mã 50.
- rationale: Mặc định từ chối để quên đặt token không làm API quản trị thành công khai. healthz kiểm phụ thuộc thật thay vì chỉ cho biết tiến trình còn sống, và số outboxPending là chỉ số vận hành duy nhất hiện có.
- impacts: Thân của API nội bộ được kiểm trước token (do FastAPI) nên người chưa đăng nhập có thể nhận 400 thay vì 401 với thân sai (đã đo). Chưa có chỉ số, cảnh báo hay phân quyền chi tiết cho API nội bộ.
