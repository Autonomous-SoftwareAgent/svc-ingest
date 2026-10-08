<!-- GENERATED từ docs/service.yaml bằng bsn-docs. Không sửa tay; ghi nguồn bằng service_doc_set / problem_record. -->
# Ingest (cửa nhận tồn và giá khách sạn) (ingest)

Cửa nhận tồn phòng, điều kiện bán và giá khách sạn do nhà cung cấp đẩy vào. Kiểm người gửi và quyền theo khách sạn, đổi mã phòng và gói giá sang mã nội bộ, chống trùng, lưu bền rồi mới báo đã nhận, sau đó phát lên Kafka. Không giữ số phòng hay giá hiện tại và không tính giá.

Cập nhật: 2026-10-08. Bản cho người đọc: BSN_/docs/portal/ingest/index.html (sinh từ cùng nguồn).

## Nghiệp vụ

Mục tiêu: Để số phòng còn bán, điều kiện bán và giá mà khách thấy khi tìm và đặt khớp với hệ thống của nhà cung cấp: chuẩn hóa mã, kiểm quyền theo khách sạn, rồi mới đẩy đi.

Người dùng và nhu cầu:
- Hệ thống của nhà cung cấp khách sạn: Tự động gửi cập nhật số phòng, điều kiện bán và giá (chỉ phần thay đổi) và biết ngay là đã được nhận
- Dịch vụ nội bộ và người vận hành: Đăng ký đối tác, cấp quyền khách sạn, nạp danh mục phòng và gói giá, tra cứu danh mục
- Dịch vụ nhận cập nhật (tồn, giá): Nhận đủ message, đúng thứ tự trong cùng phòng và gói giá, có mã định danh để khử trùng

Giá trị mang lại:
- Khách không thấy còn phòng khi đã hết, hay thấy giá cũ, vì mọi cập nhật nhà cung cấp gửi đều được ghi nhận bền trước khi báo đã nhận
- Gửi lại hay mạng chập chờn không làm cập nhật bị trùng: cùng khóa và cùng nội dung thì nhận lại đúng một mã phiếu
- Một dòng sai không làm hỏng cả lần gửi: mã phòng hoặc gói giá lạ thì bỏ dòng đó và báo lỗi, phần hợp lệ vẫn đi
- Thêm một cách kết nối hoặc một định dạng của đối tác mới là thêm một tệp, không sửa phần đang chạy

Luồng nhan-lan-gui: Nhà cung cấp gửi tồn, điều kiện bán và giá
1. Nhà cung cấp gửi gói JSON kèm tên đăng nhập, mật khẩu, mã theo dõi X-Trace-Id (UUID) và kênh gửi X-Channel-Id
2. Ingest kiểm tên đăng nhập và mật khẩu; sai thì trả 401
3. Ingest kiểm X-Trace-Id đúng UUID và nội dung không quá lớn
4. Chuẩn hóa gói: tách khoảng ngày theo thứ trong tuần, tách mỗi dòng thành tối đa ba loại cập nhật (tồn, điều kiện bán, giá), bỏ qua trường không gửi
5. Kiểm đối tác có quyền với khách sạn này; không có hoặc mã lạ thì trả 401 và không nhận gì
6. Đổi mã phòng và gói giá của nhà cung cấp sang mã nội bộ; mã lạ thì bỏ phần dữ liệu đó và ghi lỗi mã 10
7. Ghi lần gửi và các message vào outbox trong một transaction
8. Chỉ sau khi đã commit mới trả 202 kèm mã phiếu (ticketId); lưu lỗi thì trả lỗi, không báo đã nhận
9. Một tác vụ nền (relay) trong cùng tiến trình Ingest phát các message từ outbox lên Kafka

Luồng gui-lai-cung-khoa: Gửi lại cùng một lần gửi
1. Nhà cung cấp gửi lại với cùng X-Trace-Id và cùng nội dung (do mạng, hay không nhận được phản hồi)
2. Ingest trả đúng mã phiếu cũ và đánh dấu duplicate, không ghi thêm message nào
3. Nếu cùng X-Trace-Id nhưng nội dung khác thì trả 409, không ghi gì

