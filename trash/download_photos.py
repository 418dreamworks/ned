#!/usr/bin/env python3
"""Download all photos from a shared Google Photos album.

Downloads to a temp folder, then uses MD5 hashing to assign stable
permanent numbers. Known photos keep their number forever. New photos
get the next available number. Results saved to labeled/ folder.
"""

import hashlib
import json
import os
import re
import sys
import shutil
import tempfile
import urllib.request

ALBUM_URL = (
    "https://photos.google.com/share/AF1QipMW29i4_hrw9vZiW1k9ETjZ8BZM5_Bqk8wKZs8t13Zkto7gnWt6e5-Z3mlAoG8bFQ"
    "?key=TUlHU0RFSGVYLVVNUkVIa2QyRTNiTEVrZGtZV1ZB"
)

BASE = os.path.dirname(os.path.abspath(__file__))
TEMP_DIR = os.path.join(BASE, "photos")
LABELED_DIR = os.path.join(BASE, "labeled")
HASH_MAP_FILE = os.path.join(BASE, "labels", "hash_map.json")


def md5(filepath):
    h = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def fetch_page(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_image_urls(html: str) -> list[str]:
    urls = []
    for match in re.finditer(r'AF_initDataCallback\(\{[^}]*data:(\[.+?\])\s*\}\s*\)', html, re.DOTALL):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        _walk_for_urls(data, urls)

    if not urls:
        urls = list(set(re.findall(r'(https://lh3\.googleusercontent\.com/[A-Za-z0-9_\-/]+)', html)))

    return urls


def _walk_for_urls(obj, urls: list):
    if isinstance(obj, str):
        if "googleusercontent.com" in obj and obj.startswith("http"):
            if obj not in urls:
                urls.append(obj)
    elif isinstance(obj, list):
        for item in obj:
            _walk_for_urls(item, urls)


def download_image(url: str, dest: str, index: int) -> str:
    if "=w" not in url and "=s" not in url:
        dl_url = url + "=w0"
    else:
        dl_url = re.sub(r'=[wsh]\d+.*', '=w0', url)

    req = urllib.request.Request(dl_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        content_type = resp.headers.get("Content-Type", "")
        # Always save as .jpg for consistency
        ext = ".jpg"

        filename = f"temp_{index:03d}{ext}"
        filepath = os.path.join(dest, filename)
        data = resp.read()

    with open(filepath, "wb") as f:
        f.write(data)
    return filepath


def assign_stable_numbers(temp_dir, labeled_dir, hash_map_file):
    """Assign permanent numbers based on MD5 hash."""
    os.makedirs(labeled_dir, exist_ok=True)
    hash_map = load_json(hash_map_file)
    # hash_map: {md5: {filename, comment}}

    # Find the highest existing number
    existing_numbers = set()
    for entry in hash_map.values():
        m = re.search(r'(\d+)', entry.get("filename", ""))
        if m:
            existing_numbers.add(int(m.group(1)))
    next_num = max(existing_numbers, default=0) + 1

    # Hash all downloaded temp files
    temp_files = sorted(f for f in os.listdir(temp_dir) if f.startswith("temp_"))

    new_count = 0
    kept_count = 0
    seen_hashes = set()

    for temp_file in temp_files:
        temp_path = os.path.join(temp_dir, temp_file)
        h = md5(temp_path)

        if h in seen_hashes:
            # Duplicate in this download, skip
            os.remove(temp_path)
            continue
        seen_hashes.add(h)

        if h in hash_map:
            # Known photo — keep its permanent name
            perm_name = hash_map[h]["filename"]
            kept_count += 1
        else:
            # New photo — assign next number
            perm_name = f"photo_{next_num:03d}.jpg"
            hash_map[h] = {"filename": perm_name, "comment": ""}
            next_num += 1
            new_count += 1

        perm_path = os.path.join(labeled_dir, perm_name)
        shutil.copy2(temp_path, perm_path)
        os.remove(temp_path)

    # Check for photos in hash_map that weren't in this download (deleted from album)
    downloaded_hashes = seen_hashes
    deleted = []
    for h, entry in hash_map.items():
        if h not in downloaded_hashes:
            deleted.append(entry["filename"])

    save_json(hash_map_file, hash_map)

    return kept_count, new_count, deleted


def main():
    os.makedirs(TEMP_DIR, exist_ok=True)

    print(f"Fetching album page...")
    html = fetch_page(ALBUM_URL)

    print("Extracting image URLs...")
    urls = extract_image_urls(html)

    if not urls:
        print("No images found. The album may be empty or the page structure changed.")
        sys.exit(1)

    # Clean temp files
    for f in os.listdir(TEMP_DIR):
        if f.startswith("temp_"):
            os.remove(os.path.join(TEMP_DIR, f))

    print(f"Found {len(urls)} image(s). Downloading...")
    for i, url in enumerate(urls, 1):
        try:
            path = download_image(url, TEMP_DIR, i)
            print(f"  [{i}/{len(urls)}] downloaded")
        except Exception as e:
            print(f"  [{i}/{len(urls)}] FAILED: {e}")

    print("Assigning stable numbers...")
    kept, new, deleted = assign_stable_numbers(TEMP_DIR, LABELED_DIR, HASH_MAP_FILE)

    print(f"\n--- Summary ---")
    print(f"  Known photos: {kept}")
    print(f"  New photos: {new}")
    if deleted:
        print(f"  Deleted from album: {len(deleted)}")
        for d in deleted:
            print(f"    {d}")
    print("Done.")


if __name__ == "__main__":
    main()
