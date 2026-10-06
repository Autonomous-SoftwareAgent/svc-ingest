---
module: catalog
---
# catalog - Spec (tầng 2)

Design được tách thành yêu cầu, contract, tiêu chí nghiệm thu và task. Khung tự sinh từ design; điền qua tool `spec_fill`.

## CATL-S-001: Danh mục chỉ là bản sao để đổi mã; nạp qua API nội bộ; cache 24 giờ theo tiến trình
- from: CATL-D-001
- derived_from: f388ec88
- status: ready
- requirement: Danh mục đối tác, khách sạn, phòng, gói giá nạp được qua API nội bộ; thay đổi có hiệu lực ngay trong tiến trình hiện tại; ở tiến trình khác thấy muộn tới hết hạn cache.
- contract: register_partner(name, username, password, format) -> id; lỗi 25 (trường rỗng, quá 128 ký tự, mật khẩu dưới 8), 41 (trùng name hoặc username). set_hotel, set_room, set_rate_plan: upsert; lỗi 25 khi giá trị rỗng, 42 khi chưa có đối tác hoặc chưa cấp quyền khách sạn. get_catalog(partner_id) -> {partnerId, hotels:[{code,id,name,rooms:[{code,id,name}],ratePlans:[...]}]}. TtlCache(ttl, clock): get trả None khi trôi đủ ttl; invalidate_partner(id) chỉ xóa mục của đối tác đó. Cache không nhớ kết quả "không có quyền".
- acceptance: test_core.py: test_register_partner_validations, test_catalog_upserts_and_lookup, test_catalog_not_found_errors, test_catalog_change_is_visible_immediately_in_this_process, test_cache_serves_stale_catalog_until_ttl_when_changed_elsewhere, test_ttl_cache_basics; test_http.py::test_internal_partner_and_catalog_flow.
- tasks:
  - [x] Danh mục và cache
  - [ ] Nguồn danh mục thật (dịch vụ Catalog) chưa có
  - [ ] Chưa có trong bản gốc: biên độ dài tên 128 và 129 ký tự, mật khẩu Unicode
