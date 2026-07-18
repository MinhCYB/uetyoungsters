# Career Compass — Kế hoạch chốt (kiến trúc 3-service)

> File này là bản chốt cuối, dùng làm context nền cho việc phát triển tiếp theo (kể cả cho AI/LLM khác đọc). Mọi quyết định ở mục 6 là bắt buộc, không thay đổi khi code trừ khi cả team đồng ý sửa lại file này trước.

## 1. Đề bài (tóm tắt)

**Context:** Học sinh Việt Nam chọn nghề theo cảm tính/trend/gia đình, dẫn đến thất nghiệp sau tốt nghiệp và lệch cung-cầu lao động.

**Yêu cầu:**
1. Phân tích nhu cầu kỹ năng thật từ hiring data (job posting, skill, lương, vùng, xu hướng)
2. Xây profile học sinh đa chiều — không giản lược thành 1 bài trắc nghiệm tính cách
3. Gợi ý nghề và lộ trình học tập/nghề nghiệp cá nhân hoá, giải thích được — bao gồm cả hướng nghề (vocational), không chỉ đại học
4. Ràng buộc đạo đức bắt buộc: mở rộng lựa chọn, không củng cố bias giới/vùng, luôn trình bày là tài liệu tham khảo, tôn trọng quyền tự quyết

**Tiêu chí chấm điểm:** chất lượng skill-signal extraction, mức độ cá nhân hoá + explainability, thiết kế chống bias/mở rộng cơ hội (trọng số cao), tính hữu dụng thực tế.

---

## 2. Nguyên tắc cốt lõi

Điểm mạnh của sản phẩm phải nằm ở khả năng:
- Trích xuất skill-signal có kiểm chứng, không phải LLM tự bịa
- Matching tái lập được (deterministic) — cùng input phải ra cùng output
- Lý do trace được về dữ liệu thật, có version/nguồn
- Roadmap xuất phát từ skill gap thật, không phải LLM tự sáng tác
- Không đóng khung người dùng — luôn có lựa chọn thay thế
- Cho phép chỉnh sửa và chạy lại

**Ranh giới bắt buộc:** Dữ liệu thật → Logic deterministic → LLM chỉ hỗ trợ diễn đạt/giải thích. Không được biến pipeline thành "đưa mọi thứ cho LLM, nhận về score/nghề/roadmap/lý do" — đó là rủi ro lớn nhất về fairness và khả năng giải thích.

**Kiến trúc:** 3 service độc lập — `crawl-service`, `profile-service`, `core` — không phải 1 modular monolith. Lý do tách ở mục 6.13.

---

## 3. Kiến trúc 3-service (bản chốt)

```
crawl-service     → ghi thẳng Postgres (không qua API, không real-time, chạy độc lập theo lịch)
profile-service   → expose API riêng, frontend gọi THẲNG lúc làm form (cần phản hồi tức thời)
core              → nhận structured profile (từ profile-service, qua API lúc runtime) +
                     demand data (từ DB, do crawl-service ghi) → matching, skill-gap,
                     bias-check, roadmap, explainable output
frontend          → gọi thẳng profile-service lúc làm form; gọi core lúc cần recommendation
```

**Nguyên tắc phân vai:**
- `crawl-service` nặng, không cần real-time, chạy độc lập về thời gian → tách vì lý do workload
- `profile-service` có logic riêng phức tạp (adaptive questioning: chọn câu hỏi tiếp theo dựa trên câu trả lời trước, tổng hợp thế mạnh từ kho câu hỏi lớn) → tách vì có domain logic + nguồn dữ liệu (question bank) riêng, cần thay đổi độc lập
- `core` không phải gateway đứng giữa mọi request — chỉ là bộ xử lý nhận đầu vào đã sẵn sàng để chạy AI layer, không tự hỏi, không tự crawl

### Session layer (trong `core`, thay thế hoàn toàn cho auth/user account)
- Người dùng vào web → `core` tạo **anonymous session** (secure cookie, chỉ lưu hash token)
- Không đăng ký, không đăng nhập, không email/password, không social login, không đồng bộ nhiều thiết bị, không lịch sử lâu dài theo tài khoản
- Session có TTL (24h hoặc 7 ngày), có endpoint xoá chủ động, có cleanup job cho session hết hạn

