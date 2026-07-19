# Career Compass

Career Compass là hệ thống định hướng nghề nghiệp và xây dựng lộ trình học tập cá nhân hóa. Hệ thống thu thập tin tuyển dụng công khai, kết hợp dữ liệu nghề nghiệp O*NET, chuẩn hóa dữ liệu vào PostgreSQL và cung cấp API cho frontend.

## Thành phần chính

```text
Greenhouse / ViecOi / O*NET
             ↓
        crawl-service ──→ PostgreSQL
             ↓                 ↓
          Gemini          backend-api
       (dịch Việt)             ↓
                         frontend + nginx
```

- `frontend/`: giao diện người dùng.
- `backend-api/`: API nghề nghiệp, đánh giá và tài khoản.
- `crawl-service/`: crawl, chuẩn hóa, dịch dữ liệu nghề và ghi PostgreSQL.
- `ai-worker-service/`: gateway gọi Gemini; API key chỉ nằm trong biến môi trường.
- `roadmap-service/`: tạo lộ trình nghề nghiệp.
- `nginx/`: cổng truy cập chung tại `http://localhost`.
- `config/onet_career_map.yaml`: ánh xạ nghề nội bộ sang mã O*NET-SOC.
- `data/`: dữ liệu raw, interim và processed được sinh khi chạy pipeline.

## Yêu cầu

- Docker Desktop đang chạy.
- Docker Compose v2.
- Một Gemini API key nếu cần dịch nội dung O*NET sang tiếng Việt.
- PowerShell trên Windows, hoặc shell tương đương trên macOS/Linux.

## 1. Cấu hình môi trường

Tại thư mục gốc của project, tạo `.env` từ file mẫu:

```powershell
Copy-Item .env.example .env
```

Mở `.env` và thay giá trị sau:

```dotenv
GEMINI_API_KEY=your_gemini_api_key_here
```

Không commit `.env` và không hardcode API key trong mã nguồn. Docker Compose tự đọc `.env` ở thư mục chứa `docker-compose.yml`.

## 2. Khởi động hệ thống

### Cách nhanh bằng script

Project có một script PowerShell gom các thao tác thường dùng:

```powershell
# Xem danh sách lệnh
.\scripts\dev.ps1 help

# Build và khởi động lại toàn bộ hệ thống
.\scripts\dev.ps1 rebuild

# Crawl, chuẩn hóa, dịch phần thay đổi và publish database
.\scripts\dev.ps1 refresh-data

# Xem trạng thái hoặc log
.\scripts\dev.ps1 status
.\scripts\dev.ps1 logs ai-worker-service
```

Script dừng ngay khi một bước thất bại và không xóa volume PostgreSQL. Lệnh `refresh-data` được thiết kế để có thể dùng lại với scheduler sau này, nhưng project hiện chưa tự tạo lịch chạy định kỳ.

`refresh-data` chỉ hiện trạng thái ngắn gọn trên terminal; log chi tiết nằm tại `reports/refresh-data.log`. Khi job hoàn tất, script thoát nhưng các service ứng dụng vẫn tiếp tục chạy. Muốn dừng chúng, dùng `.\scripts\dev.ps1 stop`.

### Chạy Docker Compose trực tiếp

Build và chạy toàn bộ service:

```powershell
docker compose up -d --build
```

Kiểm tra trạng thái:

```powershell
docker compose ps
```

Các địa chỉ chính:

- Ứng dụng: `http://localhost`
- Backend API trực tiếp: `http://localhost:8000`
- Backend health check: `http://localhost:8000/health`
- AI worker health check: `http://localhost:8001/health`
- PostgreSQL: `localhost:5432`

Thông tin kết nối PostgreSQL trong môi trường development:

```text
Host: localhost
Port: 5432
Database: career_compass
Username: cc_user
Password: cc_pass
```

## 3. Crawl và khởi tạo dữ liệu

Trong image Docker, entrypoint đã là `python -m crawl_service`. Vì vậy chỉ truyền tên lệnh; không chạy `docker compose run ... collect-all` trên image cũ chưa build.

### Quy trình đầy đủ

```powershell
# 1. Thu thập tin tuyển dụng và dữ liệu O*NET
docker compose run --rm crawl-service collect-all

# 2. Chuẩn hóa, tạo các bảng processed và ghi vào PostgreSQL
docker compose run --rm crawl-service pipeline

# 3. Đảm bảo AI worker đang chạy trước khi dịch
docker compose up -d ai-worker-service

# 4. Dịch tên/mô tả/nhiệm vụ nghề sang tiếng Việt bằng Gemini
docker compose run --rm crawl-service enrich-onet-vi

# 5. Chạy lại pipeline để publish bản dịch vào PostgreSQL
docker compose run --rm crawl-service pipeline

# 6. Build lại giao diện nếu frontend đã được thay đổi
docker compose build frontend
docker compose up -d frontend nginx
```

