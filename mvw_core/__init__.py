"""Shared storage layer for motion-videos-warehouse.

Single source of truth for the on-disk layout:

    <warehouse>/<source>/<item_id>/
        meta.json        # metadata, see Item.meta
        prompt.txt       # generation prompt (if known)
        original.mp4     # main video
        remake.mp4       # extra video (if source has one)
        poster.webp|jpg  # preview image

The warehouse root is $MVW_DATA, or ../warehouse next to the repos.
"""
import hashlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path

SCHEMA = 1
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"


def warehouse_root():
    env = os.environ.get("MVW_DATA")
    if env:
        return Path(env).expanduser().resolve()
    # <workspace>/mvw-core/mvw_core/__init__.py -> <workspace>/warehouse
    return Path(__file__).resolve().parents[2] / "warehouse"


def fetch(url, retries=3, timeout=60):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:  # network errors are retried, then re-raised
            last = e
            time.sleep(1 + i * 2)
    raise last


def fetch_text(url, **kw):
    return fetch(url, **kw).decode("utf-8", "replace")


def safe_id(s):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", s).strip("-")[:120]


class Item:
    def __init__(self, source, item_id, root=None):
        self.source = source
        self.id = safe_id(item_id)
        self.dir = (root or warehouse_root()) / source / self.id
        self.meta_path = self.dir / "meta.json"
        self.meta = {}
        if self.meta_path.exists():
            self.meta = json.loads(self.meta_path.read_text())

    @property
    def is_new(self):
        return not self.meta_path.exists()

    def has(self, name):
        p = self.dir / name
        return p.exists() and p.stat().st_size > 0

    def save_text(self, name, text):
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / name).write_text(text, encoding="utf-8")
        self.meta.setdefault("files", {})[name] = {"bytes": len(text.encode())}

    def download(self, name, url):
        """Idempotent: skips if file already present. Atomic via .part."""
        if self.has(name):
            return False
        self.dir.mkdir(parents=True, exist_ok=True)
        data = fetch(url)
        tmp = self.dir / (name + ".part")
        tmp.write_bytes(data)
        tmp.replace(self.dir / name)
        self.meta.setdefault("files", {})[name] = {
            "url": url,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        return True

    def save_meta(self, **fields):
        self.dir.mkdir(parents=True, exist_ok=True)
        self.meta.update({k: v for k, v in fields.items() if v is not None})
        self.meta.update(schema=SCHEMA, source=self.source, id=self.id)
        self.meta.setdefault("first_seen", time.strftime("%Y-%m-%dT%H:%M:%S%z"))
        self.meta["last_seen"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        self.meta_path.write_text(json.dumps(self.meta, ensure_ascii=False, indent=2))


def iter_items(root=None):
    root = root or warehouse_root()
    for meta in sorted(root.glob("*/*/meta.json")):
        try:
            yield json.loads(meta.read_text())
        except Exception:
            continue


def cli_args(description):
    import argparse

    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--limit", type=int, default=0, help="max items (0 = all)")
    ap.add_argument("--no-media", action="store_true", help="metadata only, skip video download")
    return ap.parse_args()
