# Student Companion Live LLM Integration — Audit

## Phạm vi và trạng thái Git

- Worktree: `D:/UET/uetyoungsters-e2e`.
- Branch triển khai: `feature/student-companion-live-llm`.
- Branch gốc: `integration/student-companion-e2e-final`; `HEAD` hiện trùng commit `13f88b1` của branch gốc.
- `origin/main` ở commit merge `edf1207`. So sánh tree `HEAD..origin/main` không có thay đổi path cần mang sang branch này, vì vậy không cần merge `origin/main`.
- Working tree sạch tại thời điểm bắt đầu audit.

## Kiến trúc hiện tại

### Thành phần chịu trách nhiệm

- `backend-api/modules/companion/router.py` công bố Student Companion API dưới prefix `/api/companion`.
- `backend-api/modules/companion/service.py` chuyển profile contract sang Engine V1, điều phối analysis/plan/follow-up, lưu state demo trong `CompanionStore`, và điều phối content generation.
- `phase1_demo/student_companion/application/facade.py` cùng domain/rules chịu trách nhiệm quyết định nghiệp vụ deterministic.
- `phase1_demo/student_companion/llm/` chứa prompt, internal content contracts, validator, provider port và orchestrator. Đây là lớp phù hợp để tích hợp AI Worker mà không đưa business logic vào gateway.
- `ai-worker-service/main.py` là Gemini gateway generic, chỉ có `GET /health` và `POST /infer`.

### Endpoint Student Companion

- `POST /api/companion/analyze`
- `POST /api/companion/plan`
- `POST /api/companion/followup`
- `POST /api/companion/content/expand-plan`
- `POST /api/companion/content/reassessment`
- `POST /api/companion/content/feedback`
- `POST /api/companion/reset`

Ba endpoint analysis/plan/follow-up là kết quả Engine deterministic và không thuộc phạm vi sinh nội dung bằng LLM. Ba endpoint dưới `/content/` là điểm tích hợp Live LLM.

## Request flow hiện tại

```text
Browser / frontend companionApi.js
  -> same-origin /api/companion/*
  -> nginx location /api/ (bỏ prefix /api khi proxy_pass)
  -> backend-api:8000 /api/companion/*
  -> CompanionService
     -> StudentCompanionFacade / Engine (analyze, plan, follow-up)
     -> StudentCompanionContentOrchestrator (content endpoints)
        -> TemplateProvider
```

AI Worker chưa nằm trong request flow của Student Companion. Frontend không gọi Gemini hoặc AI Worker trực tiếp và không nhận API key.

## Mock, fixture, deterministic và template hiện tại

- `analyze` và `followup` đọc profile fixture từ `tests/fixtures/student_profile_initial.json` và `student_profile_week3.json`; request public vẫn chứa `fixture_selector`. Đây là golden-path/demo input, không phải LLM output.
- Engine analysis/plan/follow-up là deterministic theo Phase 1 rules.
- `CompanionService.__init__` đang khởi tạo `StudentCompanionContentOrchestrator(TemplateProvider())`; vì vậy cả ba content endpoint luôn trả `result_metadata.content_mode=template_fallback`.
- `TemplateProvider` dùng các template an toàn trong `fallback_templates.py`.
- `ExistingProviderAdapter` là placeholder fail-closed, chưa gọi dịch vụ thật.
- `FakeLLMProvider` chỉ dành cho test/offline demo.
- Orchestrator hiện retry provider tối đa hai lần rồi tự động dùng `TemplateProvider`. Fallback có metadata và warning rõ ràng, nhưng production hiện chưa có config để chọn fail-closed hay cho phép fallback.
- Frontend còn có mock mode được gắn nhãn riêng; API lỗi không tự chuyển sang mock.

## Contracts hiện tại

### AI Worker request

`POST {AI_WORKER_URL}/infer` nhận:

```json
{
  "system_prompt": "...",
  "messages": [{"role": "user", "content": "..."}],
  "response_format": "json",
  "max_tokens": 2048
}
```

