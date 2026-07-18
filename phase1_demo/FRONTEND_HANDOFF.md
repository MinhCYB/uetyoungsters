# Frontend Handoff — Student Companion Contract 1.0.0

Frontend production nhận dữ liệu từ backend integration, không gọi domain rules
và không đọc trực tiếp Parquet hoặc synthetic fixtures.

## Nội dung nên render

| UI | Field path theo public contract |
|---|---|
| Ability cards | `initialAnalysisResponse.ability_profile` hoặc `followupEvaluationResponse.current_snapshot.ability_profile` |
| Gap cards ban đầu | `initialAnalysisResponse.gaps` |
| Gap cards cập nhật | `followupEvaluationResponse.updated_gaps` |
| Weekly plan | `planGenerationResponse.plan.tasks` và `planGenerationResponse.plan.total_planned_minutes` |
| Before/after | `followupEvaluationResponse.outcomes` |
| Next step | `followupEvaluationResponse.next_step` |
| Warnings | `response.warnings` của từng use case |
| Evidence source/count | `response.evidence_summary` |

## Presentation rules

- Không render raw `evidence_id` trong giao diện chính; raw IDs chỉ dành cho
  debug/support view có kiểm soát.
- Không dùng enum trực tiếp làm label. Map localization cho gap type, priority,
  outcome status, evidence source, trend và task type.
- Hiển thị `ContractWarning` bằng ngôn ngữ dễ hiểu, không biến warning thành lỗi
  chặn luồng nếu `recoverable` semantics cho phép tiếp tục.
- Không suy diễn hoặc hiển thị kết luận nghề nghiệp cuối cùng. `next_step` là
  hoạt động thu thập thêm evidence, không phải recommendation tuyệt đối.
- Loading/error/retry state thuộc frontend/backend integration, không thuộc core.
- Hiển thị market `sample_size`, `data_mode` và warning mẫu nhỏ để người dùng
  hiểu giới hạn của tín hiệu.

## Null và empty handling

- `next_step = null`: không có task phù hợp; hiển thị trạng thái trung tính.
- `self_report = null`: backend có thể trả `optional_data_missing`.
- Empty `warnings`: không render warning panel.
- Empty `outcomes`: chưa có baseline đủ để so sánh; không tự tính delta ở UI.
- `active_plan = null`: snapshot chưa có plan đang hoạt động.

Frontend chỉ format các số đã có trong response. Không tự tính ability, gap,
priority, outcome status hoặc planned minutes từ raw inputs.

## Debug and provenance

Nếu cần technical details, có thể render `evidence_ids`, `snapshot_id`,
`previous_snapshot_id`, versions và `request_id` trong panel debug đóng mặc
định. Không đưa teacher note hoặc raw sensitive profile data vào telemetry/UI
nếu chưa có consent và data policy tương ứng.
