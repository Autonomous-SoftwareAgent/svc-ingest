---
module: auth
---
# auth - Spec (tầng 2)

Design được tách thành yêu cầu, contract, tiêu chí nghiệm thu và task. Khung tự sinh từ design; điền qua tool `spec_fill`.

## AUTH-S-001: Mật khẩu đối tác băm scrypt; tên lạ vẫn tốn thời gian băm
- from: AUTH-D-001
- derived_from: 0110e44a
- status: ready
- requirement: Mật khẩu chỉ lưu dạng băm scrypt có muối; xác thực không phân biệt tên lạ với sai mật khẩu về cả kết quả lẫn thời gian xấp xỉ; đối tác không còn active thì không vào được.
- contract: hash_password(p) -> "scrypt$16384$8$1$<muối hex>$<băm hex>". verify_password(p, stored) -> bool, không ném khi bản lưu sai dạng. authenticate(engine, username, password) -> PartnerInfo(id, name, format) hoặc None.
- acceptance: test_core.py: test_password_is_stored_hashed, test_authenticate, test_inactive_partner_cannot_authenticate; test_http.py: test_wrong_credentials_same_401, test_response_and_logs_do_not_echo_credentials.
- tasks:
  - [x] Băm và xác thực
  - [ ] Khóa tài khoản khi đoán mật khẩu liên tục, đổi mật khẩu qua API (chưa làm)
  - [ ] Thời gian xác thực chưa đo, chỉ kiểm có chạy băm giả
