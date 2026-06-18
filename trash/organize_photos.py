#!/usr/bin/env python3
"""Organize commented photos into labeled/ folder using MD5 matching.

After re-downloading photos from the album, run this to:
1. Match new photos to existing labeled ones by MD5 hash
2. Move any newly commented photos into labeled/
3. Flag new/unrecognized photos

The labeled/ folder is the source of truth for commented photos.
photos/ is ephemeral — re-downloaded each time from the album.
"""

import hashlib
import json
import os
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))
PHOTOS_DIR = os.path.join(BASE, "photos")
LABELED_DIR = os.path.join(BASE, "labeled")
COMMENTS_FILE = os.path.join(BASE, "labels", "comments.json")
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


def hash_all_photos():
    """Return {filename: md5} for all photos in photos/."""
    result = {}
    exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    for f in sorted(os.listdir(PHOTOS_DIR)):
        if os.path.splitext(f)[1].lower() in exts:
            result[f] = md5(os.path.join(PHOTOS_DIR, f))
    return result


def hash_labeled_photos():
    """Return {md5: filename} for all photos in labeled/."""
    result = {}
    if not os.path.isdir(LABELED_DIR):
        return result
    exts = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    for f in sorted(os.listdir(LABELED_DIR)):
        if os.path.splitext(f)[1].lower() in exts:
            result[md5(os.path.join(LABELED_DIR, f))] = f
    return result


def organize():
    os.makedirs(LABELED_DIR, exist_ok=True)

    comments = load_json(COMMENTS_FILE)
    hash_map = load_json(HASH_MAP_FILE)
    # hash_map: {md5: {filename, comment}} — the canonical mapping

    # Hash everything currently in photos/
    photo_hashes = hash_all_photos()  # {filename: md5}
    reverse_photo = {v: k for k, v in photo_hashes.items()}  # {md5: filename}

    # Hash everything currently in labeled/
    labeled_hashes = hash_labeled_photos()  # {md5: filename}

    # Step 1: For each comment, find the photo by old filename, get its hash,
    # and move it to labeled/ if not already there
    moved = 0
    updated_comments = {}
    for old_filename, comment in comments.items():
        if not comment or not comment.strip():
            continue
        if comment.strip() == "Delete this.":
            # Skip deleted photos
            continue

        # Find this photo's hash — check photos/ first
        src = os.path.join(PHOTOS_DIR, old_filename)
        if os.path.exists(src):
            h = md5(src)
        elif old_filename in {v for v in labeled_hashes.values()}:
            # Already in labeled/ by this name
            h = next(k for k, v in labeled_hashes.items() if v == old_filename)
        else:
            print(f"  WARN: {old_filename} not found in photos/ or labeled/, skipping")
            continue

        # Determine target name in labeled/
        if h in labeled_hashes:
            # Already labeled under some name
            target_name = labeled_hashes[h]
        elif h in hash_map:
            target_name = hash_map[h]["filename"]
        else:
            target_name = old_filename

        target = os.path.join(LABELED_DIR, target_name)
        if not os.path.exists(target):
            shutil.copy2(src, target)
            moved += 1
            print(f"  Moved {old_filename} -> labeled/{target_name}")

        # Update hash_map
        hash_map[h] = {"filename": target_name, "comment": comment.strip()}
        updated_comments[target_name] = comment.strip()

    # Step 2: Check for photos in photos/ that are NOT in labeled/
    new_photos = []
    for filename, h in photo_hashes.items():
        if h not in hash_map:
            new_photos.append(filename)

    # Step 3: Rebuild comments.json keyed by labeled/ filenames
    save_json(COMMENTS_FILE, updated_comments)
    save_json(HASH_MAP_FILE, hash_map)

    # Report
    print(f"\n--- Summary ---")
    print(f"  Labeled photos: {len(updated_comments)}")
    print(f"  Newly moved: {moved}")
    print(f"  New/unlabeled photos in photos/: {len(new_photos)}")
    if new_photos:
        print(f"  Unlabeled: {', '.join(new_photos)}")

    return new_photos


if __name__ == "__main__":
    os.chdir(BASE)
    organize()
