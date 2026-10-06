# STATUS: ingest

Cập nhật lần cuối: 2026-10-05

## Mục tiêu
- [x] Khung dịch vụ theo skill `new-service`, ba lớp, test quét import (`tests/test_layers.py`, đã thử cố ý thêm import sai thì đỏ)
- [x] Chuẩn hóa gói `inventory-rates-json` (tách `dow`, bỏ qua trường không gửi, cờ đóng/mở, giá thập phân), module đăng ký (`normalize/`)
- [x] Lõi: kiểm quyền khách sạn, đổi mã phòng/gói giá, chống trùng theo (đối tác, X-Trace-Id) kèm mã băm, outbox, ACK sau commit, relay (`core/`)
- [x] HTTP: `POST /v1/inventory-rates` (Basic, X-Trace-Id), API nội bộ (đăng ký đối tác, danh mục, tra cứu), `/healthz` kiểm DB
- [x] Kafka thật bằng aiokafka (`io/kafka.py`), kiểm ba kịch bản RQM với broker cục bộ: Kafka tạm dừng, khởi động lại, message lặp
- [x] Test: 107 qua trên PostgreSQL 16 và Kafka cục bộ (chạy ba lần liên tiếp đều qua); trên SQLite 102 qua và 5 bỏ qua (2 test đồng thời cần PostgreSQL, 3 test Kafka thật)
- [x] Chạy thật: uvicorn trên PostgreSQL và Kafka, và `docker compose up --build` (ba container healthy, nhà cung cấp mô phỏng nhận 202, outbox về 0, ba topic được tạo)
- [x] Docs: `docs/service.yaml`, sổ vấn đề, bốn sơ đồ, D-001 đến D-009
- [x] Nối nền CI/CD (S-023): nhánh `main`, `bsn.ci.json`, `.github/workflows/ci.yml`, `.dockerignore`, `Dockerfile` cài thư viện trước mã. Chưa chạy trên GitHub (chưa có repo); chưa thử đường deploy Docker Hub, VM GCP
- [ ] Công cụ migration (hiện `create_all`), chọn leader cho relay, chỉ số và giám sát (số outbox chưa gửi mới chỉ có ở `/healthz`)
- [ ] JetStream, webhook ra, Kafka vào, API replay (chưa làm, ngoài phạm vi lần này)
- [ ] Xác nhận với nhà cung cấp thật: khóa chống trùng, `from`/`to` tính cả hai đầu, tiền tệ, ai thêm X-Trace-Id

## Ca test còn thiếu (chưa viết vào repo; chi tiết ở sổ vấn đề P-014, lệch đã đo ở P-011 đến P-013)
- Ca biên: thân rỗng, đúng bằng giới hạn và vượt một byte, không có Content-Length, UTF-8 sai; dạng UUID khác nhau cùng một khóa; giá 0, âm, rất lớn, NaN; ngày không có thật, năm nhuận, khoảng ngày đúng giới hạn; mã Unicode; hai thân khác nhau cùng trace đồng thời.
- Lỗi hạ tầng: mất kết nối DB giữa chừng (PostgreSQL thật); tiến trình chết sau commit trước khi phát; chết giữa lúc ghi submission và outbox; relay không thấy hàng chưa commit; hai relay cùng lúc; KafkaPublisher đơn vị với producer giả.
- Tích hợp với PostgreSQL và broker thật ở hạ tầng local: giữ thứ tự cùng khóa, ba topic đúng loại, broker không với tới được. Bộ RQM hiện có cần container Kafka riêng để docker pause, chưa chạy với Redpanda của hạ tầng local trong bộ test của repo.
- Đầu-cuối: chưa có test chạy uvicorn thật rồi kiểm hàng trong bảng và tin trên topic cho từng luồng.

## Chưa kiểm với hệ thống thật
- Nhà cung cấp thật: dạng gói, khóa chống trùng, quy ước ngày, tiền tệ. Chỉ có nhà cung cấp mô phỏng (`tools/sim/supplier.py`) viết theo mô tả của người dùng.
- Kafka production: chỉ kiểm với `apache/kafka` một nút cục bộ. Chưa kiểm nhiều broker, tạo topic, phân vùng nhiều nhánh, cấu hình bảo mật.
- Bên nhận message (Inventory, worker): chưa có; worker tham chiếu trong `tests/test_kafka_rqm.py` chỉ để kiểm khử trùng.
- Tải: chưa đo. Test đồng thời chỉ 12 luồng; mục tiêu độ trễ (dưới 10 giây kênh sở hữu, dưới 60 giây kênh đối tác, p99) chưa đo.

