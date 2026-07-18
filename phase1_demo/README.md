# Student Companion Phase 1 Demo

Scaffold độc lập cho bản demo Student Companion dành cho học sinh cấp 3.

## Trạng thái hiện tại

**TASK 1 hoàn tất ở mức domain contracts:** package hiện có enum, input model,
derived-result model, validation và JSON serialization deterministic bằng
Pydantic v2. Chưa có business calculation, dữ liệu synthetic, pipeline, API
hoặc giao diện.

## Phạm vi thư mục

Tất cả code và artifact mới của demo phải nằm trong `phase1_demo/`. Market
pipeline hiện hữu nằm ngoài phạm vi sửa đổi; các task sau chỉ được đọc output
đã tạo sẵn khi cần market context.

## Cấu trúc

- `student_companion/domain/`: enum và domain data contracts thuần.
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

## Kiểm tra domain contracts

```powershell
pytest phase1_demo/tests -q
python -c "from phase1_demo.student_companion.domain import StudentProfile, StudentSnapshot; print('domain-imports-ok')"
```

## Chạy demo

Chưa áp dụng trong TASK 1. Hướng dẫn chạy sẽ được bổ sung khi pipeline được
triển khai trong task được phê duyệt riêng.