### `crawl-service` (Người 1)
1. Crawl job posting thật (ITviec/TopCV/Vieclam24h)
2. Data cleaning & deduplication (theo `content_hash`)
3. Extraction pipeline — **hybrid, không chỉ LLM** (xem mục 6.2)
4. Demand summary theo nghề/vùng/kỳ, có snapshot version — ghi thẳng vào Postgres dùng chung
5. *Phase 2 (chưa làm ngay):* Labor supply reports / dữ liệu cung lao động

### `profile-service` (Người 2)
1. **Adaptive questioning engine**: câu hỏi cố định ban đầu → tổng hợp thế mạnh sơ bộ → chọn tiếp câu hỏi sâu hơn từ kho đề lớn hơn (không phải form tĩnh 1 lần, cũng không phải chatbot tự do — xem mục 6.1 đã cập nhật)
2. Question bank quản lý riêng, mở rộng độc lập với `core`
3. Strength synthesizer — tổng hợp thế mạnh, sở thích, mục tiêu, địa điểm mong muốn thành `structured_profile`
4. User review/edit trước khi gửi sang `core`
5. Expose API để `core`/frontend gọi lúc runtime

### `core` (Đội trưởng)
1. Session management (xem trên)
2. Matching engine — **rule-based weighted scoring**, không để LLM tự chấm điểm (xem mục 6.3)
3. Skill-gap analysis
4. Bias-check — **2 tầng**: deterministic policy trước, LLM language review sau (xem mục 6.4)
5. Pathway suggestion / roadmap — giới hạn **0-12 tháng** + alternative pathways (xem mục 6.5)
6. Explainable recommendation output — **chỉ format/tổng hợp**, không gọi LLM suy luận lại từ đầu (xem mục 6.6)

### Application layer (frontend)
- **Student dashboard là luồng chính** (form + kết quả + roadmap), không yêu cầu tài khoản
- **Counselor dashboard là optional/demo-only** — nếu giữ, dùng cơ chế "chia sẻ chủ động": học sinh bấm chia sẻ → hệ thống tạo share code tạm thời có hạn → cố vấn nhập mã để xem trong thời gian giới hạn. Không mặc định truy cập toàn bộ anonymous profiles.
- Có tải/in kết quả (PDF hoặc save-as-PDF từ trình duyệt) vì người dùng không có tài khoản để quay lại
- Có thông báo quyền riêng tư rõ ràng: dữ liệu chỉ dùng trong phiên hiện tại, kết quả mang tính tham khảo, có thể xoá dữ liệu phiên bất cứ lúc nào
- Feedback loop: chỉnh sửa profile (qua `profile-service`) → gửi structured profile mới sang `core` → rerun recommendation — tách biệt rõ với feedback endpoint trong `core` (ẩn nghề, đánh giá hữu ích, ghi chú), feedback không được âm thầm sửa profile

---

## 4. Phân công nhân sự

| Người | Service phụ trách | Phần UI liên quan |
|---|---|---|
| Người 1 | `crawl-service`: crawl, cleaning, extraction, demand warehouse | Market insight/chart |
| Người 2 | `profile-service`: adaptive questioning, question bank, strength synthesizer | Form/câu hỏi động |
| Đội trưởng (bro) | `core`: session, matching, skill gap, bias, pathway, explanation | Recommendation + roadmap page |
| Cả đội | Integration, counselor dashboard tối giản, demo | Ghép chung |

**Nguyên tắc phối hợp:** khoá taxonomy → Pydantic schema (dùng chung qua package/file share, vì giờ là 3 service riêng, không import trực tiếp được nữa) → API contract giữa 3 service → sample fixtures TRƯỚC khi code. Cả 3 người dùng chung 1 bộ fixture JSON để code song song, không chờ crawl-service/profile-service thật xong mới làm `core` hoặc frontend.

---

## 5. Tech stack (bản chốt)