Luồng phat-len-kafka: Phát lên Kafka và khi Kafka lỗi
1. Tác vụ nền (relay) trong cùng tiến trình đọc outbox theo id tăng dần và gửi từng message lên Kafka
2. Chỉ khi Kafka xác nhận mới đánh dấu đã gửi
3. Kafka tạm ngừng hoặc dịch vụ khởi động lại: dữ liệu đã báo đã nhận vẫn nằm trong outbox và được gửi tiếp khi hệ thống phục hồi
4. Lỗi ở một message thì dừng, không gửi vượt các message sau để giữ thứ tự; message lỗi chặn mọi message sau nó, của mọi khách sạn
5. Có thể có message gửi lặp; bên nhận khử trùng theo messageId

Luồng dong-bi-bo: Dòng hoặc gói bị bỏ, bị từ chối
1. Dòng sai cấu trúc (ngày sai, số âm, giá lặp số khách...): bỏ dòng, báo lỗi mã 20, các dòng khác vẫn đi
2. Mã phòng lạ: bỏ mọi cập nhật của phòng đó, báo mã 10. Mã gói giá lạ: bỏ điều kiện bán và giá nhưng giữ tồn, báo mã 10
3. Không còn dữ liệu hợp lệ nào: từ chối cả lần gửi (mã 12), không lưu gì nên cùng X-Trace-Id gửi lại được bản đã sửa
4. Gói không đọc được: trả 400. Quá lớn: trả 413

Ngoài phạm vi:
- Giữ số phòng còn lại hay giá hiện tại làm dữ liệu chính thức (dịch vụ nhận message giữ)
- Tính giá, quản lý sản phẩm và nội dung
- Đối tác kéo danh sách đặt chỗ từ VTrip
- Trả kết quả xử lý cuối cho nhà cung cấp hay API tra cứu trạng thái: ACK chỉ có nghĩa đã nhận và đã lưu an toàn
- Chạy lại phân tích (replay), kết nối JetStream, webhook ra, Kafka vào (chưa làm)

CHƯA kiểm với hệ thống thật:
- Chưa kiểm với nhà cung cấp thật: dạng gói, quy ước thứ trong tuần, cờ đóng, và nhà cung cấp thật có gửi được Basic và X-Trace-Id không
- Chưa rõ ai thêm header X-Trace-Id (nhà cung cấp hay cổng trung gian)
- Khóa chống trùng là (đối tác, X-Trace-Id) kèm mã băm nội dung: là giả định, chưa xác nhận
- Khoảng ngày from và to được hiểu là tính cả hai đầu: giả định, chưa xác nhận
- Dữ liệu không có tiền tệ nên không biết các số tiền là đồng nào
- Gói không có giờ của nhà cung cấp nên không phát hiện được gửi trễ hay đảo thứ tự giữa hai lần gửi
- Chỉ kiểm Kafka với broker một nút chạy cục bộ (Kafka và một lần thử với Redpanda một nút tạm), chưa kiểm cụm nhiều nút, bảo mật hay broker production
- Bộ test RQM trong repo chỉ chạy với Kafka cục bộ có container riêng để tạm dừng; chưa chạy với broker dùng chung của hệ (không được tạm dừng broker dùng chung)
- Danh mục khách sạn, phòng, gói giá nạp qua API nội bộ vì chưa biết nguồn thật
- Mục tiêu độ trễ (dưới 10 giây kênh sở hữu, dưới 60 giây kênh đối tác, p99) là của cả đường đi và chưa được đo; test đồng thời mới 12 luồng
- Chưa có dịch vụ nhận message (Inventory, worker tồn); chỉ có worker tham chiếu trong test
- Hành vi khi JSON lồng cực sâu, khi kết nối DB chết giữa chừng ở bước đọc trước transaction, và khi hai relay chạy cùng lúc chỉ mới đo bằng test thử nghiệm, chưa có trong bộ test của repo (xem P-011 đến P-013)
- Thời gian xác thực của tên lạ so với tên thật chỉ được kiểm là có chạy băm giả, chưa đo chênh lệch thời gian

