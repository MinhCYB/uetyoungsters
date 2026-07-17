# Career Intelligence Baseline

Baseline end-to-end cho hệ thống định hướng nghề nghiệp dựa trên:

1. Tín hiệu kỹ năng từ tin tuyển dụng.
2. Hồ sơ kỹ năng và sở thích của người học.
3. Xếp hạng nhiều hướng nghề nghiệp có giải thích.
4. Guardrail không dùng thuộc tính nhạy cảm để đánh giá năng lực.

## Baseline này làm được gì?

- Đọc dữ liệu tuyển dụng từ CSV.
- Trích xuất kỹ năng bằng taxonomy và alias.
- Tổng hợp số tin và lương theo kỹ năng, khu vực.
- Nhận hồ sơ kỹ năng, sở thích và khu vực của người dùng.
- Đề xuất top nghề cùng kỹ năng thiếu và lộ trình tham khảo.
- Loại các thuộc tính nhạy cảm khỏi mô hình đề xuất.
- Có test counterfactual cơ bản cho giới tính.

## Chạy dự án

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

Chạy test:

```bash
pytest
```

## Kiến trúc baseline

```text
jobs.csv
   ↓
cleaning + skill taxonomy extraction
   ↓
market signals
   ↓
                       student profile
                            ↓
                multi-factor ranking baseline
                            ↓
             top careers + missing skills + route
```

## Công thức baseline

```text
score =
    0.45 × skill overlap
  + 0.30 × activity/interests match
  + 0.25 × local market signal
```

Điểm số chỉ dùng để xếp hạng hướng khám phá, không phải xác suất người dùng
thành công trong nghề.

## Hạn chế hiện tại

- Dữ liệu mẫu rất nhỏ.
- Trích xuất kỹ năng đang dùng rule-based taxonomy.
- Chưa có chống trùng tin tuyển dụng.
- Chưa có mô hình xu hướng theo thời gian.
- Chưa có hội thoại thích ứng hoặc micro-task.
- Chưa có knowledge graph nghề–kỹ năng–khóa học.
- Chưa đánh giá fairness trên dữ liệu thật.

## Nâng cấp tiếp theo

1. Thêm bộ dữ liệu tuyển dụng thật và gán nhãn 300–500 tin để benchmark.
2. Thêm deduplication bằng fingerprint + embedding.
3. Chuẩn hóa chức danh nghề nghiệp.
4. Kết hợp rule extraction với mô hình NER/LLM structured output.
5. Xây student profile theo evidence và micro-task.
6. Thêm diversification để mở rộng lựa chọn.
7. Tạo source logging cho mọi số liệu và giải thích.
