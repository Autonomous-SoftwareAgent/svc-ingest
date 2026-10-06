---
module: catalog
prefix: CATL
---
# catalog - Design (tầng 1)

Vì sao và cái gì: quyết định nghiệp vụ và kỹ thuật của module. Chỉ ghi qua tool `design_record` / `design_update`.

## CATL-D-001: Danh mục chỉ là bản sao để đổi mã; nạp qua API nội bộ; cache 24 giờ theo tiến trình
- date: 2026-10-06
- status: accepted
- decision: catalog.py giữ đối tác, khách sạn được phép (hotel_access), phòng (room_map) và gói giá (rate_plan_map). Nạp bằng set_hotel, set_room, set_rate_plan (upsert: sửa trước, không có hàng thì thêm; thử lại một lần khi xung đột) qua API nội bộ; mỗi lần ghi xóa cache của đối tác đó (invalidate_partner) nên đổi có hiệu lực ngay trong tiến trình hiện tại. TtlCache khóa (partner_id, hotel_code), hết hạn sau catalog_cache_ttl_seconds (mặc định 86400); hết hạn khi đã trôi đúng ttl. Đăng ký đối tác kiểm: name, username, format không rỗng và tối đa 128 ký tự; mật khẩu tối thiểu 8 ký tự; trùng name hoặc username là mã 41.
- rationale: Theo mô tả: Ingest đổi mã từ bản sao danh mục nhớ tạm 24 giờ, không phải dữ liệu gốc. Nguồn danh mục thật (dịch vụ Catalog) chưa có nên tạm nạp qua API nội bộ.
- impacts: Cache chỉ có hiệu lực trong một tiến trình: sửa danh mục ở tiến trình khác thì tiến trình này thấy muộn tới 24 giờ (đã kiểm bằng test đồng hồ giả). Nguồn danh mục thật chưa chốt.