Bản dịch được cache trong `data/interim/`. Nếu nội dung nguồn không thay đổi, chạy lại sẽ không gọi Gemini cho những nghề đã dịch.

### Chỉ cập nhật O*NET

```powershell
docker compose run --rm crawl-service collect-onet
docker compose run --rm crawl-service pipeline
```

O*NET hiện cung cấp cho hệ thống:

- mô tả nghề và nhiệm vụ thường làm;
- RIASEC;
- Essential Skills và Transferable Skills;
- Software Skills, gồm cờ `Hot Technology` và `In Demand`.

### Chỉ crawl từng nguồn tuyển dụng

```powershell
docker compose run --rm crawl-service collect-greenhouse
docker compose run --rm crawl-service collect-viecoi
docker compose run --rm crawl-service pipeline
```

### Publish lại dữ liệu đã xử lý

Nếu các file Parquet đã tồn tại và chỉ cần ghi lại database:

```powershell
docker compose run --rm crawl-service publish-db
```

## 4. Kiểm tra kết quả

Tìm nghề:

```text
http://localhost:8000/api/careers/search?q=data&limit=20
```

Xem chi tiết Data Analyst:

```text
http://localhost:8000/api/careers/CAREER_DATA_ANALYST
```

Response chi tiết gồm `overview_vi`, `typical_tasks`, `top_skills`, `riasec_scores`, số tin tuyển dụng và nguồn bằng chứng.

Sau khi build lại frontend, mở `http://localhost/careers` và nhấn `Ctrl + F5` nếu trình duyệt vẫn giữ bundle cũ.

## 5. Các lệnh vận hành hữu ích

```powershell
# Xem log toàn hệ thống
docker compose logs -f

# Xem log một service
docker compose logs -f crawl-service
docker compose logs -f ai-worker-service
docker compose logs -f backend-api

# Khởi động lại service
docker compose restart backend-api

# Dừng hệ thống, giữ nguyên database
docker compose down

# Xem trạng thái crawl-service
docker compose run --rm crawl-service status
```

Không dùng `docker compose down -v` nếu muốn giữ dữ liệu PostgreSQL vì `-v` xóa volume database.

## 6. Chạy test

Cài Python dependencies ở máy host rồi chạy:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e .\crawl-service
pytest -q
```

Các kiểm tra bổ sung:

```powershell
python -m compileall crawl-service/src backend-api ai-worker-service
python -m json.tool crawl-service/data/taxonomy.json
docker compose config
```

## 7. Lỗi thường gặp

### `exec: "collect-all": executable file not found in $PATH`

Image crawl-service đang dùng entrypoint cũ. Build lại rồi chạy:

```powershell
docker compose build crawl-service
docker compose run --rm crawl-service collect-all
```

### Không kết nối được PostgreSQL

Port đúng là `5432`, không phải `16`. Kiểm tra container:

```powershell
docker compose ps db
```

Sau đó dùng thông tin kết nối ở mục 2.

### AI worker không khởi động

Kiểm tra `.env` có đủ các biến bắt buộc và xem log:

```powershell
docker compose logs ai-worker-service
```

Lỗi `429` từ Gemini thường là hết quota hoặc gửi quá nhiều request. Dữ liệu dịch đã hoàn thành vẫn nằm trong cache nên không cần dịch lại từ đầu.

### Giao diện chưa thấy dữ liệu mới

```powershell
docker compose build frontend
docker compose up -d frontend nginx
```

Sau đó nhấn `Ctrl + F5`.

## Dữ liệu và độ tin cậy

- Dữ liệu tuyển dụng hiện chỉ đại diện cho các nguồn đang theo dõi, không đại diện toàn bộ thị trường lao động Việt Nam.
- Kỹ năng có `% tin tuyển dụng` được tính từ snapshot crawl thực tế.
- Kỹ năng O*NET dùng nhãn `In Demand`, `Hot Technology` hoặc điểm quan trọng; không giả lập thành tỷ lệ phần trăm thị trường Việt Nam.
- Collector không bypass CAPTCHA, Cloudflare, đăng nhập hoặc giới hạn truy cập.
- Raw/interim/processed data và cache là generated artifacts, không nên commit.

Tài liệu chi tiết: [Data Layer](docs/data-layer-phase1.md), [Data contracts](docs/data-contracts.md), [AI worker gateway](docs/ai-worker-gateway.md).
