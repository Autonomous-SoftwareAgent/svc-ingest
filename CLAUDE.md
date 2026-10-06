# ingest

Quy tắc chung cho mọi dịch vụ và cách làm việc (một harness duy nhất ở `BSN_/.claude`) nằm ở `../../CLAUDE.md` (tự nạp). **Mở phiên Claude Code ở `BSN_/`** rồi giao việc cho dịch vụ này; hook, MCP `bsn-docs` và skill chỉ nạp ở gốc, mở thẳng trong thư mục dịch vụ thì không có hook nào. Tệp này là phần riêng của dịch vụ.

## Phạm vi
- Làm trong `system_service/ingest/`. Ngoài thư mục này chỉ đọc; việc cần dịch vụ khác thì ghi yêu cầu vào `../../docs/handoff/`.
- Đầu phiên: đọc [docs/agent/STATUS.md](docs/agent/STATUS.md), [docs/agent/DECISIONS.md](docs/agent/DECISIONS.md), [docs/agent/CONVENTIONS.md](docs/agent/CONVENTIONS.md). Liệt kê các tệp `../../docs/handoff/*-to-ingest-*.md` còn `open` và báo người dùng.
- Tài liệu ba tầng (design/spec/impl) chỉ ghi qua công cụ MCP `bsn-docs` với `service="ingest"` (`design_record` tạo `docs/modules` lần đầu); không sửa tay. Dịch vụ này CHƯA dùng ba tầng.
- Trong `docs/` của dịch vụ chỉ có Markdown cho agent, không đặt HTML. Nguồn có cấu trúc của dịch vụ là `docs/service.yaml` (nghiệp vụ, kiến trúc, vấn đề và tiến độ), ghi bằng `bsn-docs`: `service_doc_set`, `problem_record`. Sơ đồ khai bằng `diagram_save`, không tự viết Mermaid. Người đọc xem cổng cục bộ `BSN_/docs/portal/ingest/index.html`, sinh tự động từ nguồn đó sau mỗi commit.

## Ba lớp (nguyên tắc ở ../../CLAUDE.md)
- Lớp vào/ra: `src/ingest/io/`. `http.py` (nhận lô từ nhà cung cấp, API nội bộ, xác thực Basic và Bearer, đổi mã lỗi sang HTTP), `kafka.py` (phát ra Kafka bằng aiokafka), `publishers.py` (ghi log, bộ nhớ). Không chứa nghiệp vụ, không biết định dạng của đối tác.
- Lớp chuẩn hóa: `src/ingest/normalize/`. Mỗi định dạng của đối tác một module tự đăng ký bằng `@register("<tên>")` (hiện có `inventory_rates_json.py`). Thêm định dạng là thêm một tệp, không sửa tệp nào đang có.
- Hợp đồng chuẩn: `src/ingest/contract.py` (`Update`, `NormalizedSubmission`, `MessageKind`, `ErrorCode`, `IngestError`, `Publisher`...).
- Lớp logic nội bộ: `src/ingest/core/`. `service.py` (kiểm quyền khách sạn, đổi mã, chống trùng, ghi nhật ký và outbox), `relay.py` (phát outbox), `catalog.py` (danh mục, đối tác), `auth.py` (băm mật khẩu), `cache.py`, `schema.py` (bảng).
- Nối ba lớp: chỉ `src/ingest/main.py` và `config.py`.
- Test giữ ranh giới (quét import): `tests/test_layers.py`. Đã thử cố ý thêm import sai (core->io, core->aiokafka, io->core, normalize->core, core->main) và test đỏ. Đừng sửa test để cho qua.
- Chỗ chưa tách đúng ba lớp: chưa có nợ đã biết.

## Việc của dịch vụ
- Sở hữu: nhận tồn, điều kiện bán và giá khách sạn do nhà cung cấp đẩy vào; kiểm quyền theo khách sạn; đổi mã phòng và gói giá sang mã nội bộ; chống trùng theo khóa của lần gửi; nhật ký lần gửi; outbox và phát lên Kafka; bản sao danh mục (khách sạn, phòng, gói giá) để đổi mã.
- Không sở hữu: tồn và giá hiện tại (dịch vụ nhận message sẽ giữ), tính giá, sản phẩm và nội dung, đặt chỗ, việc kéo danh sách đặt chỗ từ VTrip.
- Giao diện công bố: HTTP `POST /v1/inventory-rates` và `/internal/v1/...` (`src/ingest/io/http.py`); ba topic Kafka (tên cấu hình ở `config.py`), dạng message ở `core/service.py` (`_build`).
- Phụ thuộc: PostgreSQL; Kafka (broker production chưa chọn, xem DECISIONS D-002). Danh mục hiện nạp qua API nội bộ vì chưa có dịch vụ nào cấp.

