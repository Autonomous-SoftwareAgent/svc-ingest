# DECISIONS: ingest

Chỉ thêm bản ghi mới; không sửa bản ghi cũ (đánh dấu `superseded by D-xxx`). Mẫu: ngày, trạng thái, bối cảnh, quyết định, hệ quả.

## D-001: Ingest là dịch vụ riêng, Python, tách hẳn các "ingest" khác
- Ngày: 2026-10-05
- Trạng thái: accepted (người dùng chốt).
- Bối cảnh: sơ đồ tham chiếu (`BSN_/docs/tham-chieu/02-engineering-view.md`) có thành phần Ingestion nhận tồn và giá nhà cung cấp. Trên máy còn hai hệ khác cũng có "ingest" (DA08 `rag-worker`, `D:\Training\ingest_service`) nhưng nạp tài liệu vào Qdrant cho RAG, khác hẳn.
- Quyết định: một repo riêng `system_service/ingest`, Python, ba lớp theo `BSN_/CLAUDE.md`, không dùng chung mã hay tiến trình với các hệ kia (chỉ dùng chung cách làm). Hệ thống tham chiếu mà người dùng mô tả được coi là tham khảo bên ngoài, không đối chiếu với mã của nó.
- Hệ quả: bản làm trước đó (viết khi chưa được duyệt, theo giả định tồn/giá chung chung) bị gỡ hẳn; bản sao lưu ở `BSN_/.backup/ingest-cu-2026-10-05/`.

## D-002: Phát lên Kafka bằng cổng Publisher; broker production chưa chọn
- Ngày: 2026-10-05
- Trạng thái: accepted (cách làm); broker production còn mở.
- Bối cảnh: yêu cầu RQM nêu rõ tiến trình nền gửi outbox lên Kafka. Payment Hub cũng dùng Kafka (D-008 của nó), nhưng chưa chọn broker cho production.
- Quyết định: `contract.Publisher` là cổng; bản thật dùng `aiokafka` (`acks=all`, producer idempotent) ở `io/kafka.py`; ba topic theo loại message (cấu hình `INGEST_TOPIC_*`). Khóa phân vùng: `<hotelId>:<roomId>` cho tồn, thêm `:<ratePlanId>` cho điều kiện bán và giá. Tạo sẵn topic là việc của vận hành (broker cục bộ tự tạo).
- Hệ quả: kiểm với broker `apache/kafka` một nút cục bộ, KHÔNG phải broker production. Chưa làm JetStream, webhook ra, Kafka vào; thêm sau bằng một tệp mới, không sửa tệp cũ.

## D-003: ACK sau commit, transactional outbox, phát ít nhất một lần
- Ngày: 2026-10-05
- Trạng thái: accepted (RQM của người dùng).
- Quyết định: ghi `submission` và `outbox` trong một transaction, commit xong mới trả ACK kèm `TicketId`. Relay đọc outbox theo `id`, gửi, chỉ đánh dấu đã gửi khi Kafka xác nhận; gặp lỗi thì dừng để giữ thứ tự. Mỗi message có `messageId` ổn định (`uuid5(ticketId, vị trí)`), bên nhận khử trùng theo `messageId`.
- Hệ quả: có thể có message lặp (đã đo: khi Kafka bị tạm dừng, lần gửi hết giờ vẫn có thể tới broker rồi bị gửi lại). Chỉ chạy MỘT relay tại một thời điểm (chưa chọn leader); lỗi ở một message chặn các message sau (head-of-line).

## D-004: Khóa chống trùng là (đối tác, X-Trace-Id) kèm mã băm nội dung
- Ngày: 2026-10-05
- Trạng thái: accepted nhưng là GIẢ ĐỊNH (người dùng chọn mặc định, chưa xác nhận với nhà cung cấp).
- Quyết định: `X-Trace-Id` (bắt buộc, UUID) làm khóa; cùng khóa và cùng nội dung (sha256) trả đúng `TicketId` cũ; cùng khóa nhưng nội dung khác trả 409. Lần gửi bị từ chối (không còn dữ liệu hợp lệ) không được lưu nên cùng khóa có thể gửi lại bản đã sửa.
- Hệ quả: nếu nhà cung cấp thật dùng khóa khác thì đổi `service.accept` và `io/http.py`.