`model` là optional và nên bỏ qua để AI Worker sử dụng `DEFAULT_MODEL`.

### AI Worker response

Response gồm `content`, `parsed`, `model`, và `usage`. Với JSON mode, `parsed=false` nghĩa là Gemini không trả JSON hợp lệ dù HTTP thành công.

### Student Companion internal content contracts

- `DetailedLearningPlan`
- `ReassessmentPackage`
- `PersonalizedFeedback`

Các model Pydantic đều `extra=forbid`. Orchestrator loại bỏ `content_id` và `result_metadata` do provider đưa vào, tạo lại metadata tin cậy, validate schema, rồi kiểm tra invariant nghiệp vụ/safety trước khi trả kết quả.

### Public frontend contract

- Analysis/plan/follow-up dùng contract `1.0.0` và adapter `frontend/src/contracts/responseAdapter.js`.
- Content endpoint trả trực tiếp internal content contract `1.0.0`; frontend chỉ đọc các field đã định nghĩa và `result_metadata`.
- Có thể giữ nguyên toàn bộ public response shape khi đổi provider từ template sang AI Worker.

## Cấu hình hiện tại

- Chỉ `ai-worker-service` nhận `GEMINI_API_KEY`, `DEFAULT_MODEL`, `DEFAULT_MAX_TOKENS`, `REQUEST_TIMEOUT_SECONDS` trong Compose.
- `backend-api` chưa nhận `AI_WORKER_URL`, timeout, token limit hoặc fallback mode.
- `roadmap-service` còn nhận `LLM_API_KEY`; đây là path ngoài Student Companion và không được thay đổi trong task này. Student Companion hiện không đọc `LLM_API_KEY`.
- Repository không có `.env.example` phù hợp cho Live LLM.
- AI Worker có healthcheck, nhưng `backend-api` chưa phụ thuộc health condition của AI Worker.

## Tests hiện tại

- `tests/test_ai_worker_service.py`: health, request mapping, JSON parsing, invalid JSON và upstream failure của Gemini gateway.
- `tests/test_companion_api.py`: public routes, golden path template và structured errors.
- `tests/test_student_companion_e2e.py`: mapping, deterministic Engine, public presentation contract và template content.
- `phase1_demo/tests/test_llm_*`: strict contracts, prompt privacy, validators, retry/fallback, deterministic/fake providers.
- Chưa có test client HTTP Student Companion -> AI Worker, payload `/infer`, `parsed=false`, timeout, connection error, HTTP 4xx/5xx, hay secret-safety của frontend bundle.

## Thay đổi dự kiến

- Thêm typed `AIWorkerProvider` và response model trong `phase1_demo/student_companion/llm/providers/`.
- Thêm lỗi provider có mã phân loại an toàn để phân biệt missing config, connection, timeout, HTTP, parsed=false, empty response và schema/invariant failure.
- Cấu hình `CompanionService` theo environment để dùng AI Worker; dependency injection vẫn cho phép tests dùng fake/template provider.
- Điều chỉnh orchestrator để production có thể fail-closed hoặc chỉ fallback khi config cho phép, không âm thầm giả kết quả live.
- Chuyển các lỗi content generation thành public `CompanionError` an toàn, không lộ exception/URL/secret.
- Cập nhật `docker-compose.yml`, `backend-api/requirements.txt`, tài liệu cấu hình và `.env.example`.
- Bổ sung tests ở `tests/` và giữ nguyên tests Phase 1 hiện có.

## Rủi ro tương thích

