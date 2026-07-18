# Student Companion Core — Integration Contract 1.0.0

## 1. Scope

Student Companion core nhận dữ liệu học sinh đã có cấu trúc, chuẩn hóa evidence,
tạo ability profile, ba loại gap, weekly plan, follow-up outcomes và next step.
Public boundary là `StudentCompanionFacade` cùng các Pydantic contract version
`1.0.0`.

Core không thu thập học bạ, xác thực người dùng, lưu database, quản lý session,
cung cấp production HTTP endpoint hay render giao diện. Core không đọc fixture,
JSON hay Parquet qua public facade; nguồn dữ liệu được cung cấp qua request và
ports.

## 2. Reusable core và demo-only

### Reusable core

- `student_companion/domain/models.py`: input và derived domain models.
- `student_companion/domain/enums.py`: stable domain vocabulary.
- `student_companion/domain/rules.py`: normalization, ability, gap, planner,
  outcome và next-step rules thuần.
- `student_companion/contracts/`: public request/response/error models.
- `student_companion/application/facade.py`: stateless public use cases.
- `student_companion/application/ports.py`: integration protocols.
- `student_companion/infrastructure/market.py`: read-only market provider có
  fallback rõ data mode.

### Demo-only

- `fixtures/` và `infrastructure/fixtures.py`: persona synthetic Nguyễn Minh Anh.
- `infrastructure/demo_contract_adapter.py`: fixture-to-contract adapter.
- `application/service.py`: in-memory demo state machine.
- `run_demo.py`: local standard-library HTTP server.
- `static/`: local demo UI.
- `scripts/preflight.py`, `DEMO_SCRIPT.md`: demo operations.
- `fixtures/market_fallback.json`: fallback content dành cho demo.

Các thành phần demo vẫn được giữ nguyên để regression test; production không
import chúng vào core flow.

## 3. Ownership boundaries

| Owner | Cung cấp / chịu trách nhiệm |
|---|---|
| Profile team | `StudentProfile`, `AcademicRecord`, `TeacherObservation`, `AssessmentAttempt`, `ActivityResult`, stable IDs, timestamps, schema versions |
| Companion core | Ability profile, academic/exploration/decision gaps, weekly plan, outcomes, next step, warnings |
| Backend integration | Authentication, authorization, persistence, session, endpoint, audit logging, request IDs |
| Frontend | Presentation, localization, navigation, input forms, loading/error states |

Không có adapter cho schema profile production cho đến khi schema đó được chốt.
Production team implement `StudentInputProvider` hoặc mapping riêng tại boundary.

## 4. Public use cases

### Initial analysis

`InitialAnalysisRequest → facade.analyze() → InitialAnalysisResponse`

Request chứa profile, academic records, teacher observations, ít nhất một
diagnostic/pretest, optional self-report và prior activity results. Response
chứa snapshot T0, ability, gaps, market context, evidence counts và warnings.

### Plan generation

`PlanGenerationRequest → facade.generate_plan() → PlanGenerationResponse`

Request chứa student, snapshot đã phân tích và completed activity IDs. Response
chứa `WeeklyPlan`; tổng phút luôn nhất quán với tasks và không vượt budget.

### Follow-up evaluation

`FollowupEvaluationRequest → facade.evaluate_followup() → FollowupEvaluationResponse`

Request chứa previous snapshot và ít nhất một posttest hoặc activity result. Để
tạo assessment outcome trước/sau, nên gửi diagnostic/pretest so sánh được cùng
`assessment_id`; nếu thiếu baseline, response trả warning thay vì tự bịa dữ liệu.

## 5. Required và optional fields

| Contract | Required | Optional/được phép rỗng |
|---|---|---|
| `ContractMetadata` | Tất cả field; `contract_version=1.0.0`, request ID, source, requested timestamp | `taxonomy_version` có thể `null` |
| `InitialAnalysisRequest` | metadata, student, assessment có diagnostic/pretest, mọi collection field | `academic_records`, `teacher_observations`, `prior_activity_results` có thể rỗng; `self_report` có thể `null` và sinh warning |
| `PlanGenerationRequest` | metadata, student, snapshot, completed activity list | list có thể rỗng |
| `FollowupEvaluationRequest` | metadata, student, previous snapshot, assessment/activity lists | một list có thể rỗng nếu list còn lại đáp ứng posttest/activity rule |

Caller phải truyền collection rỗng hoặc `null` đúng contract; field không có
default ngầm. Unknown field bị từ chối.

## 6. Versioning

- `contract_version`: public wire contract; hiện chỉ chấp nhận `1.0.0`.
- `schema_version`: version của từng input record do source owner cung cấp.
- `taxonomy_version`: taxonomy mà source/backend dùng để map stable IDs.
- `pipeline_version`: business pipeline ghi trong snapshot.
- `snapshot_version`: market snapshot/data provenance.

Thay đổi additive optional có thể giữ backward compatibility trong minor
version. Rename, xóa field, thay semantics hoặc validation cần contract version
mới. Không thay interpretation của stable ID trong cùng version.

## 7. Error và warning behavior

Validation lỗi request tạo Pydantic validation error tại boundary. Runtime
integration lỗi có `ContractExecutionError.error: ContractError`.

| Tình huống | Hành vi |
|---|---|
| Thiếu diagnostic/pretest ban đầu | Request bị reject |
| Nested student ID không khớp | Request bị reject với field context |
| Unknown career group | Warning `unknown_career_group`; academic analysis continues and no unsupported activity is assigned |
| Evidence quá ít | Warning `insufficient_evidence` |
| Optional profile data thiếu | Warning `optional_data_missing` |
| Market sample dưới 5 | Warning `small_market_sample` |
| Posttest thiếu baseline so sánh | Warning `baseline_not_found`; không tạo assessment outcome giả |

Warning không chứa teacher note hoặc dữ liệu nhạy cảm. Evidence summary chỉ có
source type và count.

## 8. Integration sequence

```text
Profile source
  → production adapter
  → InitialAnalysisRequest
  → StudentCompanionFacade.analyze()
  → InitialAnalysisResponse
  → production API/persistence
  → frontend
```

Market implementation được inject qua `MarketContextProvider`. Core không biết
market đến từ Parquet, database hay service khác. Sprint này không tạo HTTP
client.

## 9. Production migration checklist

Port/cherry-pick theo dependency nhỏ, không merge nguyên demo branch:

1. `domain/enums.py`, `domain/models.py`, `domain/rules.py`, `config.py`.
2. `contracts/` và contract tests.
3. `application/ports.py` và `application/facade.py`.
4. Market provider hoặc implementation production của `MarketContextProvider`.
5. Behavior/invariant tests và JSON examples để consumer review.
6. Viết profile adapter sau khi profile schema chính thức được chốt.
7. Bọc facade bằng production API, auth, persistence và audit logging.
8. Frontend consume response contract; không đọc Parquet hay fixture.

Không port local server, static demo UI, synthetic fixtures hoặc demo state
machine vào production trừ khi dùng riêng cho sandbox/testing.

## 10. Contract examples

Sáu JSON trong `integration_examples/` được sinh bằng facade thật:

```powershell
python -m phase1_demo.scripts.export_contract_examples
```

Exporter dùng request IDs và timestamps cố định từ demo adapter; chạy lại tạo
cùng byte content.
