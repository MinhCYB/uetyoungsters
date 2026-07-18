# Demo fixtures

`demo_profile.json` là dữ liệu giả phục vụ phát triển và trình diễn.

- Không được import tự động vào `frontend/src/main.jsx`.
- Không được seed vào PostgreSQL production.
- Người dùng thật vẫn bắt đầu với hồ sơ, phân tích AI, nghề gợi ý và lộ trình ở trạng thái trống.
- Mở `http://localhost:3000/?demo=1` để nạp fixture vào session trình duyệt và chuyển đến hồ sơ demo.
- Mở URL bình thường không tự nạp demo; nút “Làm lại từ đầu” xóa session demo như một session thông thường.
