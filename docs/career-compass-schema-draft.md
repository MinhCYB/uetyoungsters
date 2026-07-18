# Career Compass — Schema chốt (kiến trúc 3-service)

> Bản này thay bản trước — cập nhật theo kiến trúc 3 service độc lập (`crawl-service`, `profile-service`, `core`). Mỗi bảng ghi rõ service nào sở hữu (ghi) và service nào chỉ đọc.

## Sở hữu bởi `crawl-service` (ghi), `core` (chỉ đọc)

### `job_postings` — dữ liệu gốc

```python
class JobPosting(BaseModel):
    id: str
    source: str                    # "itviec" | "topcv" | "vieclam24h"
    external_id: str
    title_raw: str
    description_raw: str
    salary_raw: str | None
    location_raw: str | None
    posted_at: date | None
    crawled_at: datetime
    content_hash: str               # dedup + cache, tránh gọi LLM lại cho JD trùng
```

### `job_extracted_signals` — kết quả sau extraction hybrid

```python
class JobExtractedSignal(BaseModel):
    job_posting_id: str
    normalized_career_id: str
    skills: list[str]                # đã map về canonical taxonomy
    unmapped_skills: list[str]       # skill không map được, giữ lại để review
    salary_min: int | None
    salary_max: int | None
    normalized_location: str
    experience_level: str            # "intern" | "junior" | "mid" | "senior"
    extraction_model: str            # "rule" | "gemini-2.5-flash" | ...
    extraction_version: str
    confidence: float                # 0-1
```

### `demand_summaries` — tổng hợp theo nghề/vùng/kỳ

```python
class DemandSummary(BaseModel):
    career_id: str
    location_id: str
    period: str                      # "2026-Q1"
    job_count: int
    top_skills: list[str]
    salary_stats: dict                # {"min": ..., "max": ..., "median": ...}
    trend_metrics: dict | None         # chỉ điền nếu có đủ dữ liệu lịch sử (xem notes mục 6.7)
    snapshot_version: str
```

---

## Sở hữu bởi `profile-service` (ghi + đọc riêng)

### `student_profiles`

```python
class StudentProfile(BaseModel):
    id: str
    session_id: str                   # session_id do core phát hành, dùng chung để liên kết
    profile_version: int
    raw_answers: list[dict]           # danh sách {question_id, answer}, có thể nhiều vòng hỏi
    structured_profile: dict          # đã chuẩn hoá: interests, strengths, preferred_region, willing_to_relocate...
    confirmed_by_user: bool           # user đã review/xác nhận trước khi gửi sang core
    created_at: datetime
    updated_at: datetime
```

Không có `conversation_log` dạng hội thoại tự do (xem quyết định 6.1 trong notes) — nhưng khác với bản form tĩnh trước đó, `raw_answers` giờ là list vì adaptive questioning có nhiều vòng hỏi.

### `question_bank` — kho câu hỏi, chỉ profile-service dùng

```python
class Question(BaseModel):
    id: str
    text: str
    competency_group: str             # nhóm năng lực mà câu hỏi này đo (VD: "analytical", "creative"...)
    depth_level: int                  # 1 = câu hỏi cố định ban đầu, 2+ = câu hỏi đào sâu
    trigger_condition: dict | None     # điều kiện để hệ thống chọn câu này (dựa trên câu trả lời trước)
```

`adaptive_engine.py` đọc bảng này để quyết định câu hỏi tiếp theo dựa trên `raw_answers` hiện tại của session.

---

## Sở hữu bởi `core` (ghi + đọc)

### `anonymous_sessions` — thay thế hoàn toàn cho users/auth

```python
class AnonymousSession(BaseModel):
    id: str
    session_token_hash: str          # không lưu token dạng plaintext
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime              # TTL 24h hoặc 7 ngày cho MVP
    deleted_at: datetime | None
```

Không có bảng `users`, `accounts`, `auth_sessions`, `user_credentials`. `core` phát hành `session_id`; `profile-service` dùng lại đúng `session_id` này để liên kết dữ liệu (xem "Cần chốt tiếp" trong notes về cách 2 service xác thực lẫn nhau).

### `recommendations`

