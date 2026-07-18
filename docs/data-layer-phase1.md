# Data Layer Phase 1

## Phạm vi

Phase 1 thu thập dữ liệu đa nguồn, lưu raw có provenance, chuẩn hóa schema,
nghề, địa điểm, lương, seniority và work mode; trích xuất skill; làm sạch
boilerplate; deduplicate; theo dõi lifecycle; aggregation và quality reports.

Phase này không xây API frontend, recommendation, skill-gap scoring, dashboard,
LLM recommendation hoặc mô hình ML.

## Nguồn production

### Greenhouse NAVER Vietnam

- Public API chính thức, `source_id=greenhouse_navervietnam`.
- Có full JD và raw JSON.
- Snapshot Phase 1 đã kiểm thử với 16 jobs.

### ViecOi

- Public listing qua requests, `source_id=viecoi_listing`.
- Ba trang, tối đa 90 jobs, delay 6–10 giây.
- Chỉ dùng title, company, salary, location, deadline và skill tags trên card.
- `detail_pages_enabled=false`.

### TopCV

TopCV bị tắt do HTTP 403/Cloudflare challenge. Mã thử nghiệm nằm tại
`experiments/topcv/` và không thuộc production.

## Pipeline

```text
config/sources.yaml
  → crawl_service.collectors
  → data/raw
  → data/interim
  → source adapters / RawJobPosting
  → description cleaning
  → normalization + taxonomy extraction
  → same-source dedup / cross-source candidate grouping
  → lifecycle
  → processed tables
  → aggregation + quality/coverage/gap reports
```

Implementation production duy nhất nằm trong
`crawl-service/src/crawl_service/`; `scripts/` chỉ là compatibility wrapper.

## Quy tắc dữ liệu

- Lifecycle key: `(source_id, source_job_id)` dạng string.
- Không dùng `collected_at`, `source_updated_at` hoặc application deadline làm
  `posted_at`.
- Remote có thể có `province=null`, `work_mode=REMOTE`.
- Có province không tự suy ra onsite.
- ViecOi listing skills có `requirement_level=mentioned`.
- Greenhouse full JD có thể phân loại required/preferred/not_required.
- Mapping deterministic bằng taxonomy; không dùng LLM fallback.
- Trùng cùng nguồn được loại bằng source identity. Candidate chéo nguồn chỉ
  dùng chung `dedup_group_id`, không mất source record/provenance.

## Lifecycle

- Mới: `active`.
- Vắng 1–2 lần: `missing_unconfirmed`.
- Vắng đủ 3 lần: `inactive`.
- Hash đổi: `content_changed=true`.
- Quay lại: `reactivated=true`.
- ViecOi category URL có `/danh-muc-`: `invalid`, không tính như market job.

## Outputs và reports

Canonical outputs nằm trong `data/processed/`; reports nằm trong `reports/`.
Chi tiết field và consumer guidance xem [data-contracts.md](data-contracts.md).

## Vận hành

```powershell
pip install -e .\crawl-service
python -m crawl_service collect-greenhouse
python -m crawl_service collect-viecoi
python -m crawl_service pipeline
python -m crawl_service validate-handoff --production-only
pytest -q
```

Các command cũ vẫn tương thích trong thời gian hackathon.

Nếu collector trả rỗng hoặc thất bại, interim snapshot hợp lệ trước đó không bị
ghi đè bằng file rỗng.

## Coverage Phase 1 đã xác minh

```text
Current jobs:                    106
Greenhouse / ViecOi:             16 / 90
Career mapping:                  106 / 106
Location non-remote:             101 / 104
Remote jobs:                     2
Jobs có mapped skill:            101 / 106
ViecOi jobs có mapped skill:     85 / 90
Duplicate current rows:          0
Lifecycle active / invalid:      106 / 2
Taxonomy version:                0.4.0
```

Đây là snapshot từ các nguồn đang theo dõi, không phải thống kê đại diện toàn
bộ thị trường lao động Việt Nam.
