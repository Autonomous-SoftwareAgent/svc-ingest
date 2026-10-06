---
module: http
---
# http - Spec (tầng 2)

Design được tách thành yêu cầu, contract, tiêu chí nghiệm thu và task. Khung tự sinh từ design; điền qua tool `spec_fill`.

## HTTP-S-001: POST /v1/inventory-rates: thứ tự kiểm, giới hạn kích thước và bảng đổi mã lỗi sang HTTP
- from: HTTP-D-001
- derived_from: 9ffc2284
- status: ready
- requirement: POST /v1/inventory-rates kiểm theo thứ tự xác thực, X-Trace-Id, kích thước, rồi mới xử lý; trả mã và thân đúng bảng; không lộ thông tin xác thực hay chi tiết lỗi nội bộ.
- contract: Yêu cầu: Authorization Basic; X-Trace-Id UUID bắt buộc; X-Channel-Id tùy chọn (cắt tối đa 128); thân tối đa INGEST_MAX_BODY_BYTES. 202: {"status":"Success","data":{"ticketId","duplicate"},"errors":[{code,shortText,path?}]}. Lỗi: {"status":"Fail","errors":[...]}. Mã HTTP: 400 (12,20,21,22,25), 401 (30,31, kèm WWW-Authenticate: Basic), 409 (40,41), 413 (23,24), 404 (42), 503 (50 và mọi lỗi bất ngờ).
- acceptance: test_http.py: test_missing_or_malformed_basic_is_401, test_wrong_credentials_same_401, test_auth_is_checked_before_body_is_parsed, test_trace_id_required_and_must_be_uuid, test_unparseable_body_is_400, test_body_too_large_is_413, test_success_returns_202_with_ticket_after_data_is_stored, test_resend_same_key_and_body_returns_same_ticket, test_same_key_different_body_is_409, test_unknown_room_row_dropped_with_code_10_rest_goes, test_all_rows_invalid_rejects_whole_request, test_hotel_not_allowed_is_401, test_database_failure_is_never_acked, test_response_and_logs_do_not_echo_credentials.
- tasks:
  - [x] Endpoint và bảng mã
  - [ ] Chưa có trong bản gốc: thân rỗng, đúng bằng giới hạn và vượt một byte, UTF-8 sai, thân không có Content-Length, dạng UUID khác nhau, đầu vào Unicode
  - [ ] Đo độ trễ p99 (dưới 10 giây kênh sở hữu, dưới 60 giây kênh đối tác): chưa đo

## HTTP-S-002: API nội bộ mặc định từ chối, và /healthz kiểm cơ sở dữ liệu thật
- from: HTTP-D-002
- derived_from: fecb4674
- status: ready
- requirement: API nội bộ mặc định từ chối khi chưa đặt token; thân sai chỉ báo vị trí và lý do, không lặp lại giá trị; /healthz báo trạng thái DB thật.
- contract: Bearer khớp INGEST_INTERNAL_TOKEN (compare_digest) hoặc 401 mã 30 kèm WWW-Authenticate: Bearer. POST /internal/v1/partners {name, username, password, format?="inventory-rates-json"} -> 201 {id}; GET /internal/v1/partners; PUT /internal/v1/partners/{id}/hotels/{hotel_code} {hotelId, name?}; PUT .../rooms/{room_code} {roomId, name?}; PUT .../rate-plans/{code} {ratePlanId, name?}; GET /internal/v1/partners/{id}/catalog. Trường lạ trong thân hoặc sai kiểu: 400 mã 25. GET /healthz -> 200 {"database":"ok","outboxPending":n} hoặc 503 mã 50.
- acceptance: test_http.py: test_internal_api_requires_token, test_internal_api_denied_by_default_when_token_not_configured, test_internal_partner_and_catalog_flow, test_internal_validation_and_errors, test_healthz_reports_database_and_pending, test_healthz_503_when_database_down.
- tasks:
  - [x] API nội bộ và healthz
  - [ ] Kiểm token trước khi kiểm thân (hiện thân sai nhận 400 trước 401)
  - [ ] Chỉ số, cảnh báo, phân quyền chi tiết (chưa làm)
