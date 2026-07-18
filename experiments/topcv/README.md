# TopCV collector experiments

Các collector trong thư mục này chỉ là bằng chứng nghiên cứu nguồn, không thuộc luồng production.

- HTTP collector từng nhận HTTP 403.
- Listing collector gặp access challenge.
- Playwright collector phải dừng khi gặp CAPTCHA, challenge, HTTP 403 hoặc HTTP 429.

TopCV đang bị vô hiệu hóa trong `config/sources.yaml` cho tới khi có phương thức thu thập ổn định và được phép.
