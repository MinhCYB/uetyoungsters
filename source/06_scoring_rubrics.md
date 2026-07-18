# Rubric và nguyên tắc chấm

## 1. Thang chung

Mỗi tiêu chí chấm 0–3:

| Điểm | Ý nghĩa |
|---:|---|
| 0 | Không có bằng chứng hoặc trả lời lệch yêu cầu |
| 1 | Có tín hiệu nhưng mơ hồ, thiếu liên kết |
| 2 | Thể hiện tương đối rõ và hợp lý |
| 3 | Thể hiện rõ, có cấu trúc và kiểm tra được |

Điểm thấp trong một task chỉ có nghĩa năng lực **chưa được thể hiện trong task đó**, không chứng minh người dùng không có năng lực.

## 2. Rubric theo năng lực

### Phân tích và suy luận

- Xác định đúng vấn đề.
- Chọn thông tin liên quan.
- Tạo giả thuyết hoặc quan hệ logic.
- Sử dụng dữ liệu để hỗ trợ kết luận.
- Nhận ra thông tin còn thiếu.

### Tư duy phản biện

- Kiểm tra nguồn và độ tin cậy.
- Nhận diện giả định.
- Xem xét bằng chứng trái chiều.
- Phân biệt tương quan và nguyên nhân.
- Nêu giới hạn của kết luận.

### Sáng tạo và tạo ý tưởng

- Số ý tưởng phù hợp.
- Sự khác biệt giữa các nhóm ý tưởng.
- Tính mới trong bối cảnh task.
- Khả năng cải tiến ý tưởng.
- Khả năng đáp ứng giới hạn thực tế.

Không chấm sáng tạo chỉ bằng độ “lạ”; ý tưởng vẫn phải liên quan và có ích.

### Học hỏi và thích ứng

- Nhận ra khi chiến lược không còn phù hợp.
- Tiếp thu quy tắc hoặc phản hồi mới.
- Thay đổi cách làm phù hợp mục tiêu.
- Theo dõi kết quả sau khi thay đổi.
- Biết tìm thêm thông tin hoặc trợ giúp.

### Ngôn ngữ và diễn đạt

- Hiểu đúng nội dung.
- Chọn đúng ý chính.
- Cấu trúc rõ ràng.
- Ngôn ngữ phù hợp người nhận.
- Diễn đạt chính xác và súc tích.

Không đánh đồng lỗi chính tả nhỏ với khả năng suy luận kém.

### Lập kế hoạch và thực thi

- Xác định mục tiêu và đầu ra.
- Chia công việc thành bước.
- Sắp xếp ưu tiên và phụ thuộc.
- Phân bổ thời gian, người và nguồn lực.
- Có checkpoint và phương án dự phòng.

### Chú ý chi tiết

- Số lỗi đúng được phát hiện.
- Số cảnh báo sai.
- Phân loại đúng mức ảnh hưởng.
- Theo dõi đầy đủ các yêu cầu.
- Có hành vi kiểm tra lại.

Điểm hiệu suất có thể tính:

```text
Điểm thô = lỗi đúng × trọng số − cảnh báo sai × hệ số phạt
```

### Tương tác và hợp tác

- Lắng nghe và tìm hiểu bối cảnh.
- Giao tiếp tôn trọng, cụ thể.
- Làm rõ trách nhiệm và mục tiêu chung.
- Đưa ra giải pháp khả thi cho nhiều bên.
- Có bước theo dõi cam kết.

Không mặc định người nói nhiều là hợp tác tốt hơn.

## 3. Confidence

`score` trả lời “người dùng thể hiện tốt đến đâu trong task”. `confidence` trả lời “có thể tin đây là đặc điểm ổn định đến đâu”.

Quy tắc demo:

| Mức | Điều kiện gợi ý |
|---|---|
| Low | Một bằng chứng hoặc câu trả lời không đầy đủ |
| Medium | Hai bằng chứng khác loại, tương đối nhất quán |
| High | Từ ba bằng chứng khác loại, nhất quán, có task hiệu suất |

Không cho confidence cao chỉ vì câu trả lời dài.

## 4. Tổng hợp nhiều bằng chứng

```text
FinalScore = Σ(score × sourceWeight) / Σ(sourceWeight)
```