| Hạng mục | Lựa chọn | Ghi chú |
|---|---|---|
| Backend (cả 3 service) | Python + FastAPI | Mỗi service 1 app riêng, deploy riêng |
| Database | PostgreSQL (Docker), 1 instance dùng chung | `crawl-service` ghi thẳng, `core` đọc; `profile-service` không cần đọc DB này lúc runtime |
| ORM/Schema | SQLAlchemy (từng service tự có models) + Pydantic (schema dùng chung, đóng gói thành package hoặc copy file) | Vì 3 service không chung 1 codebase, cần thống nhất qua package/API contract, không import trực tiếp |
| Extraction (crawl-service) | Hybrid: rule-based + taxonomy matching + LLM fallback | Không dùng LLM cho toàn bộ trường dữ liệu |
| Crawler | BeautifulSoup (trang tĩnh) / Playwright (trang JS) | Bắt buộc data thật, không mockup |
| Adaptive questioning (profile-service) | Rule-based branching hoặc LLM hỗ trợ chọn câu hỏi kế tiếp | Cần quyết định thêm — xem mục "Cần chốt tiếp" |
| Matching score (core) | Rule-based weighted scoring + embedding hỗ trợ mapping | LLM chỉ diễn giải, không tự chấm điểm |
| Bias-check (core) | Deterministic policy enforcement + LLM language review | 2 tầng, rule trước LLM sau |
| LLM chính | Gemini API | Fallback extraction, diễn giải lý do, trình bày roadmap |
| LLM phụ (tốc độ cao) | Groq | LLM language review ở tầng 2 của bias-check |
| Frontend | React (Vite) | Gọi thẳng `profile-service` lúc làm form, gọi `core` lúc cần recommendation |
| Deploy demo | Home server qua CasaOS (chính) + laptop local (backup) | Docker compose chạy 4 service: db, crawl-service, profile-service, core |
| Session management | Anonymous secure-cookie session (hash token, TTL, cleanup job), nằm trong `core` | Không có user account, không auth |
| Version control | GitHub — cân nhắc: 1 repo nhiều folder (dễ quản lý chung) hay 3 repo riêng (đúng tinh thần tách service hơn) | Xem mục "Cần chốt tiếp" |

---

## 6. Các quyết định đã khoá (bắt buộc, không đổi khi code)

### 6.1 Profiling dùng adaptive questioning trong `profile-service`, không dùng chatbot tự do
Câu hỏi cố định ban đầu → tổng hợp thế mạnh sơ bộ → hệ thống chọn tiếp câu hỏi sâu hơn từ kho đề lớn hơn (question bank) → lặp lại tới khi đủ tín hiệu → user review/edit → gửi `structured_profile` sang `core`. Không xây dựng conversation agent/chatbot tự do hoàn toàn. Không lưu `conversation_log` dạng hội thoại tự do; thay vào đó lưu `raw_answers` (từng câu hỏi + trả lời, có thể có nhiều vòng), `structured_profile`, `profile_version`, `confirmed_by_user`.

### 6.2 Extraction (trong `crawl-service`) là hybrid, không thuần LLM
```
Raw JD → Rule-based extraction → Taxonomy matching → LLM fallback cho trường mơ hồ
→ Pydantic validation → Confidence score → Lưu provenance/version → ghi Postgres
```
Phân công theo trường: ngày đăng (parser/rule), lương (regex + normalization), địa điểm (alias mapping + taxonomy), seniority (rule + LLM fallback), job title (rule/embedding + LLM fallback), skills (dictionary + fuzzy matching + LLM fallback). LLM không được tự tạo skill không có trong JD gốc. Cache theo `content_hash` để không gọi LLM lại cho JD trùng.

### 6.3 Matching score (trong `core`) là deterministic
```
Match score = 30% interest match + 30% skill match + 20% market demand
            + 10% work preference match + 10% location compatibility
```
Rule-based weighted scoring + embedding similarity hỗ trợ mapping; LLM chỉ diễn giải kết quả, không tự chấm điểm. Phải có version, có breakdown, cùng input cho cùng output. Không dùng giới tính, không dùng quê quán để loại nghề. Hiển thị dạng "Điểm phù hợp: 76/100", không dùng "Xác suất phù hợp: 76%" (không phải xác suất khoa học).

