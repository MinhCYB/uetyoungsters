# Career Compass — Phase 1 Data Layer

Phase 1 xây dựng lớp dữ liệu tuyển dụng có thể truy vết, chuẩn hóa và kiểm
soát chất lượng. Logic production dùng lại được tập trung tại `backend/data/`;
`scripts/` chỉ là các entry point mỏng.

## Phạm vi Phase 1

Bao gồm thu thập đa nguồn, lưu raw, chuẩn hóa schema, nghề, địa điểm, lương,
seniority và work mode; trích xuất kỹ năng; làm sạch boilerplate; deduplicate;
theo dõi lifecycle; tổng hợp nhu cầu nghề–kỹ năng; báo cáo coverage và test.

Không bao gồm API cho frontend, dashboard, recommendation, skill-gap scoring,
LLM fallback, mô hình ML hoặc nguồn crawl mới ngoài Greenhouse và ViecOi.

## Kiến trúc

```text
config/sources.yaml
        ↓
collectors → data/raw → data/interim
        ↓
source adapters → RawJobPosting
        ↓
description cleaning → normalization → taxonomy extraction
        ↓
same-source dedup + cross-source candidate grouping
        ↓
lifecycle → jobs_clean/job_skills
        ↓
aggregation → quality/coverage/gap reports
```

- `backend/data/collectors/`: thu thập và parse theo từng nguồn.
- `backend/data/pipeline.py`: adapters và schema chung.
- `backend/data/normalization.py`: chuẩn hóa dùng chung.
- `backend/data/extraction.py`: mapping deterministic bằng taxonomy.
- `backend/data/lifecycle.py`: trạng thái lịch sử của tin.
- `backend/data/aggregation.py`: nhu cầu nghề và ma trận nghề–kỹ năng.
- `backend/data/quality.py`: báo cáo chất lượng, coverage và taxonomy gap.
- `backend/shared/taxonomy.json`: nguồn cấu hình chính cho nghề, skill, tỉnh.

## Nguồn production

### Greenhouse NAVER Vietnam

- `source_id`: `greenhouse_navervietnam`.
- Greenhouse public API chính thức.
- Có full job description và raw JSON.
- Coverage thiên về một doanh nghiệp, không đại diện toàn thị trường.

### ViecOi

- `source_id`: `viecoi_listing`.
- Chỉ đọc ba trang public listing, tối đa 90 tin.
- Có title, company, salary, location, deadline và listing skill tags.
- Không mở detail page; `detail_pages_enabled: false`.
- Delay 6–10 giây theo `config/sources.yaml` và dừng khi gặp 403, 429 hoặc
  challenge.

### TopCV

TopCV bị tắt do HTTP 403/Cloudflare challenge. Mã thử nghiệm nằm trong
`experiments/topcv/` và không thuộc production. Không dùng proxy, stealth,
cookie đăng nhập, CAPTCHA solver hoặc cơ chế bypass.

## Cài đặt và vận hành

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python scripts\collect_greenhouse.py
python scripts\collect_viecoi.py
python run_pipeline.py
pytest -q
```

Nếu collector thất bại hoặc trả rỗng, file interim hợp lệ trước đó không bị
ghi đè bằng dữ liệu rỗng.

## Outputs

```text
data/processed/jobs_clean.parquet
data/processed/job_skills.parquet
data/processed/job_lifecycle.parquet
data/processed/career_demand_summary.parquet
data/processed/career_skill_matrix.parquet

reports/data_quality.json
reports/source_coverage.json
reports/taxonomy_coverage.json
reports/viecoi_taxonomy_gap.csv
reports/viecoi_skill_gap.csv
reports/viecoi_location_gap.csv
reports/viecoi_skill_frequency.csv
reports/viecoi_unmapped_skills.csv
```

`jobs_clean` chỉ chứa snapshot current. `job_lifecycle` giữ lịch sử. Raw JSON,
listing HTML và đường dẫn raw/interim giữ provenance của dữ liệu nguồn.
`application_deadline_raw`, `listing_page`, `listing_url`, `collection_scope`
và `skills_raw` vẫn truy vết được trong ViecOi interim/raw; deadline không được
dùng thay cho `posted_at`.

## Schema và quy tắc dữ liệu

Khóa lifecycle là chuỗi `(source_id, source_job_id)`. `province` và
`work_mode` độc lập: job remote có thể có `province = None` và
`work_mode = REMOTE`; có tỉnh không tự suy ra onsite. Khi nguồn không cung cấp
ngày đăng thật, `posted_at = None`; `collected_at`, `source_updated_at` và
application deadline không được dùng làm ngày đăng.

ViecOi listing skill tags có `requirement_level = mentioned`. Greenhouse full
JD có thể phân loại `required`, `preferred` hoặc `not_required` theo ngữ cảnh.
Mapping Phase 1 hoàn toàn deterministic, không dùng LLM fallback.

Dedup cùng nguồn dùng `(source_id, source_job_id)`. Candidate giống nhau chéo
nguồn chỉ được gán chung `dedup_group_id` khi company, title và province đều
khớp; hai source record và provenance vẫn được giữ.

## Lifecycle

- Tin mới: `active`.
- Vắng 1–2 lần: `missing_unconfirmed`.
- Vắng đủ 3 lần: `inactive`.
- Hash thay đổi: `content_changed = true`.
- Tin quay lại: `reactivated = true`.
- `first_seen_at` được giữ ổn định; `last_seen_at` cập nhật khi thấy lại.
- ViecOi category page có bằng chứng `/danh-muc-` được đánh dấu `invalid`,
  không tính như job inactive và không vào aggregation/coverage thị trường.

## Giới hạn và đạo đức dữ liệu

Đây là snapshot của các nguồn đang theo dõi, không đại diện toàn bộ thị trường
lao động Việt Nam. Greenhouse có full JD nhưng chỉ từ NAVER Vietnam. ViecOi
bao phủ ba trang listing và không có full JD. Không vượt CAPTCHA, Cloudflare,
robots/access challenge hoặc sử dụng dữ liệu đăng nhập.

## Thêm nguồn

1. Đăng ký nguồn và giới hạn truy cập trong `config/sources.yaml`.
2. Đặt collector/parser đặc thù nguồn trong `backend/data/collectors/`.
3. Thêm adapter về `RawJobPosting` trong `backend/data/pipeline.py`.
4. Giữ entry point trong `scripts/` mỏng.
5. Thêm fixture, test provenance, empty-response safety và source coverage.

## Mở rộng taxonomy

Thêm canonical career/skill/location và alias cụ thể vào
`backend/shared/taxonomy.json`, tăng semantic version, chạy gap reports và thêm
regression test. Không tạo một career cho từng title; không dùng alias rộng như
“nhân viên”, “quản lý” hoặc “sales” nếu có nguy cơ map hàng loạt.

## Git

Raw, interim, processed, CSV/Parquet và report sinh tự động không được commit.
Chỉ commit code, cấu hình, taxonomy, tài liệu và fixture nhỏ phục vụ test.
