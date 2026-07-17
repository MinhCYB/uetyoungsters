# Career Compass — Data Layer

Pipeline dữ liệu việc làm với một nơi duy nhất chứa logic tái sử dụng: `backend/data/`.

```text
collector → raw → interim → description cleaning
          → normalization/extraction → processed
          → aggregation/quality
```

## Nguồn production

- `greenhouse_navervietnam`: Greenhouse public API, đang bật trong `config/sources.yaml`.
- `topcv`: đang tắt do HTTP 403/access challenge. Mã thử nghiệm được lưu tại `experiments/topcv/` và không thuộc pipeline production.

## Cài đặt

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Chạy

```bash
# Thu thập các Greenhouse board đang bật trong registry
python scripts/collect_greenhouse.py

# Chạy pipeline trên dữ liệu Greenhouse thật
python run_pipeline.py

# Kiểm thử
pytest -q
```

## Đầu ra chuẩn

```text
data/processed/jobs_clean.parquet
data/processed/job_skills.parquet
data/processed/career_demand_summary.parquet
data/processed/career_skill_matrix.parquet
reports/data_quality.json
```

`greenhouse_jobs_description_clean.parquet` chỉ là output trung gian phục vụ debug. Pipeline chính dùng tên đầu ra chung, không phụ thuộc tên nguồn.

## Quy ước phát triển

- Logic dùng lại đặt trong `backend/data/`.
- `scripts/` chỉ chứa entry point mỏng.
- Collector chưa đủ điều kiện production đặt trong `experiments/`.
- Thêm nguồn Greenhouse bằng cách cập nhật `config/sources.yaml`, không hard-code board trong collector.
- Không commit dữ liệu raw/interim/processed sinh tự động; chỉ commit fixture nhỏ phục vụ test.