### 6.4 Bias-check (trong `core`) 2 tầng
- **Tầng 1 (deterministic policy):** gender không tham gia scoring; quê quán không dùng để loại nghề; preferred location chỉ bổ sung thông tin cơ hội; luôn trả tối thiểu 3 lựa chọn (nghề gần, nghề lân cận, nghề mở rộng); không dùng câu tuyệt đối ("không thể", "không phù hợp hoàn toàn"); luôn kèm disclaimer tham khảo; cho phép chỉnh profile/chạy lại; cho phép ẩn nghề không muốn xem.
- **Tầng 2 (LLM language review):** kiểm tra ngôn ngữ định kiến, giới hạn lựa chọn, phán xét, khẳng định quá mức, nội dung trái với dữ liệu đầu vào.
- Pipeline: Deterministic policy enforcement → LLM language review → Final output.

### 6.5 Roadmap (trong `core`) giới hạn 0-12 tháng, không cam kết 3-5 năm
- **Immediate action (0-3 tháng):** kỹ năng cần bổ sung ngay, mục tiêu đầu ra rõ ràng, lý do ưu tiên
- **Preparation path (3-12 tháng):** project, portfolio, chứng chỉ, kỹ năng thực hành
- **Alternative pathways:** đại học / học nghề-chứng chỉ / tự học + portfolio

Roadmap phải sinh từ dữ liệu có cấu trúc: `skill gap + skill importance + prerequisite graph + thời gian học mỗi tuần + pathway preference`. LLM chỉ dùng để trình bày thành timeline/card, không tự sáng tác milestone. Không sinh link khoá học hay lịch học từng ngày trong MVP.

Mỗi milestone tối thiểu cần: `title`, `duration`, `goal`, `reason`, `evidence` (source_snapshot, frequency) — để trace được về data thật.

### 6.6 Explainable output (trong `core`) chỉ tổng hợp, không suy luận lại
Bước cuối chỉ được: format top nghề, gộp breakdown điểm, gộp lý do đã tạo, gộp skill gap, gộp roadmap, gắn nguồn/snapshot, gắn disclaimer. Không được: tự đổi nghề, tự đổi score, tự thêm skill, tự thêm market claim, tự tạo roadmap mới khác với bước trước.

### 6.7 Không tuyên bố "trend" nếu chưa có dữ liệu lịch sử
Một lần crawl chỉ cho biết nhu cầu hiện tại, không đủ chứng minh tăng/giảm. Cần dataset lịch sử có `posted_at`, hoặc snapshot crawl định kỳ nhiều tuần/tháng. Nếu chưa đủ dữ liệu lịch sử, UI chỉ dùng cụm "nhu cầu hiện tại", "số lượng tin tuyển", "kỹ năng phổ biến", "phân bố theo khu vực" — không dùng "đang tăng"/"đang giảm"/"xu hướng 6 tháng" trừ khi có đủ dữ liệu chứng minh.

### 6.8 Database phải có version/provenance
Bắt buộc lưu `extraction_model`, `extraction_version`, `confidence`, `snapshot_version`, `profile_version` để giải thích được vì sao cùng một người có thể nhận kết quả khác nhau ở hai thời điểm.

### 6.9 Skill/career phải map về taxonomy khi matching
Input tự do được phép ở `profile-service`, nhưng `core` chỉ dùng canonical taxonomy khi matching.

### 6.10 Cả team dùng chung fixture + schema contract trước khi code thật
Không chờ `crawl-service`/`profile-service` thật xong mới làm `core` hoặc frontend — dùng mock fixture đúng theo API contract để code song song từ đầu.

