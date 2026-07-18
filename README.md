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
  crawl-service package          core/API repository layer
                                      ↑
profile-service → student profile → matching/recommendation → frontend
```

Luồng tích hợp downstream dùng `career_id`, `skill_id`, `province`,
`work_mode`, `taxonomy_version` và `snapshot_version`; không join chỉ bằng tên
hiển thị.

## Các thành phần

- `core/`: FastAPI core skeleton, shared market contracts và logic trung tâm
  trong các phase sau. Core chỉ đọc `data/processed/`.
- `profile-service/`: FastAPI skeleton thu thập và quản lý hồ sơ học sinh.
- `frontend/`: React/Vite skeleton; gọi API thay vì đọc dữ liệu trực tiếp.
- `crawl-service/`: service sở hữu Data Layer Phase 1 production, gồm
  collectors, adapters, normalization, extraction, lifecycle, dedup,
  aggregation, quality reports và handoff validation.
- `backend/shared/taxonomy.json`: taxonomy canonical duy nhất.
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

Các lệnh cũ trong `run_pipeline.py` và `scripts/` vẫn hoạt động dưới dạng
compatibility wrappers và có thể được xóa sau hackathon.

Nguồn production hiện gồm Greenhouse NAVER Vietnam và ba trang public listing
ViecOi. TopCV bị tắt do access challenge và chỉ nằm trong `experiments/topcv/`.

## Chạy toàn hệ thống

```powershell
Copy-Item .env.example .env
docker compose up --build
```

- Core: `http://localhost:8000`
- Profile service: `http://localhost:8001`
- Frontend development: chạy `npm install` và `npm run dev` trong `frontend/`.

`crawl-service` mặc định chạy `status`. Có thể override container command bằng
`python -m crawl_service collect-greenhouse`, `collect-viecoi`, `collect-all`
hoặc `pipeline` cho job thủ công/cron.

## Shared taxonomy và data contracts

Taxonomy canonical là `backend/shared/taxonomy.json`. File taxonomy draft cũ
trong `core/shared/` đã được thay bằng loader trỏ tới canonical file. Market
contracts cho core/API nằm tại `core/shared/contracts/market.py`; schema nội bộ
của pipeline nằm tại `crawl-service/src/crawl_service/models.py`. Profile và
Recommendation không cần import `crawl_service`; chúng dùng shared contract,
taxonomy, fixtures và processed tables.

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
python -m compileall crawl-service/src backend core scripts profile-service
python -m json.tool backend/shared/taxonomy.json
docker compose config
npm --prefix frontend run build
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
