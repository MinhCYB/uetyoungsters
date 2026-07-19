# Tài khoản demo

Chỉ sử dụng trong môi trường local/demo.

Mật khẩu chung: `Demo@123456`

| Role | Email |
|---|---|
| SUPERADMIN | `superadmin.v2@demo.example.com` |
| TENANT_ADMIN | `admin.v2@demo.example.com` |
| HOMEROOM_TEACHER | `teacher.v2@demo.example.com` |
| STUDENT | `student.v2@demo.example.com` |
| PROFESSIONAL | `professional.v2@demo.example.com` |

Tạo hoặc cập nhật các tài khoản:

```powershell
docker compose exec backend-api python scripts/seed_demo_accounts.py
```

Có thể đổi mật khẩu chung cho lần seed bằng biến `DEMO_PASSWORD`.