### 6.11 MVP là trải nghiệm one-time, anonymous — không có tài khoản
Không xây đăng ký/đăng nhập/email-password/social login/user profile lâu dài/đồng bộ nhiều thiết bị. Thay vào đó: anonymous session qua secure cookie (HttpOnly, Secure khi deploy HTTPS, SameSite=Lax/Strict), `core` chỉ lưu **hash** của token, không lưu plaintext. Session tự hết hạn theo TTL, có endpoint xoá chủ động. Khi session hết hạn, profile/recommendation liên quan bị xoá hoặc đánh dấu chờ dọn. LocalStorage chỉ dùng cho trạng thái UI tạm thời — không dùng làm nơi lưu duy nhất cho profile/recommendation. Không thu thập PII không cần thiết.

### 6.12 Crawl xử lý bằng service độc lập, ghi thẳng DB, không phải route runtime
`crawl-service` không expose API để frontend/`core` gọi trực tiếp lúc runtime — nó chạy độc lập theo lịch (cron) hoặc chạy tay, ghi kết quả thẳng vào Postgres dùng chung. `core` chỉ đọc dữ liệu đã có sẵn trong DB, không kích hoạt crawl.

### 6.13 Kiến trúc tách 3 service, không phải modular monolith
Lý do tách khác nhau cho từng service:
- `crawl-service`: workload nặng (crawl số lượng lớn, cần retry/rate-limit riêng), không cần real-time, có thể cần scale worker độc lập trong tương lai
- `profile-service`: có domain logic riêng đủ phức tạp (adaptive questioning: chọn câu hỏi kế tiếp dựa trên câu trả lời trước, tổng hợp thế mạnh), có nguồn dữ liệu riêng cần quản lý/mở rộng độc lập (question bank), có thể cần tinh chỉnh nhiều lần không đụng tới `core`
- `core`: chỉ giữ vai trò xử lý — nhận input đã sẵn sàng, chạy AI layer, không đứng làm gateway cho mọi request

Trade-off chấp nhận: thêm độ phức tạp deploy (3 service thay vì 1), thêm network hop giữa `profile-service` và `core` lúc gửi kết quả cuối, nhưng đổi lại ranh giới trách nhiệm rõ ràng hơn, đúng với bản chất khối lượng công việc khác biệt của từng phần.

---

## 7. API contract (khoá trước khi code)

### `profile-service` (frontend gọi thẳng)
```
POST   /session                     # tạo/lấy session cho profile-service (hoặc dùng chung session từ core — cần chốt)
POST   /questions/next              # gửi câu trả lời hiện tại, nhận câu hỏi tiếp theo hoặc báo đã đủ
GET    /profile/current             # xem structured_profile hiện tại
PATCH  /profile/current             # sửa, tạo profile_version mới
POST   /profile/current/submit      # xác nhận hoàn tất, sẵn sàng gửi sang core
```

### `core` (frontend gọi lúc cần recommendation)
```
GET    /session
DELETE /session

POST   /recommendations             # nhận structured_profile (kèm theo hoặc core tự fetch từ profile-service)
GET    /recommendations/current
POST   /recommendations/current/feedback
```

### `crawl-service` (không expose API runtime — chỉ chạy job)
```
(không có endpoint public — chạy qua cron/tay, ghi thẳng Postgres)
```

**Nguyên tắc:**
- Client không tự truyền `session_id` — lấy từ cookie
- Không cho đọc profile/recommendation của session khác
- `PATCH /profile/current` (ở `profile-service`) tạo `profile_version` mới; sau đó frontend gọi `POST /recommendations` (ở `core`) để rerun
- `POST /recommendations/current/feedback` (ở `core`) chỉ dùng cho ẩn nghề / đánh giá hữu ích / ghi chú — không âm thầm sửa profile

**Luồng end-to-end:**
```
Truy cập → tạo anonymous session → adaptive questioning (profile-service, nhiều vòng)
→ user xác nhận structured_profile → POST /recommendations (core, đọc demand data có sẵn từ DB)
→ CareerRecommendation → Dashboard → Feedback (core) hoặc sửa profile (profile-service) → rerun
→ Tải/in kết quả hoặc kết thúc session
```

**Cần chốt tiếp (chưa quyết định):** session dùng chung giữa `profile-service` và `core`, hay mỗi service tự quản session riêng rồi đồng bộ qua 1 `session_id` chung do `core` phát hành? Ảnh hưởng tới cách 2 service này xác thực lẫn nhau.

