"""Quét bài đăng trong nhóm Facebook, trích số điện thoại và lưu vào SQLite/CSV.

Chạy:  python scraper.py            (quét + xuất CSV)
       python scraper.py --watch    (quét lặp liên tục, báo khi có bài mới khớp)
       python scraper.py --export   (chỉ xuất CSV)
"""
import hashlib
import random
import re
import sys
import time
from datetime import datetime, timedelta

import yaml
from playwright.sync_api import sync_playwright

from extract import find_phones, match_keywords
from notify import notify
from storage import Storage

# Facebook không còn dùng role="article" trong feed nhóm. Mỗi bài là 1 con trực tiếp của
# div[role="feed"], phần chữ nằm trong [data-ad-rendering-role="story_message"].
# Facebook ẩn link bài nên url thường rỗng (post_id lấy từ tác giả + nội dung).
JS_COLLECT = """
() => {
  const feed = document.querySelector('div[role="feed"]');
  if (!feed) return [];
  return [...feed.children].flatMap(post => {
    const msg = post.querySelector('[data-ad-rendering-role="story_message"]');
    if (!msg) return [];
    const author = post.querySelector('[data-ad-rendering-role="profile_name"]');
    const link = post.querySelector('a[href*="/posts/"], a[href*="/permalink/"], a[href*="story_fbid"]');
    return [{
      text: msg.innerText,
      url: link ? link.href : '',
      author: author ? author.innerText.split('\\n')[0].split('·')[0].trim() : '',
      head: post.innerText.slice(0, 400),
    }];
  });
}
"""

JS_EXPAND = """
() => {
  let n = 0;
  document.querySelectorAll('[data-ad-rendering-role="story_message"] [role="button"]').forEach(b => {
    if (/^(xem thêm|see more)$/i.test(b.innerText.trim())) { b.click(); n++; }
  });
  return n;
}
"""


_TIME_RE = re.compile(r"(\d{1,2}) Tháng (\d{1,2}), (\d{4}) lúc (\d{1,2}):(\d{2})")


def parse_time(head: str):
    """Giờ đăng bài từ phần đầu bài ('4 Tháng 11, 2026 lúc 11:53'); None nếu không đọc được."""
    m = _TIME_RE.search(head or "")
    if not m:
        return None
    d, mo, y, h, mi = map(int, m.groups())
    try:
        return datetime(y, mo, d, h, mi)
    except ValueError:
        return None


def clean_url(url: str) -> str:
    return re.sub(r"[?&](__cft__|__tn__|comment_id|notif_id)[^&]*", "", url).split("?")[0] if "/posts/" in url or "/permalink/" in url else url


def expand_see_more(page):
    if page.evaluate(JS_EXPAND):
        page.wait_for_timeout(800)


def scrape_group(page, group, cfg, store, on_new=None) -> int:
    page.goto(f"https://www.facebook.com/groups/{group}?sorting_setting=CHRONOLOGICAL", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    if "login" in page.url or "checkpoint" in page.url:
        sys.exit("Chưa đăng nhập hoặc bị checkpoint. Chạy lại login.py và kiểm tra tài khoản trên trình duyệt.")

    saved = 0
    lo, hi = cfg["delay_between_scrolls"]
    max_age = cfg.get("max_age_days")
    cutoff = datetime.now() - timedelta(days=max_age) if max_age else None
    for i in range(cfg["scroll_times"]):
        expand_see_more(page)
        times_seen = []  # giờ đăng của các bài đang hiện trên màn hình
        for item in page.evaluate(JS_COLLECT):
            posted = parse_time(item["head"])
            if posted:
                times_seen.append(posted)
            if cutoff and posted and posted < cutoff:
                continue  # bài cũ hơn mốc max_age_days
            text, url = re.sub(r"\s*(Ẩn bớt|See less)\s*$", "", item["text"]), clean_url(item["url"])
            if not text.strip():
                continue
            post_id = hashlib.md5((url or f"{item['author']}|{text[:200]}").encode()).hexdigest()
            if store.exists(post_id):
                continue
            phones = find_phones(text)
            kws = match_keywords(text, cfg["keywords"]) if cfg["keywords"] else []
            if cfg["require_phone"] and not phones:
                continue
            if cfg["keywords"] and not kws:
                continue
            row = {
                "post_id": post_id, "group_id": group, "author": item["author"],
                "phones": ",".join(phones), "keywords": ",".join(kws),
                "content": text.strip(), "url": url,
                "posted_at": posted.strftime("%Y-%m-%d %H:%M") if posted else "",
            }
            store.save(row)
            saved += 1
            fresh = posted is None or posted > datetime.now() - timedelta(hours=cfg.get("notify_within_hours", 3))
            if on_new and fresh:
                try:
                    on_new(row)
                except Exception as e:  # lỗi thông báo không được làm sập vòng quét
                    print(f"  ! lỗi thông báo: {e}")
            print(f"  + {item['author'] or '?'} | {','.join(phones) or '-'} | {posted or '?'}")
        if cutoff and times_seen and all(t < cutoff for t in times_seen):
            print(f"  (đã tới bài cũ hơn {max_age} ngày, dừng)")
            break
        if cutoff and i == cfg["scroll_times"] - 1:
            print(f"  (hết {cfg['scroll_times']} lần cuộn mà chưa tới mốc {max_age} ngày, tăng scroll_times nếu muốn quét sâu hơn)")
        page.mouse.wheel(0, random.randint(2500, 4000))
        time.sleep(random.uniform(lo, hi))
    return saved


def main():
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    store = Storage()
    if "--export" in sys.argv:
        print(f"Đã xuất {store.export_csv()} dòng -> data/posts.csv")
        return

    watch = "--watch" in sys.argv
    on_new = (lambda row: notify(row, cfg)) if watch else None
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context("profile", headless=cfg["headless"], locale="vi-VN")
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        while True:
            for g in cfg["groups"]:
                print(f"[{datetime.now():%H:%M:%S}] Nhóm {g}")
                n = scrape_group(page, g, cfg, store, on_new)
                print(f"  -> {n} bài mới")
                time.sleep(random.uniform(*cfg["delay_between_groups"]))
            store.export_csv()
            if not watch:
                break
            wait = cfg.get("watch_interval_minutes", 15)
            print(f"Xong một vòng, nghỉ {wait} phút...")
            time.sleep(wait * 60)
        ctx.close()
    print(f"Đã xuất {store.export_csv()} dòng -> data/posts.csv")


if __name__ == "__main__":
    main()
