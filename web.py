"""Trang web nội bộ (chỉ mở trên máy này): danh sách bài khớp, bấm mở Zalo / copy tin mẫu / đánh dấu đã nhắn.

Chạy:  python web.py   rồi mở http://127.0.0.1:8000
"""
import json
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml

from storage import Storage

PORT = 8000
PAGE = """<!doctype html><meta charset="utf-8"><title>Bài cần liên hệ</title>
<style>
 body{font:15px system-ui;max-width:820px;margin:20px auto;padding:0 12px;background:#f5f6f8}
 h1{font-size:20px} .bar{position:sticky;top:0;background:#f5f6f8;padding:8px 0;font-weight:600}
 .card{background:#fff;border-radius:8px;padding:12px;margin:10px 0;box-shadow:0 1px 2px #0002}
 .meta{color:#666;font-size:13px} .txt{white-space:pre-wrap;margin:8px 0;max-height:7.5em;overflow:auto}
 button,a.btn{font:inherit;padding:6px 12px;margin:2px 4px 2px 0;border:0;border-radius:6px;background:#0068ff;color:#fff;cursor:pointer;text-decoration:none;display:inline-block}
 button.sec{background:#e4e6eb;color:#222}
</style>
<h1>Bài cần liên hệ</h1><div class="bar" id="bar"></div><div id="list"></div>
<script>
const LIMIT = __LIMIT__, TEMPLATE = __TEMPLATE__;
async function load(){
  const d = await (await fetch('/api/leads')).json();
  document.getElementById('bar').textContent = `Hôm nay đã nhắn: ${d.today}/${LIMIT} · Còn ${d.leads.length} bài chưa xử lý`;
  const list = document.getElementById('list'); list.replaceChildren();
  for (const p of d.leads){
    const c = document.createElement('div'); c.className='card';
    const meta = document.createElement('div'); meta.className='meta';
    meta.textContent = `${p.author||'?'} · ${p.posted_at||'không rõ giờ'} · ${p.keywords||''}`;
    const txt = document.createElement('div'); txt.className='txt'; txt.textContent = p.content;
    c.append(meta, txt);
    for (const ph of p.phones.split(',')){
      const a = document.createElement('a'); a.className='btn'; a.target='_blank'; a.rel='noopener';
      a.href = 'https://zalo.me/'+ph; a.textContent = 'Mở Zalo '+ph; c.append(a);
    }
    const cp = document.createElement('button'); cp.className='sec'; cp.textContent='Copy tin mẫu';
    cp.onclick = async()=>{ await navigator.clipboard.writeText(TEMPLATE.replace('{author}', p.author||'bạn').replace('{keywords}', p.keywords||'')); cp.textContent='Đã copy'; };
    const done = document.createElement('button'); done.textContent='Đã nhắn'; done.onclick=()=>mark(p.post_id,false);
    const skip = document.createElement('button'); skip.className='sec'; skip.textContent='Bỏ qua'; skip.onclick=()=>mark(p.post_id,true);
    c.append(cp, done, skip); list.append(c);
  }
}
async function mark(id, skip){ await fetch('/api/mark',{method:'POST',body:JSON.stringify({id,skip})}); load(); }
load(); setInterval(load, 60000);
</script>"""


def make_handler(cfg):
    page = (PAGE.replace("__LIMIT__", str(cfg.get("daily_limit", 100)))
                .replace("__TEMPLATE__", json.dumps(cfg.get("message_template", ""), ensure_ascii=False)))
    local = threading.local()

    def store():  # sqlite connection phải tạo riêng cho từng luồng
        if not hasattr(local, "s"):
            local.s = Storage()
        return local.s

    class H(BaseHTTPRequestHandler):
        def _send(self, code, body, ctype):
            data = body.encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                self._send(200, page, "text/html")
            elif self.path == "/api/leads":
                s = store()
                self._send(200, json.dumps({"leads": s.pending(), "today": s.contacted_today()}, ensure_ascii=False), "application/json")
            else:
                self._send(404, "not found", "text/plain")

        def do_POST(self):
            if self.path != "/api/mark" or self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
                return self._send(403, "forbidden", "text/plain")
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            store().mark(str(body.get("id", "")), bool(body.get("skip")))
            self._send(200, "{}", "application/json")

        def log_message(self, *a):
            pass

    return H


if __name__ == "__main__":
    cfg = yaml.safe_load(open("config.yaml", encoding="utf-8"))
    print(f"Mở http://127.0.0.1:{PORT}  (Ctrl+C để dừng)")
    ThreadingHTTPServer(("127.0.0.1", PORT), make_handler(cfg)).serve_forever()
