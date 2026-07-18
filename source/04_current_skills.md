# Ngân hàng câu hỏi — Kỹ năng hiện tại

## Mục tiêu

Phần này thu thập kỹ năng tự khai báo và bối cảnh sử dụng. Tên kỹ năng nên được chuẩn hóa bằng ESCO hoặc O*NET trước khi liên kết với nghề.

## A. Khám phá kỹ năng

1. Bạn thường được người khác nhờ hỗ trợ việc gì?
2. Bạn đã hoàn thành những môn học, khóa học hoặc chứng chỉ nào?
3. Bạn từng tạo ra sản phẩm hoặc dự án nào?
4. Bạn sử dụng công cụ, phần mềm hoặc thiết bị nào?
5. Bạn có thể giải thích hoặc hướng dẫn người khác làm việc gì?
6. Trong hoạt động nhóm, bạn thường đảm nhiệm vai trò nào?
7. Bạn từng làm công việc bán thời gian, tình nguyện hoặc câu lạc bộ nào?
8. Có kỹ năng nào bạn tự học ngoài trường không?
9. Có kỹ năng nào bạn từng làm tốt nhưng không muốn dùng trong nghề không?
10. Có kỹ năng nào bạn muốn học trong sáu tháng tới?

## B. Form cho từng kỹ năng

```text
Tên kỹ năng:
Bạn dùng kỹ năng này trong bối cảnh nào?
Lần gần nhất sử dụng là khi nào?
Bạn sử dụng thường xuyên đến mức nào?
Bạn có thể tự hoàn thành loại nhiệm vụ nào?
Bạn có sản phẩm hoặc bằng chứng nào không?
Bạn tự đánh giá mức độ hiện tại?
```

Mức tự đánh giá:

```text
0 — Chưa bắt đầu
1 — Biết khái niệm, cần hướng dẫn nhiều
2 — Tự hoàn thành nhiệm vụ cơ bản
3 — Tự hoàn thành nhiệm vụ có độ phức tạp vừa
4 — Có thể xử lý tình huống khó và hướng dẫn người khác
```

## C. Câu neo mức độ

1. Bạn có thể thực hiện nhiệm vụ mà không xem lại hướng dẫn không?
2. Khi gặp lỗi, bạn có thể tự tìm nguyên nhân không?
3. Bạn có thể áp dụng kỹ năng trong một bối cảnh mới không?
4. Bạn có thể giải thích lý do chọn phương pháp đó không?
5. Bạn có thể đánh giá chất lượng kết quả không?
6. Bạn có thể hướng dẫn người mới bắt đầu không?

## D. Nhóm kỹ năng gợi ý để nhập

### Công nghệ và dữ liệu

- Lập trình.
- SQL và cơ sở dữ liệu.
- Bảng tính.
- Phân tích dữ liệu.
- Trực quan hóa dữ liệu.
- Thiết kế giao diện.
- Sử dụng công cụ AI.
- An toàn thông tin.

### Ngôn ngữ và nội dung

- Viết.
- Đọc hiểu.
- Thuyết trình.
- Ngoại ngữ.
- Biên tập.
- Viết nội dung truyền thông.

### Kinh doanh và tổ chức

- Bán hàng.
- Chăm sóc khách hàng.
- Quản lý dự án.
- Lập kế hoạch.
- Quản lý tài chính cá nhân.
- Nghiên cứu thị trường.

### Kỹ thuật và thực hành

- Đọc bản vẽ.
- Sửa chữa thiết bị.
- Lắp ráp.
- Vận hành máy móc.
- Thiết kế kỹ thuật.
- Kiểm soát chất lượng.

### Xã hội và dịch vụ

- Giảng dạy.
- Tư vấn.
- Chăm sóc.
- Tổ chức sự kiện.
- Điều phối nhóm.
- Giải quyết xung đột.

## E. Schema lưu trữ

```json
{
  "skill_name_raw": "Excel",
  "normalized_skill_id": "esco_or_onet_id",
  "normalized_skill_name": "use spreadsheet software",
  "self_level": 2,
  "usage_frequency": "weekly",
  "last_used": "2026-07",
  "experience_context": "project môn học",
  "can_do_statement": "tạo bảng tổng hợp và biểu đồ cơ bản",
  "evidence": "báo cáo phân tích bán hàng",
  "verification_status": "self_report"
}
```

Kỹ năng tự khai báo không được coi là đã xác minh. Nếu kỹ năng ảnh hưởng mạnh đến nghề gợi ý, hệ thống nên đề xuất một mini-task liên quan.