## D-005: Ingest không giữ tồn hay giá hiện tại; thứ tự theo giờ nhận
- Ngày: 2026-10-05
- Trạng thái: accepted (theo mô tả của người dùng); điểm yếu ghi thành vấn đề.
- Quyết định: chỉ giữ nhật ký lần gửi, outbox và bản sao danh mục. Gói của nhà cung cấp không có giờ riêng nên mỗi message mang `receivedAt` (giờ ingest nhận) và thứ tự được giữ trong cùng khóa phân vùng.
- Hệ quả: không phát hiện được gửi trễ hay đảo thứ tự giữa hai lần gửi. Lệch với yêu cầu thứ tự theo timestamp ở tài liệu tham chiếu nếu bên nhận cần giờ của nhà cung cấp (vấn đề P-001).

## D-006: Mã khách sạn lạ và không có quyền cùng trả 401, mã 31
- Ngày: 2026-10-05
- Trạng thái: accepted.
- Quyết định: danh mục chỉ có khách sạn mà đối tác được phép, nên không phân biệt "lạ" và "không có quyền" (tránh dò mã). Trả 401 theo mô tả của người dùng dù thường là 403 (vấn đề P-005). Sai tên đăng nhập hoặc mật khẩu cũng 401, mã 30; tên lạ vẫn tốn thời gian băm như tên thật.

## D-007: Danh mục là bản sao trong ingest, nạp qua API nội bộ; cache 24 giờ
- Ngày: 2026-10-05
- Trạng thái: accepted nhưng nguồn danh mục là GIẢ ĐỊNH.
- Quyết định: đối tác, khách sạn được phép, phòng, gói giá nằm trong bảng của ingest, nạp bằng `/internal/v1/...` (token Bearer; thiếu token cấu hình thì từ chối mọi lời gọi). Tra cứu nhớ tạm 24 giờ trong tiến trình, xóa ngay khi sửa danh mục trong cùng tiến trình.
- Hệ quả: chưa có dịch vụ nào cấp danh mục; sửa ở tiến trình khác chỉ thấy sau khi hết hạn cache (P-006). Mã phòng lạ: bỏ mọi update của phòng đó. Mã gói giá lạ: bỏ điều kiện bán và giá nhưng giữ tồn của phòng. Mỗi mã lạ chỉ báo một lần mỗi lần gửi.

## D-008: Định dạng đối tác là module tự đăng ký (mô-đun mở)
- Ngày: 2026-10-05
- Trạng thái: accepted (người dùng chốt hướng mô-đun mở, không buộc vào một bên cụ thể, còn cách hiểu cụ thể là của tôi)
- Quyết định: `normalize/registry.py` đăng ký hàm `(bytes, Limits) -> NormalizedSubmission` theo tên; đối tác chọn định dạng khi đăng ký. Nhận bytes để một định dạng có thể không phải JSON.

## D-009: Quy ước đọc gói `inventory-rates-json`
- Ngày: 2026-10-05
- Trạng thái: accepted; các điểm đánh dấu GIẢ ĐỊNH chưa xác nhận.
- Quyết định: trường không gửi thì bỏ qua, không hiểu là 0; cờ đóng "0" là mở, giá trị khác là đóng, rỗng thì bỏ qua; `dow` 1 = Chủ nhật ... 7 = Thứ bảy, không đủ 7 ngày thì cắt khoảng ngày thành các đoạn liên tục; giá là giá đã gồm thuế, mã tuổi ADULT; không gán tiền tệ vì dữ liệu không có. GIẢ ĐỊNH: `from` và `to` tính cả hai đầu; điều kiện bán và giá bắt buộc có `rateplanid`; tồn tính một lần cho mỗi phòng (không nhân theo gói giá).
