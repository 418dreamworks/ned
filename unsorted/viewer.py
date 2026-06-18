#!/usr/bin/env python3
"""Photo viewer with comment boxes for labelling components.

Run:  python3 viewer.py
Open:  http://localhost:8080

Shows all photos in photos/ as a grid. Each photo has a text box
for comments. Comments are saved to labels/comments.json and can
be read by Claude.
"""

import http.server
import os
import json
import urllib.parse

PORT = 8080
PHOTOS_DIR = "labeled"
LABELS_DATA = "labels/data.json"
COMMENTS_FILE = "labels/comments.json"


def get_photos():
    exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    photos = []
    for f in sorted(os.listdir(PHOTOS_DIR)):
        if os.path.splitext(f)[1].lower() in exts:
            photos.append(f)
    return photos


def load_comments():
    if os.path.exists(COMMENTS_FILE):
        with open(COMMENTS_FILE) as f:
            return json.load(f)
    return {}


def save_comments(comments):
    os.makedirs(os.path.dirname(COMMENTS_FILE), exist_ok=True)
    with open(COMMENTS_FILE, "w") as f:
        json.dump(comments, f, indent=2)


def build_html():
    photos = get_photos()
    comments = load_comments()

    labels = {}
    if os.path.exists(LABELS_DATA):
        with open(LABELS_DATA) as f:
            labels = json.load(f)

    cards = ""
    for i, photo in enumerate(photos, 1):
        name = os.path.splitext(photo)[0]
        # Extract number from filename (e.g. "photo_042" -> "042")
        import re
        num_match = re.search(r'(\d+)', name)
        display_num = num_match.group(1) if num_match else str(i)
        comment = comments.get(photo, "")
        comment_escaped = comment.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

        label_info = ""
        if name in labels:
            info = labels[name]
            label_info = "<br>".join(f"<b>{k}:</b> {v}" for k, v in info.items() if k != "raw")
            label_info = f'<div class="label-info">{label_info}</div>'

        saved_indicator = ' class="saved"' if comment else ""

        cards += f"""
        <div class="card" id="photo-{display_num}">
            <div class="photo-num">#{display_num}</div>
            <img src="/labeled/{photo}" loading="lazy" onclick="this.classList.toggle('zoomed')" />
            <div class="caption">{photo}</div>
            {label_info}
            <div class="comment-box">
                <textarea id="comment-{i}" data-photo="{photo}" placeholder="Describe this component..."
                    onfocus="this.rows=4" onblur="if(!this.value)this.rows=2"
                    rows="2">{comment_escaped}</textarea>
                <button onclick="saveComment({i})" id="btn-{i}"{saved_indicator}>Save</button>
            </div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
<title>MotionMaster Component Photos</title>
<style>
    body {{
        font-family: -apple-system, sans-serif;
        background: #1a1a1a;
        color: #eee;
        margin: 0;
        padding: 20px;
    }}
    h1 {{ text-align: center; color: #fff; margin-bottom: 10px; }}
    .info {{ text-align: center; color: #888; margin-bottom: 20px; }}
    .grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
        gap: 16px;
        max-width: 1800px;
        margin: 0 auto;
    }}
    .card {{
        background: #2a2a2a;
        border-radius: 8px;
        overflow: hidden;
        position: relative;
    }}
    .card img {{
        width: 100%;
        display: block;
        cursor: zoom-in;
    }}
    .card img.zoomed {{
        cursor: zoom-out;
        position: fixed;
        top: 0; left: 0;
        width: 100vw; height: 100vh;
        object-fit: contain;
        z-index: 1000;
        background: rgba(0,0,0,0.95);
        border-radius: 0;
    }}
    .photo-num {{
        position: absolute;
        top: 8px; left: 8px;
        background: rgba(255,50,50,0.85);
        color: white; font-weight: bold; font-size: 18px;
        padding: 4px 10px; border-radius: 4px; z-index: 10;
    }}
    .caption {{ padding: 8px 12px; font-size: 13px; color: #aaa; }}
    .label-info {{ padding: 4px 12px 8px; font-size: 12px; color: #8f8; line-height: 1.6; }}
    .comment-box {{ padding: 8px 12px 12px; display: flex; gap: 8px; }}
    .comment-box textarea {{
        flex: 1;
        background: #1a1a1a;
        border: 1px solid #444;
        border-radius: 4px;
        color: #eee;
        padding: 8px;
        font-family: inherit;
        font-size: 13px;
        resize: vertical;
    }}
    .comment-box textarea:focus {{ border-color: #6af; outline: none; }}
    .comment-box button {{
        background: #444;
        border: none;
        color: #eee;
        padding: 8px 16px;
        border-radius: 4px;
        cursor: pointer;
        font-size: 13px;
        align-self: flex-end;
    }}
    .comment-box button:hover {{ background: #555; }}
    .comment-box button.saved {{ background: #2a5a2a; }}
    .toast {{
        position: fixed;
        bottom: 20px; right: 20px;
        background: #2a5a2a;
        color: #fff;
        padding: 12px 24px;
        border-radius: 8px;
        font-size: 14px;
        opacity: 0;
        transition: opacity 0.3s;
        z-index: 2000;
    }}
    .toast.show {{ opacity: 1; }}
</style>
</head>
<body>
    <h1>MotionMaster Component Photos</h1>
    <div class="info">{len(photos)} photos | Click photo to zoom | Add comments below each photo | Claude reads labels/comments.json</div>
    <div class="grid">
        {cards}
    </div>
    <div class="toast" id="toast">Saved!</div>
    <script>
    function saveComment(num) {{
        const ta = document.getElementById('comment-' + num);
        const photo = ta.dataset.photo;
        const comment = ta.value;
        const btn = document.getElementById('btn-' + num);

        fetch('/save_comment', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{photo: photo, comment: comment}})
        }}).then(r => r.json()).then(data => {{
            if (data.ok) {{
                btn.className = comment ? 'saved' : '';
                const toast = document.getElementById('toast');
                toast.textContent = 'Saved #' + num + '!';
                toast.classList.add('show');
                setTimeout(() => toast.classList.remove('show'), 1500);
            }}
        }});
    }}

    // Ctrl+Enter to save from textarea
    document.addEventListener('keydown', function(e) {{
        if (e.ctrlKey && e.key === 'Enter' && e.target.tagName === 'TEXTAREA') {{
            const num = e.target.id.split('-')[1];
            saveComment(parseInt(num));
        }}
    }});
    </script>
</body>
</html>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            html = build_html()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html.encode())
        elif self.path.startswith("/labeled/") or self.path.startswith("/photos/"):
            filepath = os.path.join(".", self.path.lstrip("/"))
            if os.path.exists(filepath):
                self.send_response(200)
                ext = os.path.splitext(filepath)[1].lower()
                ct = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                      ".png": "image/png", ".gif": "image/gif",
                      ".webp": "image/webp"}.get(ext, "application/octet-stream")
                self.send_header("Content-Type", ct)
                self.end_headers()
                with open(filepath, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/save_comment":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            data = json.loads(body)

            comments = load_comments()
            if data["comment"].strip():
                comments[data["photo"]] = data["comment"].strip()
            else:
                comments.pop(data["photo"], None)
            save_comments(comments)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    print(f"Serving at http://localhost:{PORT}")
    print("Press Ctrl+C to stop")
    server = http.server.HTTPServer(("", PORT), Handler)
    server.serve_forever()