## Quy tắc riêng (người dùng đã chốt)
- Python, FastAPI, SQLAlchemy Core, PostgreSQL là cơ sở dữ liệu duy nhất. Số nghiệp vụ và giới hạn là cấu hình `INGEST_*` (`config.py`), không viết cứng.
- ACK (202 kèm `ticketId`) chỉ trả SAU KHI dữ liệu đã nằm bền trong outbox và transaction đã commit; lưu lỗi thì trả lỗi, không ACK. ACK chỉ có nghĩa "đã nhận, đã kiểm sơ bộ, đã lưu an toàn để xử lý"; không trả kết quả xử lý cuối, không có API tra cứu trạng thái.
- Phát ít nhất một lần: relay chỉ đánh dấu "đã gửi" khi Kafka xác nhận; message có ID ổn định để bên nhận khử trùng. Gửi lại cùng khóa và cùng nội dung trả cùng `TicketId`.
- Trường nhà cung cấp không gửi thì bỏ qua, không hiểu là 0. Mã phòng hoặc gói giá lạ: bỏ dòng đó, ghi lỗi mã 10, phần hợp lệ vẫn đi. Không còn dữ liệu hợp lệ nào: từ chối cả lần gửi.
- Không giữ tồn hay giá hiện tại. Dữ liệu nhà cung cấp không có tiền tệ: không tự gán.
- Chưa kiểm với hệ thống thật phải ghi là chưa kiểm: nhà cung cấp thật, Kafka production. Test dùng nhà cung cấp mô phỏng và Kafka một nút cục bộ.
- Log chỉ ghi số đếm và mã, không ghi nội dung gói, mật khẩu hay token.

## Lệnh thường dùng
- `pip install -e ".[dev]"` rồi `python -m pytest`. Có `INGEST_TEST_DATABASE_URL=postgresql+psycopg://...` thì chạy trên PostgreSQL (kể cả `tests/test_concurrency.py`); thiếu thì dùng SQLite tạm và test đồng thời bị bỏ qua có nêu lý do.
- Test Kafka thật (`tests/test_kafka_rqm.py`): cần `INGEST_TEST_KAFKA_BOOTSTRAP` và `INGEST_TEST_KAFKA_CONTAINER` (tên container Kafka để `docker pause`); thiếu thì bỏ qua có nêu lý do. Cách dựng container ở `docker-compose.yml` (mục `kafka`).
- Kiểm cấu hình: `python -m ingest.main --check-config` (cần `INGEST_DATABASE_URL`).
- Chạy cục bộ: sao `.env.example` thành `.env`, rồi `docker compose up --build -d` (Ingest, PostgreSQL, Kafka một nút). Gửi thử: `python tools/sim/supplier.py --user ... --password ...` sau khi đăng ký đối tác và danh mục qua `/internal/v1/...`.
- Kiểm tài liệu (từ `BSN_/`): `node .claude/plugin/mcp/cli.js --service ingest check`.

## CI và ghim bản mới (S-023; cách làm ở skill `cicd`)
- Nhánh chính là `main`; chỉ `main` được đóng gói. Repo có `bsn.ci.json`, `.github/workflows/ci.yml` (job `test` rồi job `image` gọi workflow chung của nền) và `.dockerignore`. Trên GitHub CI chỉ chạy được test SQLite và PostgreSQL; ba ca Kafka tự bỏ qua vì cần `docker pause` broker.
- `Dockerfile` cài thư viện từ `pyproject.toml` TRƯỚC khi chép `src`: sửa mã chỉ làm lại lớp mã. Thêm phụ thuộc thì sửa `pyproject.toml` (lớp thư viện sẽ được dựng lại).
- **Khai báo trước, build sau (S-029):** job `image` chỉ đóng gói commit đang được ghim trong `infra/services/ingest.json`; lần đẩy khác chỉ chạy test. Thứ tự lên bản mới: (1) commit ở máy và chạy test; (2) từ `BSN_/` chạy `node infra/bsn.js pin ingest --apply`, rồi `git -C infra add services/ingest.json`, `git -C infra commit -m "ghim ingest <mã commit>"`, `git -C infra push`; (3) `git push` repo ingest: test qua thì bản `main-<12 ký tự commit>` được đóng gói. Lỡ đẩy mã trước khi ghim: ghim xong thì chạy tay `gh workflow run ci.yml -R tochuc-cu/svc-ingest`. `node infra/bsn.js images` báo "CHỜ BUILD" cho commit đã ghim mà chưa có bản. Tờ `infra/services/ingest.json` thuộc repo `tochuc-cu/deploy` (`BSN_/infra/`, S-028), không thuộc repo gốc. Ghim và đẩy chỉ khi người dùng bảo. Phiên ingest chỉ ghi đúng tờ của mình, không sửa phần còn lại của `infra/`.

## Sơ đồ (docs/diagrams/, khai bằng `diagram_save`)
- Nghiệp vụ: `trinh-tu-nhan-lan-gui` (trình tự một lần gửi), `luong-xu-ly-tung-dong` (luồng xử lý một dòng dữ liệu).
- Kiến trúc: `ket-noi-thanh-phan` (kết nối các thành phần), `trang-thai-message-outbox` (trạng thái một message trong outbox).
- Dữ liệu: `du-lieu-bang` (6 bảng PostgreSQL). Sơ đồ này do công cụ TỰ SINH từ cơ sở dữ liệu thật, không khai tay: sửa `src/ingest/core/schema.py` xong thì gọi `diagram_generate` với `id="du-lieu-bang"` (cần hạ tầng local đang chạy) rồi viết lại phần giải thích; `check` sẽ nhắc khi quên.
- Kiểu và giao diện: `kieu-vao-ra-chuan-hoa` (hợp đồng chuẩn, lớp vào/ra, lớp chuẩn hóa), `kieu-logic-luu-tru` (logic nội bộ và nơi lưu). Đổi import giữa các module thì sửa hai sơ đồ này.
- Mỗi dịch vụ phải đủ năm loại sơ đồ (luồng, trình tự, trạng thái, dữ liệu, lớp); xem còn thiếu gì bằng `diagram_list`.