Trọng số baseline để thử nghiệm, không phải chuẩn khoa học cố định:

| Nguồn | Trọng số |
|---|---:|
| Tự khai báo | 0.3 |
| Thói quen tự báo cáo | 0.35 |
| Câu tự luận theo rubric | 0.6 |
| Task có đáp án rõ | 0.75 |
| Mini-task mô phỏng thực tế | 0.8 |
| Dự án hoặc sản phẩm | 0.85 |

Phải hiệu chỉnh sau pilot. Không cộng nhiều câu gần giống nhau như các bằng chứng hoàn toàn độc lập.

## 5. JSON đầu ra AI

```json
{
  "question_id": "CT01",
  "status": "scored",
  "evaluations": [
    {
      "dimension": "critical_thinking",
      "raw_score": 9,
      "max_score": 15,
      "normalized_score": 0.6,
      "confidence": "low",
      "status": "emerging_evidence",
      "reason": "Người dùng nhận ra mẫu khảo sát không đại diện và yêu cầu kiểm tra nguồn.",
      "evidence_quotes": [
        "Khảo sát chỉ lấy từ thành viên câu lạc bộ lập trình"
      ],
      "demonstrated": [
        "Nhận diện thiên lệch lựa chọn mẫu"
      ],
      "missing_evidence": [
        "Chưa kiểm tra định nghĩa mức lương cao",
        "Chưa xem xét quan hệ nhân quả"
      ],
      "next_task_id": "CT04"
    }
  ],
  "unsupported_dimensions": [
    "creativity",
    "collaboration"
  ]
}
```

## 6. Prompt chấm AI

```text
Bạn là hệ thống chấm bằng chứng năng lực hướng nghiệp.

Chỉ chấm theo target_dimensions và rubric được cung cấp.

Quy tắc:
1. Không suy luận giới tính, tính cách, hoàn cảnh hoặc nghề phù hợp.
2. Mỗi nhận định phải có bằng chứng từ câu trả lời.
3. Nếu không có bằng chứng, trả insufficient_evidence.
4. Phân biệt “không thể hiện trong câu trả lời” với “không có năng lực”.
5. Nêu cả điểm đã thể hiện và điểm chưa thể hiện.
6. Không thưởng điểm chỉ vì câu trả lời dài.
7. Không tự tạo trích dẫn.
8. Trả JSON đúng schema.

Question: {question}
Target dimensions: {target_dimensions}
Rubric: {rubric}
Student answer: {answer}
```

## 7. Kiểm tra tự động kết quả AI

Backend phải kiểm tra:

- Điểm nằm trong khoảng hợp lệ.
- Dimension thuộc danh sách cho phép.
- Mọi `evidence_quote` xuất hiện trong câu trả lời.
- `reason` không mâu thuẫn với điểm.
- Không xuất hiện kết luận nghề nghiệp, giới tính hoặc chẩn đoán tâm lý.
- Câu trả lời quá ngắn được đánh dấu `insufficient_answer`.

## 8. Quy trình xác minh bộ đề

### Tối thiểu cho hackathon

1. Lập bảng mapping từng câu với năng lực và tiêu chí.
2. Nhờ 2–3 người có chuyên môn review độc lập.
3. Thử với 20–30 học sinh/sinh viên để phát hiện câu khó hiểu.
4. Cho hai người chấm cùng một nhóm câu tự luận và so sánh.
5. Sửa câu phụ thuộc kiến thức chuyên ngành hoặc vùng miền.

### Sau hackathon

1. Pilot trên mẫu lớn hơn và đa dạng hơn.
2. Kiểm tra độ khó và khả năng phân biệt của item.
3. Kiểm tra độ tin cậy thang đo.
4. Kiểm tra cấu trúc nhân tố.
5. Kiểm tra liên hệ với bằng chứng ngoài bài kiểm tra.
6. Kiểm tra DIF và fairness giữa các nhóm.

## 9. Trạng thái hiển thị

Không dùng nhãn “yếu”. Dùng:

- Chưa được đánh giá.
- Chưa đủ dữ liệu.
- Có tín hiệu ban đầu.
- Bằng chứng tương đối rõ.
- Bằng chứng nhất quán.
- Kết quả chưa thống nhất.
- Nên thực hiện thêm task kiểm chứng.