## Nhật ký
| Ngày | Việc |
|---|---|
| 2026-10-05 | Tạo khung dịch vụ bằng .claude/plugin/tools/new-service.js (dựng lại sau khi gỡ hẳn bản cũ; bản cũ sao lưu ở `BSN_/.backup/ingest-cu-2026-10-05/`) |
| 2026-10-05 | Viết mã, test (107 qua với PostgreSQL và Kafka cục bộ), Dockerfile, compose, nhà cung cấp mô phỏng; ghi docs, sơ đồ, vấn đề. Điều chưa kiểm: xem mục "Chưa kiểm với hệ thống thật" |
| 2026-10-05 | Xử lý handoff `root-to-ingest-duong-dan-trong-tai-lieu`: sửa đường dẫn tương đối sai trong `CLAUDE.md` (dòng 6, 7) và trong D-001 của `DECISIONS.md` (hai đường dẫn ở dòng Bối cảnh và Quyết định, sửa tại chỗ, nội dung quyết định không đổi). Kiểm bằng grep và `docs check`; không đụng mã |
| 2026-10-06 | Xử lý tờ `root-to-ingest-ci-va-to-khai-bao` (S-023): đổi nhánh `master` thành `main`; thêm `bsn.ci.json`, `.github/workflows/ci.yml` (test trong ảnh `python:3.13-slim` ghim mã băm, PostgreSQL 16 ghim mã băm, rồi job `image` của nền), `.dockerignore`; `Dockerfile` cài thư viện trước khi chép mã và ghim ảnh nền bằng mã băm. Đo trên máy: lớp thư viện 76,3 MB (chưa nén) nằm DƯỚI lớp mã 0,6 MB; build lần hai sau khi sửa một dòng `config.py` dùng lại lớp thư viện (CACHED, lớp thư viện không dựng lại). Container chạy khỏe (`/healthz` 200), chạy bằng người dùng `ingest`, không có tests hay docs trong ảnh. `decide.js` trả "ĐÓNG GÓI". Test: 104 qua, 3 bỏ qua (Kafka, thiếu INGEST_TEST_KAFKA_*), 0 hỏng, trên PostgreSQL 16 tạm trên Windows. CHƯA kiểm: workflow trên máy GitHub (Linux) và lớp thư viện nén thực trên Docker Hub (chưa đo một commit sửa mã thật trên Docker Hub). Chưa ghim `infra/services/ingest.json` |
| 2026-10-06 | Điền nốt tài liệu theo tờ `root-to-ingest-dien-not-tai-lieu` (không sửa mã): soát với mã và viết giải thích cho ba sơ đồ tự sinh; tài liệu ba tầng `docs/modules/` cho 9 module (14 quyết định, 14 đặc tả, gắn mã và test); 15 mục từ vựng nghiệp vụ và 5 quan hệ nạp lúc chạy; rà `service.yaml` (khớp mã, bổ sung điều chưa kiểm); ghi P-011 đến P-014 (ba lệch đã đo bằng bộ test thử nghiệm và danh sách ca test còn thiếu). Marker `// spec:` chưa có trong mã nên `docs check` còn cảnh báo. Đo bằng bộ test thử nghiệm ngoài repo (chưa commit): chuẩn hóa, lõi, HTTP chạy được; tích hợp và đầu-cuối chạy với PostgreSQL 16 và Redpanda một nút tạm |
| 2026-10-07 | Lịch sử repo được viết lại để đổi email tác giả sang địa chỉ ẩn danh (phiên infra); nội dung từng commit giữ nguyên. Mã cũ -> mới: 1e16611 -> dde2f51, e046e2a -> 544c959, 2ca9c4e -> b30417a, de79fb2 -> 57124cc, 198c1a4 -> c4bc4f8 (HEAD). Repo đã lên GitHub `tochuc-cu/svc-ingest` (do phiên infra). Lần chạy CI đầu trên GitHub (Linux, phiên infra báo, tôi chưa tự kiểm trên GitHub): job test 104 qua, 3 bỏ qua (Kafka RQM), 0 hỏng; job image đã đẩy `nguyen1410/svc-ingest:main-c4bc4f8c59cc`. Nội dung các dòng nhật ký cũ ở trên giữ nguyên mã cũ trừ chỗ ghi chú. Chưa đo kích thước nén thật trên Docker Hub |
| 2026-10-06 | Đối chiếu sơ đồ với mã theo yêu cầu phiên harness (commit dde2f51 (trước khi đổi email: 1e16611) khai lại `ket-noi-thanh-phan` dạng tầng và thêm phần giải thích cho 4 sơ đồ). Phiên ingest sửa tiếp: vẽ lại `trang-thai-message-outbox` (chỉ hai trạng thái được lưu), `trinh-tu-nhan-lan-gui` (thêm nhánh 409, bớt cột Bên nhận) và viết lại phần giải thích của hai sơ đồ này; chỉnh `docs/service.yaml` (relay là tác vụ nền trong cùng tiến trình, chỉ việc ghi nằm trong transaction, `service.py` không gọi `catalog.py`/`auth.py`, `contract.py` chỉ là kiểu dùng chung). Không đụng mã |
