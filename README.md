# Career Compass

He thong goi y nghe nghiep va lo trinh hoc tap ca nhan hoa cho hoc sinh, dua tren du lieu tuyen dung that.

## So do tong quan

```
career-compass/
├── docs/              # ke hoach + schema da chot, doc truoc khi code
├── crawl-service/      # crawl du lieu tuyen dung that, chay doc lap, ghi thang DB
├── profile-service/    # hoi hoc sinh (adaptive), tong hop the manh, co API rieng
├── core/                # nhan du lieu tu 2 service tren, chay matching/bias-check/roadmap
├── frontend/            # giao dien, goi profile-service luc lam form, goi core luc xem ket qua
└── tests/               # test cho tung phan
```

## Y nghia tung phan

**`docs/`** — tai lieu ke hoach da chot (`career-compass-notes.md`) va schema database (`career-compass-schema-draft.md`). Doc 2 file nay truoc khi dong code vao bat ky service nao.

**`crawl-service/`** — thu thap job posting that tu ITviec/TopCV/Vieclam24h, lam sach, trich xuat skill/nganh/luong/vung (hybrid rule + LLM fallback), tong hop thanh demand summary. Chay job doc lap (tay/cron), ghi thang vao Postgres, khong expose API cho ai goi.

**`profile-service/`** — hoi hoc sinh theo kieu adaptive: cau hoi co dinh ban dau, tong hop the manh so bo, roi chon tiep cau hoi sau hon tu kho de (`question_bank/`). Co API rieng (`router.py`) de frontend goi thang luc lam form.

**`core/`** — bo xu ly trung tam. Gom:
- `session/` — quan ly anonymous session (khong dang nhap, khong tai khoan)
- `shared/` — schema va taxonomy dung noi bo trong core, phai khop voi 2 service kia theo hop dong API
- `data/` — chi DOC demand summary do crawl-service da ghi san
- `ai/` — matching, skill-gap, bias-check, sinh roadmap, tong hop ket qua giai thich duoc

**`frontend/`** — giao dien nguoi dung. Goi thang `profile-service` luc lam form (can phan hoi nhanh), goi `core` luc can ket qua goi y va roadmap.

**`tests/`** — test cho extraction, matching, bias policy, va test end-to-end xuyen suot 3 service.

## Chay du an

```
docker compose up
```

- core: http://localhost:8000
- profile-service: http://localhost:8001
- frontend: chay rieng bang `npm run dev` trong `frontend/`
