---
module: auth
prefix: AUTH
---
# auth - Design (tầng 1)

Vì sao và cái gì: quyết định nghiệp vụ và kỹ thuật của module. Chỉ ghi qua tool `design_record` / `design_update`.

## AUTH-D-001: Mật khẩu đối tác băm scrypt; tên lạ vẫn tốn thời gian băm
- date: 2026-10-06
- status: accepted
- decision: hash_password dùng scrypt (n=2^14, r=8, p=1, muối 16 byte ngẫu nhiên), lưu dạng "scrypt$n$r$p$muối$băm"; verify_password so sánh bằng hmac.compare_digest và trả False (không ném) khi bản lưu sai dạng. authenticate chỉ nhận đối tác active; tên đăng nhập không có trong bảng vẫn chạy một lần verify với băm giả để thời gian gần như nhau, nên không dò được tên đăng nhập.
- rationale: Không lưu mật khẩu thô; thư viện chuẩn của Python đủ dùng. Sai tên và sai mật khẩu trả cùng một câu trả lời 401 mã 30.
- impacts: Mỗi yêu cầu của đối tác tốn một lần băm scrypt (tốn CPU, chưa đo tải). Chưa có khóa tài khoản khi đoán mật khẩu liên tục, chưa đổi mật khẩu qua API.
