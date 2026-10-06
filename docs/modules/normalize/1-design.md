---
module: normalize
prefix: NORM
---
# normalize - Design (tầng 1)

Vì sao và cái gì: quyết định nghiệp vụ và kỹ thuật của module. Chỉ ghi qua tool `design_record` / `design_update`.

## NORM-D-001: Mỗi định dạng của nhà cung cấp là một module tự đăng ký; lỗi một dòng khác lỗi cả gói
- date: 2026-10-06
- status: accepted
- decision: Lớp chuẩn hóa là registry tên định dạng -> hàm (bytes, Limits) -> NormalizedSubmission. normalize/__init__.py nạp mọi module trong thư mục bằng importlib; module tự đăng ký bằng @register("inventory-rates-json"), trùng tên thì lỗi. Hiện chỉ có inventory-rates-json (InvResRateRequest). Lỗi cả gói (không phải JSON, không phải object, thiếu hotelid hoặc room, quá max_updates) ném IngestError mã 21 hoặc 24 và từ chối cả lần gửi. Lỗi một dòng (room hay date sai cấu trúc) chỉ bỏ dòng đó, ghi RowError mã 20 kèm đường dẫn kiểu room[0].date[1].
- rationale: Thêm nhà cung cấp mới là thêm một tệp, không sửa tệp cũ (nguyên tắc ba lớp). Một dòng hỏng không được làm mất cả lần gửi vì nhà cung cấp gửi delta nhiều phòng nhiều ngày; ngược lại gói không đọc được thì không có gì để nhận. Phương án đã bỏ: từ chối cả gói khi có một dòng sai.
- impacts: Module định dạng không được nhập nhau (test_layers). Lỗi RecursionError với JSON lồng cực sâu hiện lọt ra khỏi parse (chưa bắt), lớp HTTP vẫn trả 503/50.

## NORM-D-002: Quy ước đọc gói inventory-rates-json: bỏ trường không gửi, tách theo thứ trong tuần, giữ giá dạng chữ
- date: 2026-10-06
- status: accepted
- decision: Trường không gửi hoặc null thì BỎ QUA, không hiểu là 0 (roomstosell=0 là giá trị thật). Cờ đóng là chuỗi: "0" là mở, chuỗi khác là đóng, chuỗi rỗng thì bỏ qua, không phải chuỗi thì lỗi dòng. dow: 1=Chủ nhật đến 7=Thứ bảy; đủ 7 ngày thì một đoạn, thiếu thì cắt khoảng from-to thành các đoạn liên tục. from/to tính cả hai đầu; "value" là một ngày. Mỗi phần tử date ra tối đa ba loại update: inventory (mỗi phòng một lần mỗi đoạn), restrictions và rates (mỗi gói giá). Restrictions hoặc rates mà thiếu rateplanid thì lỗi dòng. Giá và phụ thu là số >= 0, giữ dưới dạng chuỗi thập phân (không dùng float), price_basis "after_tax", age_code "ADULT", không có tiền tệ. Một khoảng ngày dài hơn max_date_span_days (mặc định 730) là lỗi dòng. min_stay, max_stay là số nguyên >= 1 và max không nhỏ hơn min.
- rationale: Theo mô tả của người dùng (delta, không phải snapshot) nên thiếu trường nghĩa là không đổi, không phải về 0 hay mở. Giá giữ dạng chữ để không mất độ chính xác. Các quy ước này CHƯA kiểm với nhà cung cấp thật: from/to tính cả hai đầu, "0" là mở, không có tiền tệ đều là giả định.
- impacts: Đổi quy ước dow hay cờ đóng làm thay nghĩa dữ liệu bên nhận; phải xác nhận với nhà cung cấp trước.
