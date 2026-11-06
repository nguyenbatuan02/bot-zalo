import csv
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    post_id TEXT PRIMARY KEY,
    group_id TEXT,
    author TEXT,
    phones TEXT,
    keywords TEXT,
    content TEXT,
    url TEXT,
    posted_at TEXT,
    scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
)
"""
COLS = ["post_id", "group_id", "author", "phones", "keywords", "content", "url", "posted_at", "scraped_at"]


class Storage:
    def __init__(self, path="data/posts.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(SCHEMA)
        if "posted_at" not in [r[1] for r in self.db.execute("PRAGMA table_info(posts)")]:
            self.db.execute("ALTER TABLE posts ADD COLUMN posted_at TEXT")  # DB tạo từ bản cũ
        if "contacted_at" not in [r[1] for r in self.db.execute("PRAGMA table_info(posts)")]:
            self.db.execute("ALTER TABLE posts ADD COLUMN contacted_at TEXT")  # NULL = chưa nhắn; 'skip' = bỏ qua

    def exists(self, post_id: str) -> bool:
        return self.db.execute("SELECT 1 FROM posts WHERE post_id=?", (post_id,)).fetchone() is not None

    def save(self, row: dict) -> None:
        self.db.execute(
            "INSERT OR IGNORE INTO posts (post_id, group_id, author, phones, keywords, content, url, posted_at) "
            "VALUES (:post_id, :group_id, :author, :phones, :keywords, :content, :url, :posted_at)",
            row,
        )
        self.db.commit()

    def pending(self, limit=200) -> list:
        cur = self.db.execute(
            "SELECT post_id, author, phones, keywords, content, posted_at FROM posts "
            "WHERE phones != '' AND contacted_at IS NULL ORDER BY posted_at DESC, scraped_at DESC LIMIT ?", (limit,))
        return [dict(zip([c[0] for c in cur.description], r)) for r in cur.fetchall()]

    def mark(self, post_id: str, skip: bool = False) -> None:
        self.db.execute("UPDATE posts SET contacted_at=? WHERE post_id=?",
                        ("skip" if skip else __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M"), post_id))
        self.db.commit()

    def contacted_today(self) -> int:
        return self.db.execute("SELECT COUNT(*) FROM posts WHERE contacted_at LIKE date('now','localtime')||'%'").fetchone()[0]

    def export_csv(self, path="data/posts.csv") -> int:
        rows = self.db.execute(f"SELECT {','.join(COLS)} FROM posts ORDER BY posted_at DESC, scraped_at DESC").fetchall()
        with open(path, "w", newline="", encoding="utf-8-sig") as f:  # utf-8-sig để Excel đọc đúng tiếng Việt
            w = csv.writer(f)
            w.writerow(COLS)
            w.writerows(rows)
        return len(rows)
