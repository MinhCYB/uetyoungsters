# RBAC và cấp tài khoản

## Khởi tạo lần đầu

Không có API public để tạo Superadmin. Sau khi database đã sẵn sàng, chạy đúng một lần:

```powershell
$env:SUPERADMIN_EMAIL="admin@example.com"
$env:SUPERADMIN_PASSWORD="mat-khau-rat-manh"
$env:DATABASE_URL="postgresql://cc_user:cc_pass@localhost:5432/career_compass"
python backend-api/bootstrap.py
```

Đặt `AUTH_SECRET` bằng secret ngẫu nhiên dài trước khi chạy production và đặt
`COOKIE_SECURE=true` khi phục vụ qua HTTPS.

## Chuỗi cấp tài khoản

1. Superadmin đăng nhập tại `/login`, tạo trường rồi tạo lời mời Tenant Admin.
2. Tenant Admin tạo lớp, mời giáo viên và phân công giáo viên qua API.
3. Giáo viên chỉ có thể mời học sinh vào lớp có assignment đang hiệu lực.
4. Người nhận mở `/accept-invitation?token=...` và đặt mật khẩu.
5. Professional tự đăng ký tại `/register/professional`; backend luôn ép role
   `PROFESSIONAL` và `tenant_id = NULL`.

Trong môi trường hiện tại, token lời mời được trả cho dashboard để thử nghiệm.
Khi tích hợp email, gửi liên kết ở worker/email provider và không hiển thị token
trên giao diện production.

## Bảo mật

- Mật khẩu dùng bcrypt cost 12.
- Access token chỉ giữ trong bộ nhớ trình duyệt và sống 15 phút.
- Refresh token dạng ngẫu nhiên được hash trong database và gửi bằng cookie
  `HttpOnly`; token cũ bị thu hồi khi refresh.
- Backend đọc role và tenant từ user trong database ở mỗi request.
- Tenant Admin luôn bị giới hạn trong `tenant_id` của mình.
- Assignment giáo viên được kiểm tra cả ngày bắt đầu và ngày kết thúc.
- Các thao tác tạo tenant, mời tài khoản, phân công và chấp nhận lời mời có audit log.
