"""Persistent state under the add-on's /data volume: settings, history, upload cache."""

from __future__ import annotations

import copy
import json
import logging
import os
import tempfile
import threading
import time

from . import renderer

log = logging.getLogger(__name__)

DEFAULT_SETTINGS: dict = {
    "tv": {
        "host": "",
        "port": 8002,
        "tv_matte": "none",       # Samsung's own matte on top of ours; normally none
        "keep_uploads": 30,       # delete older add-on uploads from the TV; 0 = never
        "dry_run": False,         # render only, never talk to the TV
    },
    "library": {
        "folder": "/media/frame",
        "recursive": True,
        "scan_seconds": 30,
    },
    "playback": {
        "enabled": True,
        "interval_minutes": 60,
        "order": "shuffle",       # shuffle | newest | name
        "show_new_immediately": True,
        "pair_portraits": True,
        "quiet_start": "",        # "HH:MM" – no rotation between start and end
        "quiet_end": "",
    },
    "frame": dict(renderer.DEFAULT_STYLE),
}

HISTORY_LIMIT = 200


def _atomic_write(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), prefix=".tmp-")
    with os.fdopen(fd, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def _read(path: str, default):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (OSError, ValueError) as e:
        log.warning("Could not read %s (%s); starting fresh", path, e)
        return default


def merge_settings(base: dict, patch: dict) -> dict:
    """Overlay `patch` onto `base`, keeping only known keys and coercing to the default's type."""
    out = copy.deepcopy(base)
    for section, defaults in DEFAULT_SETTINGS.items():
        values = (patch or {}).get(section)
        if not isinstance(values, dict):
            continue
        for key, value in values.items():
            if key not in defaults:
                continue
            default = defaults[key]
            try:
                if isinstance(default, bool):
                    value = value if isinstance(value, bool) else str(value).lower() in ("1", "true", "yes", "on")
                elif isinstance(default, int):
                    value = int(value)
                elif isinstance(default, float):
                    value = float(value)
                else:
                    value = str(value).strip()
            except (TypeError, ValueError):
                continue
            out[section][key] = value
    out["frame"] = renderer.normalize_style(out["frame"])
    pb = out["playback"]
    pb["interval_minutes"] = max(1, pb["interval_minutes"])
    if pb["order"] not in ("shuffle", "newest", "name"):
        pb["order"] = "shuffle"
    out["library"]["scan_seconds"] = max(5, out["library"]["scan_seconds"])
    out["tv"]["keep_uploads"] = max(0, out["tv"]["keep_uploads"])
    return out


class Store:
    def __init__(self, data_dir: str):
        self.dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        self._lock = threading.RLock()
        self.is_new = not os.path.exists(self._p("settings.json"))
        self.settings = merge_settings(DEFAULT_SETTINGS, _read(self._p("settings.json"), {}))
        state = _read(self._p("state.json"), {})
        self.history: list[dict] = state.get("history", [])
        # render-key -> TV content id, so a photo shown before is re-selected, not re-uploaded
        self.uploads: dict[str, dict] = state.get("uploads", {})
        self.shown: list[str] = state.get("shown", [])  # shuffle bag of already-shown paths

    def _p(self, name: str) -> str:
        return os.path.join(self.dir, name)

    @property
    def token_file(self) -> str:
        return self._p("tv-token.txt")

    def import_legacy(self, options: dict) -> None:
        """Seed settings from the 1.x add-on options (tv, media_folder_path) on first start."""
        patch: dict = {}
        host = str(options.get("tv") or "").split(",")[0].strip()
        if host and host != "192.168.1.1":  # 1.x shipped this placeholder as the default
            patch["tv"] = {"host": host}
        folder = str(options.get("media_folder_path") or "").strip()
        if folder:
            patch["library"] = {"folder": folder}
        if patch:
            log.info("Imported settings from the previous version: %s", patch)
        self.update_settings(patch)

    def update_settings(self, patch: dict) -> dict:
        with self._lock:
            self.settings = merge_settings(self.settings, patch)
            _atomic_write(self._p("settings.json"), self.settings)
            return copy.deepcopy(self.settings)

    def save_state(self) -> None:
        with self._lock:
            _atomic_write(self._p("state.json"), {
                "history": self.history[-HISTORY_LIMIT:],
                "uploads": self.uploads,
                "shown": self.shown,
            })

    def add_history(self, entry: dict) -> None:
        with self._lock:
            entry.setdefault("time", time.time())
            self.history.append(entry)
            del self.history[:-HISTORY_LIMIT]
            self.save_state()