```python
class SkillGapItem(BaseModel):
    skill: str
    current_level: float
    required_level: float

class ScoreBreakdown(BaseModel):
    interest_match: float            # trọng số 30%
    skill_match: float                # trọng số 30%
    market_demand: float              # trọng số 20%
    work_preference_match: float      # trọng số 10%
    location_compatibility: float     # trọng số 10%
    total: float                      # 0-100, hiển thị "Điểm phù hợp: X/100"

class PathwayMilestone(BaseModel):
    title: str
    duration: str                     # VD: "3 tuần"
    goal: str
    reason: str
    evidence: dict                    # {"source_snapshot": ..., "frequency": ...}
    timeframe: str                    # "0-3 tháng" | "3-12 tháng"
    action_type: str                  # "self_study" | "vocational" | "university" | "portfolio"

class CareerRecommendation(BaseModel):
    id: str
    session_id: str
    student_profile_snapshot: dict     # copy structured_profile tại thời điểm chạy (core không tự đọc DB của profile-service)
    profile_version: int
    demand_snapshot_version: str
    scoring_version: str
    career_id: str
    score_breakdown: ScoreBreakdown
    skill_gaps: list[SkillGapItem]
    pathway: list[PathwayMilestone]    # giới hạn 0-12 tháng
    is_alternative_of: str | None
    bias_check_passed: bool
    disclaimer: str
    created_at: datetime
```

**Lưu ý quan trọng do tách service:** `core` không có quyền đọc trực tiếp database của `profile-service`. Khi tạo recommendation, `core` nhận `structured_profile` qua API call (`POST /recommendations` kèm payload, hoặc `core` tự gọi `GET /profile/current` sang `profile-service`) và **lưu lại snapshot** (`student_profile_snapshot`) tại thời điểm chạy — để sau này vẫn trace được dù profile bên `profile-service` đã đổi tiếp.

### `recommendation_feedback`

```python
class RecommendationFeedback(BaseModel):
    session_id: str
    recommendation_id: str
    feedback_type: str                # "hide_career" | "not_interested" | "helpful" | "not_helpful" | "comment"
    career_id: str | None
    comment: str | None
    created_at: datetime
```

Feedback **chỉ** dùng để ẩn nghề / đánh giá hữu ích / ghi chú, xử lý trong `core` — không dùng để sửa profile. Sửa profile đi qua `PATCH /profile/current` ở `profile-service`, tạo `profile_version` mới; frontend gọi lại `POST /recommendations` (`core`) để rerun.

### `shared_reports` (tuỳ chọn — chỉ nếu giữ counselor dashboard)

```python
class SharedReport(BaseModel):
    id: str
    recommendation_id: str
    share_code_hash: str
    expires_at: datetime
    revoked_at: datetime | None
```

---

## Taxonomy dùng chung (bắt buộc, để tránh lệch tên field giữa 3 service)

> Vì 3 service không còn chung 1 codebase, taxonomy này cần được **đóng gói dưới dạng file JSON versioned** (hoặc package riêng), mỗi service tự copy/pull bản mới nhất — không import trực tiếp qua code như trước.

```json
{
  "skills": [
    {"raw_value": "ReactJS", "canonical_id": "react", "canonical_name": "React", "confidence": 0.96}
  ],
  "interest_groups": [
    "analytical", "creative", "social", "technical", "hands_on", "leadership", "structured"
  ],
  "industries": ["IT", "Marketing", "Kế toán", "Cơ khí", "Du lịch"],
  "regions": ["Hà Nội", "Yên Bái", "Đà Nẵng"]
}
```

Skill không map được lưu riêng trong `unmapped_skills` (bảng `job_extracted_signals`) để đội review thủ công, không bỏ qua âm thầm.

---

## Việc cần chốt tiếp (chưa quyết định, ảnh hưởng schema)

1. **`profile-service` dùng cùng Postgres instance với `core`/`crawl-service` (khác schema/namespace) hay dùng database hoàn toàn riêng?** Ảnh hưởng tới cách deploy và cách backup.
2. **Cơ chế xác thực giữa `profile-service` và `core`:** dùng chung `session_id` do `core` phát hành (profile-service tin tưởng session_id trong cookie) hay cần thêm service-to-service auth (API key nội bộ)?
3. **`core` gọi `profile-service` để lấy `structured_profile` lúc nào:** ngay khi frontend gọi `POST /recommendations` (core tự fetch), hay frontend gửi kèm `structured_profile` sẵn trong request body (core không cần gọi ngược lại profile-service)? Cách 2 đơn giản hơn, giảm phụ thuộc runtime giữa 2 service.