## Kiến trúc kỹ thuật

Ba lớp, phụ thuộc một chiều, gặp nhau qua hợp đồng chuẩn (contract.py). Lớp vào/ra nhận HTTP và phát Kafka; lớp chuẩn hóa dịch gói của từng đối tác thành cập nhật chuẩn; lớp lõi kiểm quyền, đổi mã, chống trùng, ghi nhật ký và outbox. Chỉ main.py nối các lớp. PostgreSQL là cơ sở dữ liệu duy nhất; Kafka là nơi phát.

Lớp:
- vao-ra (Lớp vào/ra): Giao thức: HTTP với xác thực Basic và Bearer, giới hạn kích thước, đổi mã lỗi sang HTTP; phát ra Kafka. Không chứa nghiệp vụ [src/ingest/io/]
- chuan-hoa (Lớp chuẩn hóa): Mỗi định dạng của đối tác một module tự đăng ký; dịch gói sang cập nhật chuẩn, tách khoảng ngày theo thứ trong tuần, kiểm dữ liệu vào [src/ingest/normalize/]
- logic (Lớp logic nội bộ): Kiểm quyền khách sạn, đổi mã, chống trùng, ghi nhật ký và outbox, relay, danh mục. Chỉ biết dạng chuẩn [src/ingest/core/]
- hop-dong (Hợp đồng chuẩn): Kiểu dữ liệu, mã lỗi, ngoại lệ và cổng Publisher dùng chung của cả ba lớp. Mọi lớp import nó; không có lời gọi nào đi qua nó [src/ingest/contract.py]

Thành phần:
- http (HTTP) @vao-ra: POST /v1/inventory-rates cho nhà cung cấp; /internal/v1 cho dịch vụ nội bộ; /healthz kiểm cơ sở dữ liệu. Chỉ gọi các hook do main.py tiêm vào, không tự chuẩn hóa [src/ingest/io/http.py]
- kafka (Cổng phát Kafka) @vao-ra: aiokafka, acks=all, producer idempotent, tạo lại producer sau lỗi; chỉ trả về khi broker xác nhận [src/ingest/io/kafka.py, src/ingest/io/publishers.py]
- inventory-rates-json (Định dạng inventory-rates-json) @chuan-hoa: Đọc gói InvResRateRequest: ngày, dow, tồn, điều kiện bán, giá; dòng sai thì bỏ dòng [src/ingest/normalize/inventory_rates_json.py, src/ingest/normalize/registry.py]
- nhan-lo (Nhận lần gửi) @logic: Kiểm trùng, kiểm quyền khách sạn và đổi mã (đọc trước, qua cache.py và bảng ánh xạ; không gọi catalog.py hay auth.py), rồi ghi submission và outbox cùng một transaction; chỉ sau commit mới ACK [src/ingest/core/service.py]
- relay (Relay) @logic: Tác vụ nền trong cùng tiến trình (main.py khởi động): đọc outbox theo id tăng dần, gửi qua cổng Publisher, chỉ đánh dấu khi broker xác nhận; lỗi thì dừng và chặn mọi message sau [src/ingest/core/relay.py]
- danh-muc (Danh mục, đối tác, xác thực) @logic: catalog.py: danh mục và đối tác; auth.py: băm mật khẩu và đăng nhập; cache.py: nhớ tạm 24 giờ; schema.py: bảng. main.py gọi catalog và auth qua hook; core/service.py chỉ dùng cache.py và đọc bảng ánh xạ để đổi mã [src/ingest/core/catalog.py, src/ingest/core/auth.py, src/ingest/core/cache.py, src/ingest/core/schema.py]
- noi-lop (Nối ba lớp): Chọn publisher, tạo hook (xác thực, nhận lần gửi, API danh mục), khởi động relay nền trong cùng tiến trình, khởi tạo bảng [src/ingest/main.py, src/ingest/config.py]
- mo-phong (Nhà cung cấp mô phỏng): Script gửi gói mẫu để chạy thử; không phải nhà cung cấp thật [tools/sim/supplier.py]

