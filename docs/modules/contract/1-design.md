---
module: contract
prefix: CONT
---
# contract - Design (tầng 1)

Vì sao và cái gì: quyết định nghiệp vụ và kỹ thuật của module. Chỉ ghi qua tool `design_record` / `design_update`.

## CONT-D-001: Một tệp hợp đồng chuẩn là chỗ duy nhất ba lớp gặp nhau
- date: 2026-10-06
- status: accepted
- decision: contract.py chứa mọi thứ dùng chung giữa lớp vào/ra, lớp chuẩn hóa và lõi: loại message (MessageKind: inventory, restrictions, rates), mã lỗi (ErrorCode), RowError, IngestError, Limits, Update, NormalizedSubmission, PartnerInfo, AckResult và giao diện Publisher (publish(kind, key, value, message_id), phải ném lỗi khi broker chưa xác nhận). Tệp không nhập module nào khác của dịch vụ. Chỉ UNKNOWN_CODE (10) do nghiệp vụ quy định; các mã còn lại (12, 20-25, 30, 31, 40-42, 50) do dịch vụ tự đặt. Ngày trong Update tính cả hai đầu (giả định, chưa xác nhận với nhà cung cấp).
- rationale: Để đổi nhà cung cấp hay broker chỉ sửa lớp vào/ra và chuẩn hóa, không sửa lõi. Cấm nhập ngược được giữ bằng tests/test_layers.py chứ không chỉ ghi trong tài liệu. Mã lỗi gom một chỗ để lớp HTTP đổi sang trạng thái HTTP mà lõi không biết HTTP.
- impacts: Đổi một mã lỗi hay tên loại message là đổi hợp đồng với bên nhận (Inventory, worker) và với nhà cung cấp; làm theo kiểu thêm vào.