---

## 8. Database schema (tách theo service ghi/đọc)

`crawl-service` **ghi**, `core` **đọc**:
- `job_postings` (raw)
- `job_extracted_signals`
- `demand_summaries`

`core` **ghi và đọc** (sở hữu):
- `anonymous_sessions`
- `recommendations`
- `recommendation_feedback`
- (tuỳ chọn) `shared_reports` nếu giữ counselor dashboard

`profile-service` **sở hữu riêng** (có thể dùng DB/schema riêng, hoặc cùng Postgres nhưng khác schema namespace — cần chốt):
- `student_profiles` (raw_answers, structured_profile, profile_version, confirmed_by_user)
- `question_bank` (câu hỏi, nhóm năng lực, điều kiện chọn câu tiếp theo)

Xem chi tiết field từng bảng trong `career-compass-schema-draft.md`.

---

## 9. Cấu trúc dự án (bản chốt — 3 service)

```
career-compass/
├── docker-compose.yml                   # 4 service: db, crawl-service, profile-service, core
├── .env.example
├── README.md
├── docs/
│   ├── career-compass-notes.md          # file này
│   └── career-compass-schema-draft.md
│
├── crawl-service/                       # Người 1
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── scrapers/
│   │   ├── itviec.py
│   │   ├── topcv.py
│   │   └── vieclam24h.py
│   ├── extraction.py                    # hybrid rule + LLM fallback
│   ├── aggregation.py                   # demand summary
│   ├── db_writer.py                     # ghi thẳng Postgres dùng chung
│   └── main.py                          # entrypoint chạy job (cron/tay), không expose API
│
├── profile-service/                     # Người 2
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                          # FastAPI app riêng
│   ├── router.py
│   ├── question_bank/
│   │   └── questions.json
│   ├── adaptive_engine.py               # chọn câu hỏi tiếp theo dựa trên câu trả lời trước
│   ├── strength_synthesizer.py          # tổng hợp thế mạnh
│   └── models.py
│
├── core/                                # Đội trưởng
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                          # ghép router: /session, /recommendations
│   ├── database.py
│   ├── session/
│   │   ├── router.py
│   │   ├── service.py
│   │   ├── cleanup.py
│   │   └── models.py
│   ├── shared/
│   │   ├── schemas.py                   # Pydantic contract — cần đồng bộ thủ công với 2 service kia
│   │   ├── taxonomy.json
│   │   ├── constants.py
│   │   └── llm_client.py
│   ├── data/                            # chỉ ĐỌC demand_summary do crawl-service ghi
│   │   ├── router.py
│   │   └── models.py
│   └── ai/
│       ├── router.py
│       ├── matching.py
│       ├── skill_gap.py
│       ├── bias_policy.py
│       ├── pathway.py
│       ├── explanation.py
│       └── models.py
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── api/                         # 2 client riêng: profileServiceApi, coreApi
│       ├── components/
│       │   ├── RoadmapCard.jsx
│       │   └── SkillGapBar.jsx
│       ├── pages/
│       │   ├── ProfileForm.jsx          # gọi profile-service
│       │   ├── StudentDashboard.jsx     # gọi core
│       │   └── SharedReport.jsx
│       └── App.jsx
│
└── tests/
    ├── fixtures/
    ├── test_extraction.py
    ├── test_matching.py
    ├── test_bias_policy.py
    └── test_end_to_end.py
```

**Không cần** `LoginPage.jsx`, `RegisterPage.jsx`, `AuthProvider.jsx` trong MVP.

**Quản lý Git:** cân nhắc giữa 1 repo nhiều folder (dễ quản lý, dễ xem tổng thể — phù hợp hackathon) và 3 repo riêng (đúng tinh thần service độc lập hơn, nhưng thêm chi phí quản lý). Đề xuất: 1 repo cho hackathon, mỗi service 1 branch riêng (`feature/crawl-service`, `feature/profile-service`, `feature/core`), merge thường xuyên. File rủi ro conflict cao nhất: `core/shared/schemas.py` — vì giờ không còn import trực tiếp được giữa các service, nên các thay đổi ở đây cần thông báo cho người viết client gọi API tương ứng.

