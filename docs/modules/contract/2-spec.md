---
module: contract
---
# contract - Spec (tầng 2)

Design được tách thành yêu cầu, contract, tiêu chí nghiệm thu và task. Khung tự sinh từ design; điền qua tool `spec_fill`.

## CONT-S-001: Một tệp hợp đồng chuẩn là chỗ duy nhất ba lớp gặp nhau
- from: CONT-D-001
- derived_from: ce12bfa9
- status: ready
- requirement: Một tệp contract.py định nghĩa mọi kiểu dùng chung giữa ba lớp và không nhập module nào khác của dịch vụ. Lớp vào/ra đổi mã lỗi sang HTTP; lõi và chuẩn hóa chỉ ném IngestError mang mã chuẩn.
- contract: MessageKind: inventory, restrictions, rates (mỗi loại một topic). ErrorCode: 10 mã lạ (nghiệp vụ quy định), 12 hết dữ liệu hợp lệ, 20 dòng sai, 21 gói sai, 22 trace id sai, 23 thân quá lớn, 24 quá nhiều update, 25 tham số API sai, 30 chưa xác thực, 31 khách sạn lạ hoặc không có quyền, 40 xung đột chống trùng, 41 xung đột, 42 không thấy, 50 không lưu được. Update(kind, room_code, rate_plan_code|None, date_from, date_to, data), ngày tính cả hai đầu. Publisher.publish(kind, key, value: bytes, message_id) phải ném lỗi khi broker chưa xác nhận.
- acceptance: tests/test_layers.py::test_contract_imports_nothing_from_service qua; mọi mã lỗi dùng trong lõi, chuẩn hóa và HTTP có trong ErrorCode; bảng đổi mã lỗi sang HTTP của io/http.py phủ đủ mọi mã ném ra từ lõi.
- tasks:
  - [x] Định nghĩa kiểu và mã lỗi
  - [x] Test quét import giữ ranh giới
  - [ ] Hợp đồng message với bên nhận (chưa có bên nhận thật)
