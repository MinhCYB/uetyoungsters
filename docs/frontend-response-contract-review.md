# Frontend review — analysis response contract 1.0.0

## Kết luận

Ba file response do phía backend/AI phát hành **không có trong workspace tại thời
điểm review**, vì vậy frontend chưa thể xác nhận một contract bên ngoài là đầy đủ.

Frontend đã tạo bộ reference `1.0.0`, adapter strict và màn hình kiểm thử tại
`/contract-preview`. Nếu response backend đúng cấu trúc reference dưới đây thì
**đủ để render** Ability profile, ba loại gap, Weekly plan, Before/after,
Warning và Next step mà không cần đọc dữ liệu nội bộ.

## Field UI thực sự cần

### Chung cho cả ba response

`contract_version`, `response_type`, `request_id`, `student_id`, `generated_at`,
`title`, `summary`, `warnings[]`, `next_steps[]`.

Mỗi warning cần `code`, `severity`, `title`, `message`; `suggested_action` optional.
Mỗi next step cần `step_id`, `title`, `priority`; `description`, `route` optional.

### Initial analysis

- `ability_profile[]`: `ability_id`, `display_name`, `level`; `score`,
  `max_score`, `confidence`, `explanation` có thể nullable nếu chưa quan sát.
- `gaps[]`: `gap_id`, `gap_type`, `subject_id`, `display_name`, `priority`,
  `description`.

### Plan generation

- `plan_id`, `duration_weeks`, `progress_percentage`.
- `weekly_plan[]`: `week_number`, `title`, `objective`, `estimated_minutes`.
- `activities[]`: `activity_id`, `title`, `status`.

### Follow-up evaluation

- `baseline_analysis_id`, `progress_percentage`.
- `before_after[]`: `subject_id`, `display_name`, `before`, `after`,
  `max_value`, `delta`; `interpretation` optional.

## Yêu cầu cụ thể nếu contract backend chưa có

Không yêu cầu “response dễ dùng hơn”. Frontend yêu cầu chính xác:

1. Thêm `display_name` cho mọi ability, skill/knowledge/experience gap và subject
   trong before/after. UI không tự dịch canonical ID.
2. Thêm `gap_type` enum `knowledge | skill | experience`. Không suy luận loại gap
   từ ID hoặc mô tả.
3. Thêm `progress_percentage` dạng số 0–100 cho plan và follow-up. UI không tự
   suy luận từ số activity vì activity có thể optional hoặc trọng số khác nhau.
4. Thêm `max_score`/`max_value` cùng điểm số để UI vẽ tỷ lệ đúng; không mặc định
   mọi thang điểm là 100.
5. Thêm `before`, `after`, `delta` cùng một thang đo cho từng subject.
6. Thêm `title` và `message` đã sẵn sàng hiển thị cho warning; `code` không phải
   nội dung giao diện.
7. Thêm `title`, `priority` và `route` nullable cho next step. Frontend không tự
   dựng route từ `step_id`.
8. Thêm `estimated_minutes` cho từng tuần để học sinh biết tải học tập.

`localized_label` không bắt buộc trong `1.0.0` nếu enum thuộc danh sách đóng và
được version hóa. `display_name` bắt buộc cho entity nghiệp vụ vì taxonomy name
có thể thay đổi và frontend không sở hữu taxonomy.

## Field chưa rõ ý nghĩa nếu xuất hiện mà thiếu định nghĩa

- `confidence`: phải thống nhất 0–1, không lúc 0–1 lúc 0–100.
- `score`: phải luôn đi kèm `max_score` và mô tả nguồn/thang đo ở contract.
- `progress_percentage`: là tiến độ hoàn thành kế hoạch, không phải mức tăng năng lực.
- `priority`: là ưu tiên hành động, không phải mức độ yếu của học sinh.
- `delta`: dùng `after - before`; số dương là cải thiện.

## Field quá kỹ thuật, không đưa vào component hiển thị

- Evidence item IDs, raw evidence spans, prompt/model metadata.
- Feature vector, embedding, logits và internal confidence breakdown.
- Rule/threshold ID, threshold config và debug trace.
- Queue/job metadata, storage key, database table/column.
- Taxonomy join internals ngoài canonical ID cần cho action/analytics.

Các field này có thể tồn tại trong response nội bộ nhưng adapter UI chủ động bỏ
qua. Không được dùng chúng làm nguồn duy nhất để tạo nhãn hoặc thông điệp UI.

## Enum sang tiếng Việt

| Nhóm | Enum | Nhãn UI |
|---|---|---|
| Ability | `not_observed` | Chưa đủ dữ liệu |
| Ability | `emerging` | Đang hình thành |
| Ability | `developing` | Đang phát triển |
| Ability | `proficient` | Thành thạo |
| Ability | `advanced` | Nổi trội |
| Gap | `knowledge` | Kiến thức |
| Gap | `skill` | Kỹ năng thực hành |
| Gap | `experience` | Trải nghiệm |
| Priority | `low` | Thấp |
| Priority | `medium` | Trung bình |
| Priority | `high` | Cao |
| Priority | `critical` | Cần ưu tiên ngay |
| Warning | `info` | Lưu ý |
| Warning | `caution` | Cần thận trọng |
| Warning | `important` | Quan trọng |
| Step | `not_started` | Chưa bắt đầu |
| Step | `in_progress` | Đang thực hiện |
| Step | `completed` | Đã hoàn thành |
| Step | `skipped` | Đã bỏ qua |

Mapping thực thi nằm trong `frontend/src/contracts/responseLabels.js`.

## Xác nhận ranh giới dữ liệu

Frontend **không cần và không được đọc trực tiếp**:

- Evidence internals.
- Parquet.
- Fixture của backend/test.
- Threshold config.

Frontend chỉ nhận response JSON version hóa qua API. Ba JSON trong
`frontend/src/mocks/` là reference UI contract để chạy component preview, không
phải nguồn dữ liệu production.
