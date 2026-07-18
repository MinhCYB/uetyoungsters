# Database — quy ước dùng chung (bổ sung cho `career-compass-notes.md` mục 8)

> File này chốt lại cách 3 service cùng dùng 1 Postgres instance mà không dẫm chân nhau. Đọc trước khi viết `models.py`/`database.py` cho service của mình.

## 1. Vẫn dùng 1 Postgres instance duy nhất, không dùng Redis

Đã cân nhắc Redis cho session/profile (vì có TTL tự nhiên), nhưng **quyết định giữ Postgres** vì:
- Tech stack đã chốt ở `career-compass-notes.md` mục 5 chỉ có Postgres
- Đỡ thêm 1 dependency/1 điểm fail khi deploy demo trên CasaOS/laptop local
- TTL tự làm bằng cột `expires_at` + cleanup job định kỳ (đã có sẵn trong cấu trúc dự án dự kiến: `core/session/cleanup.py`)

## 2. Ai sở hữu bảng nào (bắt buộc tuân theo)

```
Postgres instance DUY NHẤT
│
├── crawl-service SỞ HỮU (Người 1 toàn quyền tạo/sửa)
│   job_postings, job_extracted_signals, demand_summaries
│
├── profile-service SỞ HỮU (Người 2 toàn quyền tạo/sửa)
│   student_profiles
│
└── core SỞ HỮU (Đội trưởng toàn quyền tạo/sửa)
    anonymous_sessions, recommendations, recommendation_feedback,
    question_bank_versions, questions, question_options, question_conditions,
    question_scales, question_blueprints, blueprint_rules,
    assessments, assessment_answers
```

**Nguyên tắc vàng:** chỉ chủ sở hữu bảng mới được tạo/sửa bảng đó. Service khác nếu cần đọc thì chỉ định nghĩa model đọc (map cột), **không** được `create_all()`/migrate cho bảng mình không sở hữu.

Riêng `core` cần đọc bảng của `crawl-service` để chạy matching — xem mục 4.

## 3. Migration: dùng `create_all()`, KHÔNG dùng Alembic

Quyết định vì đây là hackathon, schema còn đổi nhiều, và không có data quý cần giữ qua các lần đổi schema (nếu cần đổi schema lớn, chấp nhận `docker compose down -v` làm lại từ đầu).

Lý do không dùng Alembic (nếu sau này cần nâng cấp thì đọc lại):
- 3 service cùng 1 Postgres → cả 3 dùng Alembic mặc định sẽ tranh nhau bảng `alembic_version` chung, phải tự tách `version_table` riêng cho từng service
- Autogenerate diff toàn bộ DB (gồm cả bảng service khác) dễ hiểu nhầm "cần DROP" bảng không thuộc về mình
- Thêm setup (`alembic.ini`, `migrations/env.py`) lặp lại 3 lần, không đáng cho tốc độ hackathon

Mỗi service tự gọi `Base.metadata.create_all(engine)` cho bảng mình sở hữu, KHÔNG ALTER bảng đã tồn tại có data — chỉ tạo bảng mới nếu chưa có.

## 4. Cách `core` đọc bảng của `crawl-service` mà không tạo bảng đó

`core/data/models.py` định nghĩa các model **read-only** map đúng tên bảng/cột của `crawl-service` (`JobPostingReadModel`, `JobExtractedSignalReadModel`, `DemandSummaryReadModel`), dùng chung `Base` với `core/session` và `core/ai`.

Để tránh `create_all()` vô tình đụng vào bảng không sở hữu, `core/database.py::init_db()` liệt kê **tường minh** danh sách bảng cần tạo:

```python
Base.metadata.create_all(
    bind=engine,
    tables=[
        AnonymousSession.__table__, Recommendation.__table__, RecommendationFeedback.__table__,
        QuestionBankVersion.__table__, Question.__table__, QuestionOption.__table__,
        QuestionCondition.__table__, QuestionScale.__table__,
        QuestionBlueprint.__table__, BlueprintRule.__table__,
        Assessment.__table__, AssessmentAnswer.__table__,
    ],
)
```

Không gọi `Base.metadata.create_all(engine)` trần (không có `tables=`) trong `core`, vì `Base` đó cũng chứa bảng của `crawl-service`.

**Nếu Người 1 đổi schema `job_postings`** → phải báo lại để cập nhật `core/data/models.py` tương ứng (giống nguyên tắc với `core/shared/schemas.py`).

## 5. Thứ tự chạy lần đầu — điểm dễ vấp nhất

`docker-compose.yml` hiện tại: `core` chỉ `depends_on: db, profile-service`, **không** `depends_on: crawl-service` — vì `crawl-service` là batch job (cron/tay), không phải service runtime luôn chạy.

Hệ quả: nếu `core` khởi động và có request đọc `job_postings`/`demand_summaries` **trước khi** `crawl-service` từng chạy lần nào, bảng đó chưa tồn tại trong DB → lỗi `relation "job_postings" does not exist`.

**Cách xử lý:**
1. **Quy ước vận hành:** chạy `crawl-service` thủ công ít nhất 1 lần trước khi test/demo `core`:
   ```bash
   docker compose run crawl-service python main.py
   ```
   Lệnh này vừa tạo bảng (`init_db()`) vừa chạy job crawl thật.
2. **Code phòng thủ ở `core`:** khi query bảng crawl-service, bọc try/except — nếu bảng chưa tồn tại (crawl-service chưa chạy lần nào) thì trả về danh sách rỗng thay vì crash toàn bộ app. Đúng tinh thần DoD ở mục 11: *"core nên xử lý gracefully nếu 1 service tạm không phản hồi"* — áp dụng tương tự cho trường hợp thiếu data từ crawl-service.

## 6. Việc còn treo, chưa chốt hẳn

- **`profile-service` có thực sự cần Postgres không**, hay dùng lưu trữ khác vì `student_profiles` chỉ sống trong phạm vi session (ephemeral, có TTL)? Hiện đang tạm quyết định: vẫn dùng chung Postgres, bảng riêng — nhưng đây không phải quyết định cuối cùng, `career-compass-notes.md` mục 7 cũng ghi rõ đây là điểm "cần chốt".
- **Thang đo `SkillProfile.level`** (0-1 hay 0-100) — ảnh hưởng cả cách `core` tính `SkillGapItem.current_level`/`required_level`, cần thống nhất với Người 2 trước khi 2 bên code phần này.
