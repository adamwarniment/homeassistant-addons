"""Watches the photo folder by polling.

Polling (rather than inotify) is deliberate: Home Assistant media folders are
often network shares, where inotify events never arrive.
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
from dataclasses import dataclass, asdict

from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from .renderer import is_portrait

register_heif_opener()
log = logging.getLogger(__name__)

EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}


@dataclass
class Photo:
    path: str          # relative to the library folder
    mtime: float
    size: int
    width: int
    height: int

    @property
    def portrait(self) -> bool:
        return is_portrait(self.width, self.height)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["portrait"] = self.portrait
        return d


def open_photo(path: str) -> Image.Image:
    """Open any supported file as an upright RGB image."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        return img.convert("RGB")


def _dimensions(path: str) -> tuple[int, int]:
    with Image.open(path) as img:
        w, h = img.size
        try:
            orientation = img.getexif().get(0x0112, 1)
        except Exception:
            orientation = 1
    return (h, w) if orientation in (5, 6, 7, 8) else (w, h)


class Library:
    def __init__(self, cache_dir: str):
        self.folder = ""
        self.recursive = True
        self.photos: dict[str, Photo] = {}
        self.thumb_dir = os.path.join(cache_dir, "thumbs")
        os.makedirs(self.thumb_dir, exist_ok=True)
        self._lock = threading.Lock()

    def configure(self, folder: str, recursive: bool) -> None:
        if folder != self.folder or recursive != self.recursive:
            with self._lock:
                self.folder, self.recursive = folder, recursive
                self.photos = {}

    def abspath(self, rel: str) -> str:
        full = os.path.realpath(os.path.join(self.folder, rel))
        root = os.path.realpath(self.folder)
        if not full.startswith(root + os.sep):
            raise ValueError("path escapes library folder")
        return full

    def scan(self) -> list[Photo]:
        """Refresh the index. Returns photos that are new since the last scan."""
        if not self.folder or not os.path.isdir(self.folder):
            return []
        seen: dict[str, tuple[float, int]] = {}
        for root, dirs, files in os.walk(self.folder):
            dirs[:] = [d for d in dirs if not d.startswith(".")] if self.recursive else []
            for name in files:
                if name.startswith(".") or os.path.splitext(name)[1].lower() not in EXTENSIONS:
                    continue
                full = os.path.join(root, name)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                seen[os.path.relpath(full, self.folder)] = (st.st_mtime, st.st_size)

        added = []
        with self._lock:
            first_scan = not self.photos
            for rel in list(self.photos):
                if rel not in seen:
                    del self.photos[rel]
            for rel, (mtime, size) in seen.items():
                known = self.photos.get(rel)
                if known and known.mtime == mtime and known.size == size:
                    continue
                try:
                    w, h = _dimensions(os.path.join(self.folder, rel))
                except Exception as e:  # partially-copied or corrupt file; retry next scan
                    log.debug("Skipping %s: %s", rel, e)
                    continue
                photo = Photo(rel, mtime, size, w, h)
                self.photos[rel] = photo
                if not known and not first_scan:
                    added.append(photo)
        if added:
            log.info("Found %d new photo(s): %s", len(added), ", ".join(p.path for p in added[:5]))
        return added

    def all(self) -> list[Photo]:
        with self._lock:
            return list(self.photos.values())

    def get(self, rel: str) -> Photo | None:
        return self.photos.get(rel)

    def thumbnail(self, rel: str, size: int = 480) -> str:
        photo = self.photos.get(rel)
        if not photo:
            raise KeyError(rel)
        key = hashlib.sha1(f"{rel}|{photo.mtime}|{size}".encode()).hexdigest()
        out = os.path.join(self.thumb_dir, key + ".jpg")
        if not os.path.exists(out):
            img = open_photo(self.abspath(rel))
            img.thumbnail((size, size), Image.LANCZOS)
            img.save(out, "JPEG", quality=82)
        return out
