# Student Companion Phase 1 Demo

Bản demo offline chứng minh một vòng đồng hành khép kín cho học sinh cấp 3:
từ bằng chứng học tập và sở thích, hệ thống tạo ability profile, ba loại gap,
kế hoạch tuần 45 phút, rồi cập nhật snapshot sau post-test và micro-experience.

Demo không kết luận nghề nghiệp cuối cùng. Nó đề xuất bước thử nhỏ tiếp theo dựa
trên bằng chứng mới.

## Persona và synthetic data

Nguyễn Minh Anh là học sinh lớp 11, có 45 phút mỗi tuần, đang cân nhắc Data/AI
và Kinh tế. Minh Anh yếu biến đổi lượng giác, khá xác suất và suy luận dữ liệu,
nhưng chưa có trải nghiệm Data/AI thực tế.

Input synthetic nằm trong:

```text
fixtures/student_t0/   # hồ sơ, học bạ, giáo viên, pre-test, self-report
fixtures/student_t1/   # post-test và Data activity result
```

Fixture chỉ chứa input, dùng timestamp cố định và parse qua domain contracts.
Không có ability, gap, plan, outcome hay snapshot được viết sẵn.

## Kiến trúc

```text
static UI (HTML/CSS/JS)
        ↓ local JSON API
run_demo.py (Python standard-library HTTP server)
        ↓
application/service.py (state machine và orchestration)
        ↓
domain/rules.py + domain/models.py (business rules thuần)
        ↑
infrastructure/fixtures.py + infrastructure/market.py
```

- `domain`: Pydantic contracts và business rules deterministic, không I/O.
- `application`: điều phối `initial → analyzed → planned → advanced`.
- `infrastructure`: đọc fixtures và market output read-only.
- `run_demo.py`: `ThreadingHTTPServer`, static files và JSON API.
- `scripts/preflight.py`: kiểm tra end-to-end trước khi demo.

FastAPI không được dùng trong demo đầu tiên vì runtime offline hiện không có
FastAPI/Uvicorn/HTTPX và sprint không cho phép cài dependency. HTTP boundary
hiện dùng hoàn toàn Python standard library.

## Market data

Adapter chỉ đọc bốn output hiện có:

- `data/processed/career_skill_matrix.parquet`
- `data/processed/career_demand_summary.parquet`
- `data/processed/jobs_clean.parquet`
- `data/processed/job_skills.parquet`

Hai career group demo được map bằng `career_id` versioned, không join bằng tên
hiển thị. Foundation skill chỉ giới hạn ở kỹ năng phù hợp học sinh cấp 3.

Khi pipeline output hợp lệ, response đánh dấu `pipeline_export`. Nếu file hoặc
mapping không đủ, adapter dùng `fixtures/market_fallback.json` và đánh dấu
`fallback_demo`; demo không cần internet và không chạy crawler.

## Chạy test

Từ repository root:

```powershell
python -m pytest phase1_demo/tests -q
```

Nếu `python` chưa nằm trong PATH, dùng interpreter phù hợp của workspace.

## Chạy preflight

```powershell
python -m phase1_demo.scripts.preflight
```

## Engine V1 hardening

Public contract remains frozen at `1.0.0`. Run the 18 deterministic engine
scenarios without starting the server or UI:

```powershell
python -m phase1_demo.scripts.run_engine_scenarios
```

The versioned activity catalog is defined in
`student_companion/config.py`; rule details and scenario coverage are documented
in `ENGINE_RULES.md` and `SCENARIO_MATRIX.md`. The catalog covers Data/AI,
Economics/Business, Marketing/Communication, Design/UX, Engineering, Law/Social
Sciences, and Health/Life Sciences.

Production profile adapters, frontend integration, APIs, databases, auth, and
deployment remain outside this demo hardening sprint.

Kết quả thành công kết thúc bằng `PRE-FLIGHT PASSED`.

## Chạy demo

```powershell
python -m phase1_demo.run_demo
```

Hoặc chọn host/port:

```powershell
python -m phase1_demo.run_demo --host 127.0.0.1 --port 8000
```

Mở [http://127.0.0.1:8000](http://127.0.0.1:8000). Server không tự mở browser.

## API routes

| Method | Route | Chức năng |
|---|---|---|
| `GET` | `/health` | Trạng thái server, pipeline version, market mode |
| `POST` | `/api/demo/reset` | Trở về `initial` |
| `GET` | `/api/demo/state` | State hiện tại, chỉ chứa dữ liệu JSON-serializable |
| `POST` | `/api/demo/analyze` | Chuẩn hóa T0, tạo ability và gaps |
| `POST` | `/api/demo/plan` | Tạo weekly plan |
| `POST` | `/api/demo/advance` | Nạp T1, outcome, snapshot và next step |
| `GET` | `/api/demo/comparison` | Before/after sau khi advance |

Transition sai trả HTTP `409`; API route không tồn tại trả JSON `404`.

## Luồng demo

1. Xem hồ sơ Minh Anh.
2. Chọn **Phân tích hồ sơ** để xem điểm mạnh và ba loại gap.
3. Chọn **Tạo kế hoạch tuần** để nhận plan 20 + 25 = 45 phút.
4. Chọn **Mô phỏng sau 2 tuần** để nạp post-test 7/10 và Data activity 8/10.
5. Xem gap Data/AI đóng, decision gap vẫn còn và next step chuyển sang Kinh tế.
6. Chọn **Đặt lại demo** để chạy lại từ đầu.

## Determinism và riêng tư

- Không gọi external API, không cần API key, không dùng LLM.
- Evidence ID dùng SHA-256 ổn định.
- Timestamp và snapshot ID do fixture/use case cung cấp.
- Cùng input và market snapshot tạo cùng output.
- Local server chỉ bind `127.0.0.1` theo mặc định và giữ state trong memory.

## Hạn chế

- Persona và post-activity result là synthetic, không đại diện đánh giá tâm lý
  hay tư vấn nghề nghiệp chính thức.
- Market snapshot hiện tại nhỏ và không đại diện toàn bộ thị trường Việt Nam.
- State chỉ tồn tại trong process; restart server sẽ reset demo.
- Local server phục vụ demo đơn người dùng, chưa có authentication, persistence,
  rate limit hoặc production hardening.
- UI dùng label tiếng Việt có cấu hình cục bộ; chưa có hệ thống i18n.

## Hướng migration sang FastAPI

Khi runtime có FastAPI, giữ nguyên `DemoService` và domain rules; chỉ thay HTTP
adapter trong `run_demo.py` bằng route FastAPI, thêm schema response và dùng
TestClient. Không cần viết lại pipeline hoặc duplicate business logic.