Phụ thuộc vào:
- PostgreSQL (infra, qua SQLAlchemy Core, psycopg): Đối tác, danh mục, nhật ký lần gửi, outbox
- Kafka (infra, qua aiokafka): Phát ba loại message tồn, điều kiện bán, giá
- Hệ thống của nhà cung cấp (external, qua HTTP, xác thực Basic): Nguồn tồn, điều kiện bán và giá (chưa kiểm với nhà cung cấp thật)

Cung cấp cho:
- Nhà cung cấp (qua POST /v1/inventory-rates): Nhận cập nhật tồn, điều kiện bán và giá, trả ACK kèm mã phiếu
- Dịch vụ nội bộ và người vận hành (qua /internal/v1/partners...): Đăng ký đối tác, cấp quyền khách sạn, nạp và tra cứu danh mục
- Dịch vụ nhận cập nhật (Inventory, worker tồn; chưa có) (qua Kafka: ingest.ari.inventory, ingest.ari.restrictions, ingest.ari.rates): Cập nhật tồn, điều kiện bán và giá, có messageId để khử trùng

Quyết định liên quan:
- D-001: Ingest riêng, Python, tách hẳn các ingest khác
- D-002: Phát lên Kafka qua cổng Publisher; broker production chưa chọn
- D-003: ACK sau commit, outbox, phát ít nhất một lần
- D-004: Khóa chống trùng là (đối tác, X-Trace-Id) kèm mã băm
- D-005: Không giữ tồn hay giá hiện tại; thứ tự theo giờ nhận
- D-006: Khách sạn lạ và không có quyền cùng 401 mã 31
- D-007: Danh mục là bản sao, nạp qua API nội bộ, cache 24 giờ
- D-008: Định dạng đối tác là module tự đăng ký
- D-009: Quy ước đọc gói inventory-rates-json

## Vấn đề và tinh chỉnh

Đã xong:
- Khung dịch vụ theo skill new-service, ba lớp và test quét import
- Chuẩn hóa gói inventory-rates-json và lõi nhận lần gửi (kiểm quyền, đổi mã, chống trùng, outbox, ACK sau commit)
- HTTP cho nhà cung cấp và API nội bộ; relay; phát Kafka thật bằng aiokafka
- 107 test qua trên PostgreSQL và Kafka cục bộ, gồm ba kịch bản RQM: Kafka tạm dừng, khởi động lại, message lặp
- Chạy thật bằng uvicorn và bằng docker compose (Ingest, PostgreSQL, Kafka) với nhà cung cấp mô phỏng
- Tài liệu: service.yaml, sổ vấn đề, bảy sơ đồ agent khai và sơ đồ dữ liệu tự sinh, ba sơ đồ tự sinh từ mã đã giải thích và soát, quyết định D-001 đến D-009
- Tài liệu ba tầng cho 9 module (contract, normalize, intake, relay, catalog, auth, http, kafka, wiring): 14 quyết định thiết kế, 14 đặc tả, gắn mã và test
- Từ vựng nghiệp vụ và các quan hệ nạp lúc chạy cho kho ngữ nghĩa

Tiếp theo:
- Chốt broker production và dựng topic (số phân vùng, retention)
- Xác nhận với nhà cung cấp thật: khóa chống trùng, from/to tính cả hai đầu, tiền tệ, ai thêm X-Trace-Id
- Viết các ca test còn thiếu (P-014): ca biên, tích hợp PostgreSQL và broker thật ở hạ tầng local, đầu-cuối qua HTTP cho từng luồng
- Sửa ba lệch đã đo (P-011 đến P-013) khi được phép sửa mã
- Chỉnh skill cicd cho ingest và thử đường deploy Docker Hub, VM GCP
- Công cụ migration, chọn leader cho relay, chỉ số và cảnh báo (độ trễ, số outbox chưa gửi)
- Thêm kết nối còn thiếu: JetStream, webhook ra, Kafka vào; API replay nếu cần
- Dịch vụ nhận message (Inventory, worker tồn) và hợp đồng message thật với họ

