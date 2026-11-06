"""Chạy 1 lần: mở trình duyệt để bạn tự đăng nhập Facebook. Session lưu trong ./profile."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context("profile", headless=False, locale="vi-VN")
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://www.facebook.com/")
    input("Đăng nhập xong (kể cả 2FA) thì quay lại đây bấm Enter...")
    ctx.close()