- Global `companion_service` được tạo lúc import; cấu hình environment thay đổi sau import trong tests sẽ không tự tái tạo provider. Cần factory hoặc constructor injection rõ ràng.
- Orchestrator hiện bắt mọi exception rồi fallback; nếu giữ nguyên, timeout/config error có thể bị che thành kết quả template thành công.
- AI Worker có thể trả `parsed=true` nhưng `content` không phải object hoặc sai internal schema. Mọi trường hợp vẫn phải đi qua Pydantic và invariant validators.
- Retry hai lần có thể làm tăng latency. HTTP timeout phải hữu hạn; không thêm vòng chờ startup vô hạn.
- Public contract và `content_mode` đang được frontend/tests dùng. Live success phải dùng `external_llm`; fallback (nếu bật) vẫn là `template_fallback` với warning.
- Test suite không được phụ thuộc network hoặc Gemini key.

## Kế hoạch triển khai

1. Định nghĩa AI Worker request/response typed và HTTP provider có transport injection.
2. Gửi đúng `system_prompt`, một user message, `response_format=json`, `max_tokens`; không gửi model.
3. Phân loại và sanitize lỗi ở provider boundary.
4. Dùng prompt/schema/validator Student Companion hiện có; bổ sung yêu cầu chỉ dùng supplied data và không tiết lộ system prompt nếu cần.
5. Tạo provider từ env trong backend. `AI_WORKER_URL` là bắt buộc ở live mode; timeout/token/fallback có cấu hình rõ ràng.
6. Mặc định container dùng live mode và gọi `http://ai-worker-service:8000`; chỉ AI Worker giữ Gemini key.
7. Giữ template mode/fallback cho demo/test bằng config explicit; không tự biến lỗi live thành mock thành công khi fallback bị tắt.
8. Viết tests cho success/payload và toàn bộ failure modes, public contract, frontend adapter/static secret safety.
9. Chạy test, build, diff checks và `docker compose config` nếu Docker khả dụng.

## Acceptance criteria

- Student Companion content endpoints gọi `POST /infer` qua typed client khi live mode được cấu hình.
- Payload đúng gateway contract, JSON mode và token limit; không hardcode/send model.
- Output luôn qua Pydantic schema và invariant validation trước public response.
- Lỗi config/connection/timeout/HTTP/parsed/empty/schema được phân biệt nội bộ và trả public error an toàn.
- Không có Gemini key hoặc direct Gemini call ngoài AI Worker; frontend bundle không chứa secret/API key.
- Public contract hiện tại không đổi ngoài `result_metadata.content_mode=external_llm` khi thành công.
- Deterministic fallback chỉ chạy khi cấu hình explicit và luôn có metadata/warning.
- Automated tests không gọi Gemini thật và tất cả quality gates pass.

## Điểm chưa đủ thông tin

- Chưa có policy deployment chính thức cho việc bật deterministic fallback trong production. Triển khai sẽ chọn fail-closed mặc định cho `live` và chỉ cho fallback khi `COMPANION_LLM_FALLBACK_ENABLED=true`.
- Chưa có yêu cầu token limit riêng theo use case; dùng default client-side `2048` theo task, còn model do AI Worker quyết định.
- Không có Gemini key thật trong môi trường audit; chỉ có thể xác minh HTTP integration bằng mocked transport và Compose config.

## Kết quả triển khai sau audit

- Đã thêm `AIWorkerProvider` typed sử dụng HTTP và transport injection, không gửi model và không biết Gemini key.
- Runtime mặc định là `COMPANION_LLM_MODE=live`, fail-closed khi thiếu cấu hình hoặc AI Worker lỗi. Test suite ép `template` rõ ràng và không gọi network.
- Fallback template trong live mode chỉ hoạt động khi `COMPANION_LLM_FALLBACK_ENABLED=true`; metadata vẫn ghi `template_fallback` và warning `provider_fallback_used`.
- Prompt được gắn JSON Schema từ Pydantic contract; `content_id` và `result_metadata` vẫn do server sở hữu. Output tiếp tục qua schema validation và invariant validation trước khi trả về.
- Compose truyền URL nội bộ, timeout và token limit cho backend; chỉ AI Worker nhận Gemini key/model. Backend chờ AI Worker healthcheck với số lần retry hữu hạn.
- Public contract không đổi; live success chỉ thay `result_metadata.content_mode` thành `external_llm`.