Vấn đề chưa xong (15):
- P-001 [open, medium] Không phát hiện gửi trễ hay đảo thứ tự giữa hai lần gửi (phát hiện 2026-10-05)
  Vấn đề: Gói của nhà cung cấp không có giờ riêng, nên Ingest chỉ gắn giờ nó nhận (receivedAt) và giữ thứ tự trong cùng khóa phân vùng. Hai lần gửi tới đảo thứ tự (lần cũ tới sau lần mới) vẫn được nhận như bình thường và có thể ghi đè số phòng hoặc giá mới bằng dữ liệu cũ ở bên nhận. Lệch với yêu cầu thứ tự theo timestamp ở tài liệu tham chiếu nếu bên nhận cần giờ của nhà cung cấp.
  Tinh chỉnh: Chưa tinh chỉnh. Hướng: xin nhà cung cấp gửi giờ cập nhật trong gói, hoặc Ingest giữ mốc mới nhất theo từng phòng và gói giá (đổi quyết định D-005).
  Tham chiếu: D-005, src/ingest/core/service.py
- P-002 [open, medium] Không có kênh báo lỗi hay cảnh báo cho người vận hành (phát hiện 2026-10-05)
  Vấn đề: Các dòng bị bỏ (mã 10, 20) chỉ được trả lại cho nhà cung cấp và lưu trong cột row_errors của bảng submission. Không ai được báo khi nhà cung cấp liên tục gửi mã lạ, khi outbox đọng lại, hay khi Kafka lỗi; chỉ có log và /healthz (số outbox chưa gửi). Tài liệu tham chiếu nói cảnh báo không có người nhận thì bằng không có cảnh báo.
  Tinh chỉnh: Chưa tinh chỉnh. Cần chỉ số (độ trễ gửi, số outbox chưa gửi, số dòng bị bỏ theo đối tác) và người nhận cảnh báo.
  Tham chiếu: src/ingest/core/service.py, src/ingest/main.py
- P-003 [open, medium] Relay chỉ chạy một bản và một message lỗi chặn mọi message sau (phát hiện 2026-10-05)
  Vấn đề: Relay dừng ở message lỗi đầu tiên để không đảo thứ tự, nên một message không gửi được (ví dụ quá lớn, topic bị từ chối) chặn toàn bộ outbox: số phòng và giá mới của mọi khách sạn dồn lại, khách thấy dữ liệu cũ. Chưa có chọn leader, nên chạy nhiều bản Ingest cùng bật relay có thể gửi trùng hoặc lệch thứ tự (cần đặt INGEST_RELAY_ENABLED=false ở các bản còn lại).
  Tinh chỉnh: Chưa tinh chỉnh. Hướng: chặn theo từng khóa phân vùng thay vì toàn bộ, chuyển message hỏng sang hàng đợi lỗi sau số lần thử, chọn leader bằng khóa của PostgreSQL.
  Tham chiếu: D-003, src/ingest/core/relay.py
- P-004 [open, medium] Có thể phát lặp message, bên nhận phải khử trùng (phát hiện 2026-10-05)
  Vấn đề: Giao nhận ít nhất một lần. Đã đo với Kafka cục bộ: khi Kafka bị tạm dừng, lần gửi hết giờ vẫn có thể tới broker, rồi relay gửi lại nên cùng một messageId xuất hiện hai lần. Bên nhận không khử trùng theo messageId thì số phòng hoặc giá bị áp dụng hai lần. Hiện chưa có bên nhận thật; chỉ có worker tham chiếu trong test.
  Tinh chỉnh: Test tests/test_kafka_rqm.py kiểm worker tham chiếu khử trùng bằng khóa chính messageId trong cùng giao dịch cập nhật. Cần yêu cầu bên nhận thật làm như vậy.
  Tham chiếu: D-003, tests/test_kafka_rqm.py
