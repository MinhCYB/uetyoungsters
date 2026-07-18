# Career Compass

Career Compass là bộ khung ứng dụng định hướng nghề nghiệp và lộ trình học tập
cá nhân hóa cho học sinh. Hệ thống kết hợp hồ sơ người học với snapshot dữ
liệu tuyển dụng có provenance, taxonomy và chỉ số chất lượng rõ ràng.

## Mục tiêu

- Thu thập và chuẩn hóa tín hiệu nhu cầu nghề nghiệp từ nguồn công khai.
- Xây hồ sơ học sinh có kiểm soát quyền riêng tư.
- Cung cấp dữ liệu có version cho core matching/recommendation trong các phase
  tiếp theo.
- Giữ frontend tách khỏi storage: frontend chỉ gọi API, không đọc Parquet.

## Kiến trúc tổng thể

```text
Greenhouse / ViecOi
        ↓
crawl_service collectors → raw → interim → processed tables
        ↓                              ↓
  crawl-service package          backend-api repository layer
                                      ↑
           student profile → matching/recommendation → frontend
```

Luồng tích hợp downstream dùng `career_id`, `skill_id`, `province`,
`work_mode`, `taxonomy_version` và `snapshot_version`; không join chỉ bằng tên
hiển thị.

## Các thành phần

- `backend-api/`: FastAPI modular monolith skeleton. Modules: auth, assessment,
  candidate, recommendation. Reads `data/processed/`.
- `ai-worker-service/`: async worker service for essay scoring and CV parsing.
- `nginx/`: reverse proxy routing `/api/` to backend-api.
- `crawl-service/`: service sở hữu Data Layer Phase 1 production, gồm
  collectors, adapters, normalization, extraction, lifecycle, dedup,
  aggregation, quality reports và handoff validation.
- `crawl-service/data/taxonomy.json`: taxonomy canonical duy nhất.
- `docs/`: thiết kế hệ thống, schema, data contracts và tài liệu vận hành.

Chi tiết Data Layer: [docs/data-layer-phase1.md](docs/data-layer-phase1.md).
Contract cho consumer: [docs/data-contracts.md](docs/data-contracts.md).

## Chạy Data Layer

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .\crawl-service

python -m crawl_service collect-greenhouse
python -m crawl_service collect-viecoi
python -m crawl_service pipeline
python -m crawl_service validate-handoff --fixtures-only
pytest -q
```



Nguồn production hiện gồm Greenhouse NAVER Vietnam và ba trang public listing
ViecOi. TopCV bị tắt do access challenge và chỉ nằm trong `experiments/topcv/`.

## Chạy toàn hệ thống

```powershell
docker compose up --build
```

- Backend API: `http://localhost:8000`
- Nginx proxy: `http://localhost:80` (`/api/` → backend-api)

`crawl-service` mặc định chạy `status`. Có thể override container command bằng
`python -m crawl_service collect-greenhouse`, `collect-viecoi`, `collect-all`
hoặc `pipeline` cho job thủ công/cron.

## Shared taxonomy và data contracts

Taxonomy canonical là `crawl-service/data/taxonomy.json`. Market contracts
và schema profile nằm tại `crawl-service/src/crawl_service/shared_contracts/`.
Schema nội bộ pipeline nằm tại `crawl-service/src/crawl_service/models.py`.
Backend-api và ai-worker-service không cần import `crawl_service`; chúng dùng
shared contract, taxonomy, fixtures và processed tables.

Không tự tạo `industry`, `growth_rate` hoặc `posted_at` khi nguồn không cung
cấp bằng chứng. `province` và `work_mode` là hai chiều độc lập.

## Generated outputs

```text
data/processed/jobs_clean.parquet
data/processed/job_skills.parquet
data/processed/job_lifecycle.parquet
data/processed/career_demand_summary.parquet
data/processed/career_skill_matrix.parquet
reports/data_quality.json
reports/source_coverage.json
reports/taxonomy_coverage.json
```

Raw, interim, processed, reports và cache là generated artifacts, không được
commit. Fixture nhỏ trong `tests/fixtures/` chỉ dùng cho test tích hợp và không
được xem là production data.

## Testing

```powershell
pytest -q
python -m compileall crawl-service/src backend-api ai-worker-service
python -m json.tool crawl-service/data/taxonomy.json
docker compose config
```

## Đạo đức dữ liệu

Không bypass CAPTCHA/Cloudflare, không dùng proxy rotation, stealth browser,
cookie đăng nhập hoặc CAPTCHA solver. ViecOi chỉ dùng public listing fields và
không mở detail page. Collector dừng khi gặp 403, 429 hoặc challenge.

## Giới hạn hiện tại

- Snapshot không đại diện toàn bộ thị trường lao động Việt Nam.
- Greenhouse hiện thiên về một doanh nghiệp; ViecOi chỉ có ba trang listing.
- Phase 1 chưa triển khai recommendation model, dashboard hoặc LLM fallback.
- Generated Parquet không có trong clone mới; dùng fixture integration cho test
  contract hoặc chạy collectors/pipeline để tạo snapshot local.
