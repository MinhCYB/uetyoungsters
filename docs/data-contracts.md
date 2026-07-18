# Market Data Contracts

## Nguồn contract

- Internal extraction models: `backend/data/models.py`.
- Consumer market contracts: `core/shared/contracts/market.py`.
- Canonical taxonomy: `backend/shared/taxonomy.json`.

Core/API chỉ đọc processed tables. Frontend không đọc Parquet trực tiếp.

## `jobs_clean.parquet`

Primary key: `job_id`. Source identity: `(source_id, source_job_id)`.

| Field | Type | Nullable | Ghi chú |
|---|---|---:|---|
| job_id | string | no | Stable canonical job ID |
| source | string | no | Platform name |
| source_id | string | no | Registry source ID |
| source_job_id | string | no | Luôn chuẩn hóa về string |
| source_url | string | yes | Provenance URL |
| job_title_raw | string | no | Title nguồn |
| career_id | string | yes | Join taxonomy bằng ID |
| career_name | string | yes | Display name |
| company_name | string | yes | Tên doanh nghiệp đã làm sạch |
| province | string | yes | Null cho remote/unknown |
| work_mode | enum | no | ONSITE/HYBRID/REMOTE/UNSPECIFIED |
| salary_min_vnd | integer | yes | VND |
| salary_max_vnd | integer | yes | VND |
| salary_mid_vnd | number | yes | Chỉ có khi tính được |
| salary_disclosed | boolean | no | Cờ dùng cho salary aggregation |
| seniority_level | string | no | Normalized seniority |
| experience_min_years | number | yes | Số năm tối thiểu có bằng chứng |
| education_level | string | no | Normalized education |
| posted_at | date | yes | Null nếu nguồn không có ngày thật |
| collected_at | datetime | no | Thời điểm crawl, không phải posted_at |
| snapshot_version | string | no | Version snapshot |
| taxonomy_version | string | no | Version taxonomy dùng khi map |
| overall_confidence | number | no | 0–1 |
| is_active | boolean | no | Lifecycle current status |

## `job_skills.parquet`

Logical key: `(job_id, skill_id)`.

| Field | Type | Nullable | Ghi chú |
|---|---|---:|---|
| job_id | string | no | Join sang jobs_clean |
| career_id | string | yes | Join demand by canonical ID |
| skill_id | string | no | Canonical taxonomy ID |
| skill_name | string | no | Display name |
| raw_mention | string | no | Evidence từ nguồn |
| requirement_level | enum | no | required/preferred/not_required/mentioned |
| confidence | number | no | 0–1 |
| extraction_method | enum | no | taxonomy/fuzzy/rule/llm_fallback |

Không chuyển skill thành list string tự do vì sẽ mất ID, evidence và confidence.

## Aggregate tables

- `career_demand_summary.parquet`: group theo `career_id`, `province`,
  `work_mode`, `snapshot_version`; salary sample chỉ gồm disclosed salary.
- `career_skill_matrix.parquet`: liên kết career–skill theo ID và snapshot.
- `job_lifecycle.parquet`: lịch sử active/missing/inactive/reactivated/invalid.

`data_from` và `data_to` phải null nếu không có ngày đăng thật; không dùng ngày
crawl để tạo khoảng thời gian thị trường giả.

## Consumer guidance

Downstream phải join bằng `career_id`, `skill_id`, `province`, `work_mode`,
`taxonomy_version` và `snapshot_version`. Display names chỉ dùng cho UI.
Recommendation/profile schema không được nhập vào Data Layer models. Industry
và growth rate không được thêm nếu chưa có dữ liệu có bằng chứng.