- P-005 [open, low] Sai quyền theo khách sạn trả 401, khách sạn lạ không phân biệt được (phát hiện 2026-10-05)
  Vấn đề: Theo mô tả của người dùng, đối tác không được gửi cho khách sạn này thì trả 401 (thường là 403). Danh mục chỉ có khách sạn mà đối tác được phép, nên mã khách sạn lạ và không có quyền cùng trả 401 mã 31. Nhà cung cấp phân biệt "sai mật khẩu" và "sai khách sạn" chỉ qua mã lỗi 30 và 31 trong thân phản hồi.
  Tinh chỉnh: Giữ như mô tả. Cân nhắc đổi thành 403 nếu nhà cung cấp chấp nhận.
  Tham chiếu: D-006, src/ingest/io/http.py
- P-006 [open, medium] Danh mục chưa có nguồn thật; cache 24 giờ theo từng tiến trình (phát hiện 2026-10-05)
  Vấn đề: Khách sạn, phòng, gói giá và quyền đối tác hiện nạp bằng tay qua API nội bộ vì chưa dịch vụ nào cấp. Tra cứu được nhớ 24 giờ trong từng tiến trình: sửa danh mục ở tiến trình khác thì tiến trình này vẫn đổi mã theo bản cũ tới khi hết hạn (đã có test). Thu hồi quyền một khách sạn của đối tác có thể chậm hiệu lực tới 24 giờ khi chạy nhiều bản.
  Tinh chỉnh: Chưa tinh chỉnh. Hướng: nguồn danh mục thật (Master data), cache có thể xóa chủ động hoặc ngắn hơn cho phần quyền.
  Tham chiếu: D-007, src/ingest/core/catalog.py, src/ingest/core/cache.py
- P-007 [open, high] Chưa kiểm với nhà cung cấp thật và Kafka production (phát hiện 2026-10-05)
  Vấn đề: Mọi test chạy với nhà cung cấp mô phỏng viết theo mô tả của người dùng và Kafka một nút cục bộ. Chưa biết nhà cung cấp thật có gửi được Basic và X-Trace-Id, có dùng cùng khóa chống trùng, có hiểu from và to tính cả hai đầu, và quy ước dow có đúng không. Sai một điểm thì có thể từ chối nhầm lô hợp lệ hoặc ghi sai ngày bán, ảnh hưởng tới số phòng và giá khách thấy.
  Tinh chỉnh: Chưa tinh chỉnh. Cần thử với một nhà cung cấp thật hoặc môi trường kiểm của họ, và dựng Kafka production rồi chạy lại ba kịch bản RQM.
  Tham chiếu: D-002, D-004, D-009, tests/test_kafka_rqm.py
- P-008 [open, medium] Giá không có tiền tệ (phát hiện 2026-10-05)
  Vấn đề: Gói của nhà cung cấp chỉ có số tiền, không có đơn vị tiền tệ hay thuế riêng (giá được coi là đã gồm thuế). Ingest không gán tiền tệ, nên bên nhận không thể biết các số là đồng nào. Gán sai (ví dụ cứ coi là VND) sẽ hiển thị sai giá cho khách.
  Tinh chỉnh: Chưa tinh chỉnh. Cần quyết định nghiệp vụ: tiền tệ theo khách sạn hay theo đối tác, đặt ở danh mục hoặc hợp đồng với nhà cung cấp.
  Tham chiếu: D-009, src/ingest/normalize/inventory_rates_json.py
- P-009 [open, medium] Chưa có bên nhận message và hợp đồng message thật (phát hiện 2026-10-05)
  Vấn đề: Dạng message phát ra (tên trường, mã nội bộ, khoảng ngày tính cả hai đầu, tên topic, khóa phân vùng) do Ingest tự định nghĩa vì Inventory và worker tồn chưa tồn tại. Tài liệu tham chiếu yêu cầu mỗi topic có chủ, có bên phát và bên nhận; hiện topic chưa có bên nhận nên chưa chắc đã đúng nhu cầu của họ.
  Tinh chỉnh: Chưa tinh chỉnh. Khi dựng dịch vụ nhận, chốt hợp đồng message cùng họ qua docs/handoff.
  Tham chiếu: D-002, src/ingest/core/service.py
