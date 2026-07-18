# Contract hồ sơ học sinh cho phân tích ban đầu và đánh giá tiếp diễn

Contract thực thi nằm tại `backend-api/modules/candidate/analysis_contracts.py`.
Pydantic cấu hình `extra="forbid"`: field ngoài schema bị từ chối thay vì bị bỏ qua.

## Payload gốc

```json
{
  "schema_version": "1.0.0",
  "profile_version": 1,
  "generated_at": "2026-07-19T08:00:00Z",
  "student": {},
  "academic_records": [],
  "teacher_observations": [],
  "assessment_attempts": [],
  "self_report": null,
  "activity_results": []
}
```

Hai mẫu bàn giao:

- `tests/fixtures/student_profile_initial.json`: hồ sơ ban đầu, có diagnostic và pretest, `self_report = null`.
- `tests/fixtures/student_profile_week3.json`: snapshot tuần 3, có pretest, posttest, self-report và activity result.

## Field bắt buộc và tùy chọn

| Object | Bắt buộc | Tùy chọn / nullable |
|---|---|---|
| Payload | `schema_version`, `profile_version`, `generated_at`, sáu nhóm dữ liệu | Không có |
| Student | `student_id`, `tenant_id`, `class_id`, `student_code`, `display_name`, `profile_type` | `grade_level`, `date_of_birth` |
| AcademicRecord | `record_id`, `student_id`, `subject_id`, `subject_name`, `period`, `score`, `score_scale`, `recorded_at`, `source` | Không có |
| TeacherObservation | `observation_id`, `student_id`, `teacher_id`, `observed_at`, `context`, `skill_ids`, `observation`, `visibility` | Không có; `skill_ids` phải có ít nhất một ID |
| AssessmentAttempt | `attempt_id`, `student_id`, `assessment_id`, `purpose`, `started_at`, `status`, `skill_scores` | `submitted_at`, `total_score`, `total_max_score` khi chưa scored |
| SkillScore | `skill_id`, `score`, `max_score` | `evidence_item_ids` mặc định rỗng |
| SelfReport | Toàn object có thể `null`; nếu có thì cần `submitted_at` | Các danh sách mặc định rỗng; `weekly_learning_hours`, `free_text` nullable |
| ActivityResult | `activity_result_id`, `student_id`, `activity_id`, `completed_at`, `skill_id`, `score`, `max_score` | `duration_minutes`, `evidence` |

Với assessment `status = scored`, `submitted_at`, điểm tổng và ít nhất một
`skill_scores[]` là bắt buộc. Điểm tổng không thay thế điểm theo `skill_id`.

## ID

ID là opaque string, lowercase ASCII, bất biến sau khi tạo và không tái sử dụng:

- `student_id`: `stu_<tenant-or-source>_<stable-key>`.
- `record_id`: `acr_<subject-or-type>_<period>_<stable-key>`.
- `attempt_id`: `att_<purpose>_<stable-key>`.
- `activity_result_id`: `act_<activity>_<stable-key>`.
- `observation_id`: `obs_<context>_<stable-key>`.

Client không tự tạo lại ID khi sửa dữ liệu. Database/service sinh ID; import phải
giữ mapping từ source key sang canonical ID để retry không tạo bản ghi trùng.
Mọi child resource phải có cùng `student_id` với object `student`, nếu không
validation thất bại.

## Timestamp và version

- Tất cả timestamp dùng ISO-8601/RFC 3339 có timezone; chuẩn trao đổi là UTC với hậu tố `Z`.
- `generated_at` là thời điểm snapshot được dựng, không thay thế timestamp sự kiện.
- `recorded_at`, `observed_at`, `started_at`, `submitted_at`, `completed_at` giữ thời điểm nghiệp vụ thật.
- `schema_version` dùng SemVer. Thay đổi breaking tăng major; thêm field optional tăng minor; sửa mô tả/validation tương thích tăng patch.
- `profile_version` là số nguyên tăng đơn điệu theo từng học sinh. Bất kỳ thay đổi nào làm payload phân tích khác đi phải tăng version.
- Consumer phải xử lý idempotent theo `(student_id, profile_version)`.

## Loại assessment

`AssessmentAttempt.purpose` là enum và phân biệt rõ:

- `diagnostic`: đánh giá chẩn đoán/phân tích ban đầu.
- `pretest`: baseline trước hoạt động hoặc can thiệp.
- `posttest`: đo lại sau hoạt động hoặc can thiệp.

Mỗi điểm thành phần bắt buộc nằm trong `skill_scores[]` và có `skill_id`.
`total_score` chỉ phục vụ hiển thị/tổng hợp, không dùng để suy ra kỹ năng.

## Mapping sang AI request

**Có, map được hoàn toàn** sau khi contract này được thêm vào repo:

- Hồ sơ ban đầu → `to_initial_analysis_request(...)` → `InitialAnalysisRequest`.
- Hồ sơ tuần 2–3 → `to_followup_evaluation_request(...)` → `FollowupEvaluationRequest`.

Follow-up bổ sung metadata ngoài payload:

- `baseline_analysis_id` bắt buộc để chỉ kết quả ban đầu cần so sánh.
- `window_started_at` và `window_ended_at` bắt buộc để xác định cửa sổ đánh giá.
- Snapshot follow-up bắt buộc có ít nhất một assessment `posttest`.

Không còn field dữ liệu học sinh nào bị thiếu cho hai request đã định nghĩa.
AI worker chưa chạy job thực tế; bước tích hợp kế tiếp là đưa hai model này vào
queue handler thay cho payload dictionary không version.

## Endpoint/hàm trả payload

Hàm mapping đã có và là điểm tích hợp chính thức:

```python
to_initial_analysis_request(payload, request_id=..., requested_at=...)
to_followup_evaluation_request(
    payload,
    request_id=...,
    requested_at=...,
    baseline_analysis_id=...,
    window_started_at=...,
    window_ended_at=...,
)
```

Endpoint backend dự kiến:

```text
GET /api/teacher/students/{student_id}/analysis-payload?profile_version=latest
```

Endpoint phải dùng RBAC + tenant scope + assignment lớp đang hiệu lực trước khi
dựng snapshot. Student chỉ được lấy payload của chính mình qua endpoint ownership
riêng; không cho frontend gửi `tenant_id` để quyết định phạm vi.
