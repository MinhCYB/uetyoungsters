# Student Companion Phase 1 Demo

Scaffold độc lập cho bản demo Student Companion dành cho học sinh cấp 3.

## Trạng thái hiện tại

**TASK 0 hoàn tất ở mức scaffold:** repository và schema market output đã được
audit; package Python cùng ranh giới kiến trúc đã được tạo. Chưa có business
logic, dữ liệu synthetic, API hoặc giao diện.

## Phạm vi thư mục

Tất cả code và artifact mới của demo phải nằm trong `phase1_demo/`. Market
pipeline hiện hữu nằm ngoài phạm vi sửa đổi; các task sau chỉ được đọc output
đã tạo sẵn khi cần market context.

## Cấu trúc

- `student_companion/domain/`: vị trí dự kiến cho business rules thuần.
- `student_companion/application/`: vị trí dự kiến cho điều phối use case.
- `student_companion/infrastructure/`: vị trí dự kiến cho adapter offline.
- `tests/`: vị trí dự kiến cho test của từng business rule.
- `ARCHITECTURE.md`: ranh giới phụ thuộc và kết quả audit schema.

## Smoke check

Từ repository root:

```powershell
python -c "import phase1_demo.student_companion as sc; print(sc.__version__)"
```

Kết quả mong đợi ở TASK 0: `0.0.0`.

## Chạy demo

Chưa áp dụng trong TASK 0. Hướng dẫn chạy sẽ được bổ sung khi pipeline được
triển khai trong task được phê duyệt riêng.