- P-010 [open, low] Chưa có migration, chỉ số và đo tải; chưa chỉnh skill cicd (phát hiện 2026-10-05)
  Vấn đề: Bảng tạo bằng create_all lúc khởi động nên đổi schema sau này không có đường nâng cấp. Mục tiêu độ trễ (dưới 10 giây kênh sở hữu, dưới 60 giây kênh đối tác, p99) chưa đo và chưa có chỉ số. Skill cicd viết cho payment-hub, chưa chỉnh và chưa thử deploy Docker Hub, VM GCP cho ingest.
  Tinh chỉnh: Chưa tinh chỉnh.
  Tham chiếu: docker-compose.yml, src/ingest/core/schema.py
- P-011 [open, low] JSON lồng cực sâu làm lọt RecursionError, trả 503 thay vì 400 (phát hiện 2026-10-06)
  Vấn đề: json.loads ném RecursionError (không phải ValueError) với thân lồng hàng nghìn tầng, nên normalize/inventory_rates_json.parse không đổi nó thành IngestError mã 21; io/http.py bắt mọi ngoại lệ và trả 503 mã 50 "không lưu được, hãy gửi lại". Không có gì được ACK hay lưu, nhưng nhà cung cấp bị bảo gửi lại một gói sẽ luôn hỏng thay vì được báo gói sai (400), và có thể gửi lại mãi. Đã đo: thân 1900 cặp ngoặc trả 503.
  Tinh chỉnh: Chưa sửa (đợt này không sửa mã). Hướng: bắt RecursionError trong parse và trả mã 21.
  Tham chiếu: NORM-S-001, src/ingest/normalize/inventory_rates_json.py:211, src/ingest/io/http.py:175
- P-012 [open, low] Lỗi DB ở bước đọc trước transaction lọt ra thô khỏi service.accept (phát hiện 2026-10-06)
  Vấn đề: _find_existing và _maps chạy ngoài try của accept, nên kết nối PostgreSQL chết ở đó làm SQLAlchemyError (OperationalError) lọt ra thay vì IngestError mã 50. Lớp HTTP bắt mọi ngoại lệ nên vẫn trả 503 mã 50 và không ACK giả; hậu quả chỉ là mã lỗi không nhất quán ở tầng lõi và log khác. Đã đo trên PostgreSQL 16 khi cắt kết nối bằng pg_terminate_backend, engine không bật pool_pre_ping. main.py bật pool_pre_ping nên trường hợp thật ít gặp hơn.
  Tinh chỉnh: Chưa sửa. Hướng: bọc các bước đọc đầu trong cùng try thành mã 50.
  Tham chiếu: INTK-S-001, src/ingest/core/service.py:178, src/ingest/core/service.py:181
- P-013 [open, low] API nội bộ kiểm thân yêu cầu trước khi kiểm token (phát hiện 2026-10-06)
  Vấn đề: Với POST và PUT /internal/v1/..., FastAPI kiểm thân (pydantic) trước khi chạy hàm kiểm Bearer, nên người chưa đăng nhập gửi thân sai nhận 400 mã 25 kèm tên trường và lý do thay vì 401. Không lộ dữ liệu, mật khẩu không bị lặp lại, nhưng lộ hình dạng thân của API quản trị cho người không có token. Đã đo bằng TestClient.
  Tinh chỉnh: Chưa sửa. Hướng: kiểm token bằng dependency chạy trước khi đọc thân.
  Tham chiếu: HTTP-S-002, src/ingest/io/http.py:207, src/ingest/io/http.py:189
