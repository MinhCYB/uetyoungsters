# Student Companion Phase 1 — Architecture Skeleton

## Trạng thái

Tài liệu này chỉ mô tả scaffold của **TASK 0**. Chưa có pipeline, model,
synthetic data, API hay giao diện được triển khai.

## Mục tiêu kiến trúc

Demo Phase 1 là một module độc lập trong `phase1_demo/`. Module có thể **đọc**
market output hiện có nhưng không sửa, xóa hoặc phụ thuộc vào code nội bộ của
market pipeline.

```text
phase1_demo/
├── student_companion/
│   ├── domain/          # Business rules thuần, deterministic (task sau)
│   ├── application/     # Điều phối use case/pipeline (task sau)
│   └── infrastructure/  # Adapter đọc input/market output offline (task sau)
├── tests/               # Test business rules và integration (task sau)
├── ARCHITECTURE.md
└── README.md
```

## Ranh giới phụ thuộc dự kiến

Hướng phụ thuộc chỉ đi vào trong:

```text
infrastructure ──> application ──> domain
```

- `domain` không đọc file, không gọi mạng và không phụ thuộc framework.
- `application` điều phối các bước nhưng không chứa I/O cụ thể.
- `infrastructure` là nơi duy nhất được phép đọc market snapshot hiện có.
- Mọi artifact mới của demo phải nằm trong `phase1_demo/`.
- LLM và external API không nằm trong critical path.

## Luồng mục tiêu cho các task sau

```text
student input
  -> evidence normalization
  -> ability profile
  -> academic / exploration / decision gaps
  -> market context
  -> weekly plan
  -> post-test and activity result
  -> outcome evaluation
  -> updated snapshot
  -> before / after presentation
```

Luồng trên là định hướng, không phải chức năng đã có ở TASK 0.

## Market output đã audit

Các file dưới đây được đọc ở chế độ read-only từ `data/processed/`:

| Output | Số dòng tại thời điểm audit | Vai trò dự kiến |
|---|---:|---|
| `jobs_clean.parquet` | 106 | Chi tiết posting đã chuẩn hóa |
| `job_skills.parquet` | 350 | Quan hệ job–skill và mức yêu cầu |
| `job_lifecycle.parquet` | 108 | Trạng thái vòng đời posting |
| `career_demand_summary.parquet` | 73 | Nhu cầu theo nghề, tỉnh và work mode |
| `career_skill_matrix.parquet` | 275 | Tỷ trọng skill theo nhóm nghề |

Các khóa tích hợp quan trọng đã quan sát: `career_id`, `skill_id`, `province`,
`work_mode`, `snapshot_version` và `taxonomy_version` (ở các bảng có trường
tương ứng). Adapter ở task sau phải kiểm tra schema rõ ràng, không join bằng
tên hiển thị và không ghi ngược vào các file này.

## Quyết định của TASK 0

1. Dùng package Python độc lập dưới namespace `phase1_demo.student_companion`.
2. Tách ba lớp nhỏ để giữ business rules thuần và dễ test.
3. Không thêm dependency, framework, service hay build tool trong scaffold.
4. Không tạo dữ liệu mẫu hoặc output sinh tự động ở task này.

