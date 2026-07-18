# Student Companion Phase 1 — Architecture Skeleton

## Trạng thái

Scaffold, domain contracts và vertical slice Phase 1 đã hoàn tất. Demo có
synthetic inputs, deterministic pipeline, standard-library local API và static
UI tiếng Việt.

## Mục tiêu kiến trúc

Demo Phase 1 là một module độc lập trong `phase1_demo/`. Module có thể **đọc**
market output hiện có nhưng không sửa, xóa hoặc phụ thuộc vào code nội bộ của
market pipeline.

```text
phase1_demo/
├── fixtures/            # Synthetic student inputs và market fallback
├── static/              # HTML, CSS, vanilla JavaScript
├── scripts/             # Preflight end-to-end
├── run_demo.py          # ThreadingHTTPServer và local JSON API
├── student_companion/
│   ├── domain/          # Contracts và deterministic business rules
│   ├── application/     # State machine và use-case orchestration
│   └── infrastructure/  # Fixture loader và read-only market adapter
├── tests/               # Domain, pipeline và local server tests
├── ARCHITECTURE.md
└── README.md
```

## Ranh giới phụ thuộc dự kiến

Hướng phụ thuộc chỉ đi vào trong:

```text
HTTP/UI ──> application ──> domain
               ↑
         infrastructure
```

- `domain` không đọc file, không gọi mạng và không phụ thuộc framework.
- `application` điều phối các bước nhưng không chứa I/O cụ thể.
- `infrastructure` là nơi duy nhất được phép đọc market snapshot hiện có.
- Mọi artifact mới của demo phải nằm trong `phase1_demo/`.
- LLM và external API không nằm trong critical path.

## Luồng đã triển khai

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

Luồng trên chạy end-to-end qua `DemoService`; local API chỉ gọi service và không
duplicate business logic.

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

## Quyết định của TASK 0–1

1. Dùng package Python độc lập dưới namespace `phase1_demo.student_companion`.
2. Tách ba lớp nhỏ để giữ business rules thuần và dễ test.
3. Không thêm dependency, framework, service hay build tool trong scaffold.
4. Không tạo dữ liệu mẫu hoặc output sinh tự động ở task này.
5. Domain contracts dùng Pydantic v2, từ chối field dư và giá trị NaN/infinite.
6. ID và timestamp đều là field bắt buộc do caller cung cấp; không có default
   theo thời gian hiện tại hoặc ID ngẫu nhiên.
7. Derived models chỉ biểu diễn kết quả và kiểm tra consistency; chưa sinh ra
   ability, gap, plan hoặc outcome.
