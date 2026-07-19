# Tài khoản demo

Chỉ sử dụng trong môi trường local/demo.

Mật khẩu chung: `Demo@123456`

| Role | Email |
|---|---|
| SUPERADMIN | `superadmin@demo.example.com` |
| TENANT_ADMIN | `admin@demo.example.com` |
| HOMEROOM_TEACHER | `teacher@demo.example.com` |
| STUDENT | `student@demo.example.com` |
| PROFESSIONAL | `professional@demo.example.com` |

Tạo hoặc cập nhật các tài khoản:

```powershell
docker compose exec backend-api python scripts/seed_demo_accounts.py
```

Có thể đổi mật khẩu chung cho lần seed bằng biến `DEMO_PASSWORD`.
