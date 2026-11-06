"""Báo cho người dùng khi có bài mới khớp (có sđt + từ khóa). Người dùng tự nhắn tin."""
import json
import os
import subprocess
import sys
import urllib.request


def build_text(row: dict, cfg: dict) -> str:
    phones = [p for p in row["phones"].split(",") if p]
    greeting = cfg.get("message_template", "Chào {author}, mình thấy bài bạn đăng. ").format(
        author=row["author"] or "bạn", keywords=row["keywords"])
    lines = [
        f"Bài mới: {row['author'] or '?'} ({row['posted_at'] or 'không rõ giờ'})",
        row["content"][:300],
        *(f"Zalo: https://zalo.me/{p}" for p in phones),
        f"Tin mẫu: {greeting}",
    ]
    return "\n".join(lines)


def _mac_notification(title: str, body: str) -> None:
    if sys.platform != "darwin":
        return  # chỉ có trên macOS; Windows/Linux dùng Telegram
    body, title = body.replace('"', "'"), title.replace('"', "'")
    subprocess.run(["osascript", "-e", f'display notification "{body[:200]}" with title "{title}"'], check=False)


def _telegram(method: str, payload: dict) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("chưa đặt biến môi trường TELEGRAM_BOT_TOKEN")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def send_telegram(row: dict, cfg: dict) -> None:
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        raise RuntimeError("chưa đặt biến môi trường TELEGRAM_CHAT_ID")
    phones = [p for p in row["phones"].split(",") if p]
    _telegram("sendMessage", {
        "chat_id": chat_id,
        "text": build_text(row, cfg),
        "disable_web_page_preview": True,
        "reply_markup": {"inline_keyboard": [[{"text": f"Mở Zalo {p}", "url": f"https://zalo.me/{p}"}] for p in phones]},
    })


def notify(row: dict, cfg: dict) -> None:
    text = build_text(row, cfg)
    print("  >> THÔNG BÁO\n" + "\n".join("     " + l for l in text.splitlines()))
    _mac_notification("Bài mới khớp từ khóa", f"{row['author']}: {row['phones']}")
    if os.environ.get("TELEGRAM_BOT_TOKEN"):
        send_telegram(row, cfg)


if __name__ == "__main__" and "--setup" in sys.argv:
    # Lấy chat_id: nhắn bot 1 tin bất kỳ trên Telegram rồi chạy `python notify.py --setup`
    for u in _telegram("getUpdates", {}).get("result", []):
        chat = (u.get("message") or {}).get("chat")
        if chat:
            print("TELEGRAM_CHAT_ID =", chat["id"], f"({chat.get('first_name', '')})")
            break
    else:
        print("Chưa thấy tin nào. Hãy nhắn cho bot 1 tin bất kỳ rồi chạy lại.")