- P-014 [open, medium] Danh sách ca test còn thiếu so với bộ test hiện có (107 ca) (phát hiện 2026-10-06)
  Vấn đề: Bộ test hiện có (tests/) CHƯA có: (1) Ca biên: thân rỗng; thân đúng bằng giới hạn và vượt một byte; thân không có Content-Length; UTF-8 sai; dạng UUID khác nhau (hoa, không gạch, ngoặc, urn) phải cùng một khóa; giá 0, âm, rất lớn, NaN, Infinity; ngày 2026-02-30, năm nhuận; khoảng ngày đúng bằng giới hạn và hơn một ngày; mã Unicode; dow sai; cờ không phải chuỗi; roomstosell kiểu sai; hai thân khác nhau cùng trace gửi đồng thời; tên và username đúng 128 và 129 ký tự. (2) Lỗi hạ tầng: mất kết nối DB giữa chừng trên PostgreSQL thật; tiến trình chết sau commit trước khi phát; tiến trình chết giữa lúc ghi submission và outbox; relay không thấy hàng của transaction chưa commit; hai relay cùng lúc; relay sống sót lỗi DB tạm thời; KafkaPublisher đơn vị với producer giả (lỗi tạo lại producer, hết giờ). (3) Tích hợp: giữ thứ tự cùng khóa trong một phân vùng và ba topic đúng loại trên broker thật; broker không với tới được thì lỗi nhanh. Bộ RQM hiện có chỉ chạy được khi có container Kafka riêng để docker pause, chưa chạy với Redpanda của hạ tầng local trong bộ test của repo. (4) Đầu-cuối: chưa có test nào chạy dịch vụ uvicorn thật rồi kiểm hàng trong bảng và tin trên topic cho từng luồng (nhận, gửi lặp, 409, mã lạ, toàn bộ lỗi, khách sạn lạ, nạp danh mục, broker dừng, khởi động lại, healthz). (5) Chưa có test tự động cho vòng đời lifespan, --check-config, tải và độ trễ p99. Đã thử viết và chạy một bộ test bổ sung bên ngoài repo (docs/handoff/ingest-dung-lai/tests, chưa commit): phần chuẩn hóa, lõi, HTTP chạy được với mã hiện tại; phần tích hợp và đầu-cuối chạy được với PostgreSQL 16 và Redpanda một nút tạm.
  Tinh chỉnh: Chưa viết test vào repo (đợt này chỉ ghi danh sách). Ba lệch đã đo từ bộ thử nghiệm ghi ở P-011 đến P-013.
  Tham chiếu: tests/, tests/test_kafka_rqm.py, INTK-S-001, HTTP-S-001, RELY-S-001
- P-015 [open, medium] CI không phủ phần Kafka; chờ có Kafka thật của cả hệ (phát hiện 2026-10-08)
  Vấn đề: Ba ca RQM trong tests/test_kafka_rqm.py (Kafka tạm dừng rồi chạy lại, dịch vụ khởi động lại khi outbox còn tin, tin bị gửi hai lần) cần broker thật và quyền docker pause lên container broker. Job test của CI chạy trong container Python và không dựng broker, nên trên GitHub ba ca tự bỏ qua (lần chạy 37756461447: 104 qua, 3 bỏ qua). Hậu quả: một lỗi chỉ nằm ở io/kafka.py hoặc core/relay.py (mất tin đã báo đã nhận khi Kafka sập, hoặc áp dụng trùng) không làm CI đỏ; bước chạy thử của nền chỉ kiểm /healthz. Hiện chỉ có chạy tay ở máy trước khi ghim bản mới (đã chạy với Kafka và Redpanda một nút cục bộ).
  Tinh chỉnh: Người dùng quyết GÁC (qua phiên infra, 2026-10-08): chưa làm, đợi khi build toàn bộ dịch vụ có Kafka thật của cả hệ. Hướng khi làm (phiên infra gợi ý, chưa chạy thật trên GitHub): bỏ container: để job chạy trên runner có docker, cài Python bằng actions/setup-python ghim mã commit, PostgreSQL trong services: có cổng và địa chỉ localhost, broker bật bằng bước docker run có tên cố định rồi đặt INGEST_TEST_KAFKA_BOOTSTRAP và INGEST_TEST_KAFKA_CONTAINER, và thêm một biến chỉ đặt trong ci.yml để thiếu Kafka thì ba ca hỏng thay vì bỏ qua.
  Tham chiếu: tests/test_kafka_rqm.py, .github/workflows/ci.yml, RELY-S-001, RELY-S-002, KAFK-S-001
