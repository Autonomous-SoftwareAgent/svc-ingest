---
module: normalize
---
# normalize - Spec (tầng 2)

Design được tách thành yêu cầu, contract, tiêu chí nghiệm thu và task. Khung tự sinh từ design; điền qua tool `spec_fill`.

## NORM-S-001: Mỗi định dạng của nhà cung cấp là một module tự đăng ký; lỗi một dòng khác lỗi cả gói
- from: NORM-D-001
- derived_from: 968bcff2
- status: ready
- requirement: Có một registry định dạng; thêm định dạng là thêm một tệp trong normalize/. inventory-rates-json đọc InvResRateRequest và trả NormalizedSubmission. Lỗi cả gói thì ném IngestError (21, 24); lỗi một dòng thì bỏ dòng và ghi RowError mã 20 kèm đường dẫn room[i].date[j].
- contract: parse(body: bytes, limits: Limits) -> NormalizedSubmission(hotel_code, updates, row_errors). Cả gói sai (mã 21): không phải JSON, không phải object, thiếu hotelid (chuỗi không rỗng), thiếu room (danh sách không rỗng). Quá limits.max_updates (mã 24). register(name) ném RuntimeError khi trùng tên; get(name) trả None nếu chưa đăng ký.
- acceptance: test_normalize.py: test_registered_and_discoverable, test_bad_row_is_dropped_with_error_and_others_survive, test_bad_room_entry_does_not_stop_next_room, test_payload_errors_reject_whole_request, test_too_many_updates_rejects_whole_request, test_registry_rejects_duplicate_names; test_layers.py::test_normalize_modules_do_not_import_each_other.
- tasks:
  - [x] Registry và nạp tự động
  - [x] Module inventory-rates-json
  - [ ] Bắt RecursionError với JSON lồng cực sâu (chưa có trong bản gốc)
  - [ ] Định dạng thứ hai (chưa có nhà cung cấp)

## NORM-S-002: Quy ước đọc gói inventory-rates-json: bỏ trường không gửi, tách theo thứ trong tuần, giữ giá dạng chữ
- from: NORM-D-002
- derived_from: 5329bdf3
- status: ready
- requirement: Quy ước đọc dữ liệu inventory-rates-json: bỏ trường không gửi, cờ đóng là chuỗi, tách theo thứ trong tuần, giá giữ dạng chữ thập phân không tiền tệ, khoảng ngày giới hạn.
- contract: Không gửi hoặc null: bỏ qua; roomstosell số nguyên >= 0 (0 là thật, bool và số thực sai). closed, closedonarrival, closedondeparture: "0" mở, chuỗi khác đóng, rỗng bỏ qua, không phải chuỗi sai. minimumstay, maximumstay nguyên >= 1, max >= min. dow danh sách không rỗng các số 1..7 (1 = Chủ nhật), đủ 7 thì không cắt. date: "value" một ngày hoặc from/to dạng yyyy-MM-dd hợp lệ, to >= from, dài tối đa limits.max_span_days. price: danh sách không rỗng, NumberOfGuests nguyên >= 1 không lặp, value số hữu hạn >= 0, ra chuỗi thập phân giữ nguyên; kèm price_basis "after_tax", age_code "ADULT"; extraadultrate, extrachildrate số >= 0. Restrictions hoặc rates cần rateplanid. Mỗi gói giá (không lặp) một update restrictions và một update rates; mỗi đoạn ngày một update inventory.
- acceptance: test_normalize.py: test_full_example_splits_into_three_kinds, test_single_day_uses_value, test_dow_cuts_range_into_continuous_segments, test_dow_one_is_sunday_seven_is_saturday, test_absent_fields_are_skipped_not_zero, test_zero_rooms_is_a_real_value, test_closed_flag_zero_is_open_anything_else_closed, test_empty_flag_is_skipped, test_two_rate_plans_one_inventory_two_each_of_others, test_decimal_amounts_keep_exact_text, test_element_with_nothing_to_update_is_an_error.
- tasks:
  - [x] Quy ước theo mô tả của người dùng
  - [ ] Xác nhận với nhà cung cấp thật: from/to cả hai đầu, "0" là mở, tiền tệ
  - [ ] Ca biên chưa có trong bản gốc: giá 0, âm, rất lớn, NaN; ngày 2026-02-30; năm nhuận; ký tự Unicode trong mã
