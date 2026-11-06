# fb_group_scraper

Quét bài đăng trong các nhóm Facebook, lọc theo từ khóa, trích số điện thoại Việt Nam, lưu vào SQLite và xuất CSV.

## Cách hoạt động

1. Mở Chromium (Playwright) bằng profile đã đăng nhập sẵn trong `profile/`.
2. Vào từng nhóm trong `config.yaml` (sắp xếp bài mới nhất), cuộn trang `scroll_times` lần.
3. Mỗi lần cuộn: bấm "Xem thêm", lấy các bài viết, trích số điện thoại, lọc theo từ khóa.
4. Bài mới (chưa có trong DB) được lưu vào `data/posts.db`, cuối cùng xuất ra `data/posts.csv`.

## Cài đặt (làm 1 lần)

```bash
cd ~/fb_group_scraper
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## Chạy

### Bước 1: Đăng nhập Facebook
```bash
python login.py
```
Trình duyệt mở ra, bạn tự đăng nhập (kể cả 2FA), xong quay lại terminal bấm Enter. Session lưu trong `profile/`, chỉ cần làm lại khi bị đăng xuất.

### Bước 2: Cấu hình `config.yaml`

| Khóa | Ý nghĩa |
|---|---|
| `groups` | Danh sách ID hoặc slug nhóm (phần sau `facebook.com/groups/`) |
| `keywords` | Chỉ giữ bài chứa ít nhất 1 từ khóa (không phân biệt hoa/thường). `[]` = lấy mọi bài |
| `require_phone` | `true` = chỉ lưu bài có số điện thoại |
| `scroll_times` | Số lần cuộn mỗi nhóm (càng nhiều càng quét sâu) |
| `delay_between_scrolls` | Khoảng nghỉ ngẫu nhiên giữa các lần cuộn (giây) |
| `delay_between_groups` | Khoảng nghỉ ngẫu nhiên giữa các nhóm (giây) |
| `headless` | `true` = chạy ẩn trình duyệt. Nên để `false` cho đỡ bị phát hiện |

Ví dụ:
```yaml
groups:
  - "123456789012345"
  - "ten-slug-cua-nhom"
keywords:
  - "cần mua"
  - "tìm mua"
require_phone: true
```

### Bước 3: Quét
```bash
python scraper.py            # quét + xuất CSV
python scraper.py --export   # chỉ xuất lại CSV từ DB, không quét
```

Mỗi bài mới lưu được sẽ in ra một dòng: `+ tác giả | số điện thoại | link bài`.

## Kết quả

- `data/posts.db`: SQLite, bảng `posts` (`post_id`, `group_id`, `author`, `phones`, `keywords`, `content`, `url`, `scraped_at`).
- `data/posts.csv`: cùng dữ liệu, mã hóa UTF-8 có BOM nên mở bằng Excel không lỗi tiếng Việt.
- Chạy lại nhiều lần không bị trùng: bài đã có trong DB sẽ bị bỏ qua (khóa theo hash của link bài).

## Cấu trúc file

| File | Vai trò |
|---|---|
| `login.py` | Đăng nhập thủ công, lưu session |
| `scraper.py` | Vòng quét chính, lọc bài |
| `extract.py` | Trích và chuẩn hóa số điện thoại VN (`0xxx`, `+84xxx`, `84xxx`), khớp từ khóa |
| `storage.py` | SQLite + xuất CSV |
| `config.yaml` | Cấu hình |

## Xử lý sự cố

- **"Chưa đăng nhập hoặc bị checkpoint"**: chạy lại `python login.py`, mở Facebook xem tài khoản có bị yêu cầu xác minh không.
- **Không ra bài nào**: kiểm tra tài khoản đã là thành viên nhóm chưa; thử đặt `require_phone: false` và `keywords: []` để xem có lấy được bài không. Nếu vẫn không, Facebook có thể đã đổi giao diện, cần sửa selector `JS_COLLECT` trong `scraper.py`.
- **Muốn quét lại từ đầu**: xóa `data/posts.db`.

## Lưu ý

- Chỉ quét được nhóm mà tài khoản là thành viên.
- Facebook cấm scrape tự động: nên dùng tài khoản phụ, ít nhóm, giữ delay, không chạy quá dày.
- Số điện thoại là dữ liệu cá nhân (NĐ 13/2023): chỉ liên hệ người chủ động đăng nhu cầu.