---

## 10. Thứ tự triển khai

1. **Khoá hợp đồng chung:** Taxonomy → Pydantic schemas (dùng làm tài liệu tham chiếu, copy sang từng service) → API contract giữa 3 service → Sample fixtures
2. **Dùng mock fixture đúng API contract:** cả 3 người code song song, không chờ service khác xong
3. **Làm service độc lập:** `crawl-service`, `profile-service`, `core` — mỗi người phát triển và test service của mình với fixture giả cho phần phụ thuộc
4. **Ghép service thật:** `crawl-service` chạy job → ghi DB → `core` đọc được demand thật; `profile-service` chạy thật → `core` nhận structured_profile thật qua API
5. **Test và harden:** test extraction, test deterministic matching, test bias policy, test feedback loop, test khi 1 service down (core nên xử lý gracefully nếu profile-service tạm không phản hồi), test demo fallback

---

## 11. Definition of Done theo service

**`crawl-service`:** import/crawl được dữ liệu thật; có báo cáo duplicate; extraction trả JSON hợp lệ; có sample kiểm tra thủ công; có demand summary theo nghề/vùng; có provenance và snapshot version; không gọi LLM lại cho JD trùng; ghi thành công vào Postgres dùng chung.

**`profile-service`:** adaptive questioning hoạt động ít nhất 2 vòng (câu hỏi cố định → câu hỏi sâu hơn); tạo ra `structured_profile` hợp lệ theo schema; có location preference; người dùng xem/chỉnh được profile; không có thuộc tính nhạy cảm; có profile version; có user confirmation; expose API ổn định cho `core`/frontend gọi.

**`core`:** cùng input cho cùng kết quả; có score breakdown; có skill gap; có tối thiểu 3 lựa chọn; có option mở rộng; roadmap trace được về skill gap và demand; bias policy test pass; explainable output không tự sửa score/dữ liệu nguồn; session layer hoạt động đầy đủ (tạo, hết hạn, xoá, cleanup).

**Application layer (frontend):** chạy xuyên suốt qua 2 service không lỗi; có loading/error states cho từng service riêng (đặc biệt khi 1 service chậm/lỗi); hiển thị nguồn và thời điểm dữ liệu; có chỉnh profile và rerun; có disclaimer; có lộ trình thay thế; có tải/in kết quả; có thông báo quyền riêng tư; không có trang đăng nhập/đăng ký; counselor dashboard không truy cập mặc định vào toàn bộ anonymous profiles.

---

## 12. Quyền riêng tư (bắt buộc, gắn với mô hình anonymous session)

**Không thu thập:** tên thật, email, SĐT, địa chỉ chi tiết, giới tính (nếu không phục vụ scoring — và gender vốn đã bị cấm dùng trong scoring ở mục 6.3/6.4), trường học cụ thể (nếu không phục vụ matching), hay bất kỳ thông tin định danh cá nhân nào khác.

**Chỉ thu thập tối thiểu phục vụ recommendation:** sở thích, kỹ năng, mục tiêu, cách làm việc mong muốn, tỉnh/thành mong muốn làm việc, khả năng remote/relocate, thời gian học mỗi tuần, hướng học mong muốn.

**UI bắt buộc hiển thị thông báo:** "Thông tin chỉ được dùng để tạo gợi ý trong phiên hiện tại. Kết quả mang tính tham khảo. Bạn có thể xoá dữ liệu phiên bất cứ lúc nào."

---

## 13. Các quyết định phụ khác đã thống nhất

- **Định vị bài toán:** "NLP-powered career recommendation system" — NLP là thành phần lõi (extraction, adaptive questioning, giải thích) nhưng hệ thống còn cần data engineering, deterministic scoring/ranking — không phải bài toán thuần NLP.
- **Deploy demo:** ưu tiên home server qua CasaOS, laptop local làm phương án dự phòng nếu mạng/điện nhà gặp sự cố lúc trình bày.
