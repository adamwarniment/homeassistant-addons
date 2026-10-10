"""Ties the library, renderer and TV together: scanning, scheduling and pushing."""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import io
import json
import logging
import os
import random
import time

from . import renderer
from .library import Library, Photo, open_photo
from .store import Store
from .tv import DryRunTV, FrameTV, TVError

log = logging.getLogger(__name__)


def _in_quiet_hours(start: str, end: str, now: dt.datetime | None = None) -> bool:
    try:
        s = dt.time.fromisoformat(start)
        e = dt.time.fromisoformat(end)
    except ValueError:
        return False
    t = (now or dt.datetime.now()).time()
    return s <= t < e if s <= e else (t >= s or t < e)


class Engine:
    def __init__(self, store: Store, cache_dir: str, ha=None):
        self.store = store
        self.library = Library(cache_dir)
        self.cache_dir = cache_dir
        self.ha = ha
        self.current: dict | None = store.history[-1] if store.history else None
        self.next_at: float | None = None
        self.busy = False
        self.last_error: str | None = None
        self.tv_status: dict = {}
        self._push_lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------------ lifecycle

    @property
    def settings(self) -> dict:
        return self.store.settings

    def tv(self):
        t = self.settings["tv"]
        if t["dry_run"] or not t["host"]:
            return DryRunTV(os.path.join(self.cache_dir, "dry-run"))
        return FrameTV(t["host"], t["port"], self.store.token_file)

    async def start(self) -> None:
        self._apply_library_settings()
        await asyncio.to_thread(self.library.scan)
        log.info("Library: %d photo(s) in %s", len(self.library.photos), self.library.folder)
        self._schedule_next()
        self._tasks = [asyncio.create_task(self._scan_loop()),
                       asyncio.create_task(self._rotate_loop())]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()

    def settings_changed(self) -> None:
        self._apply_library_settings()
        self._schedule_next()
        self._wake.set()

    def _apply_library_settings(self) -> None:
        lib = self.settings["library"]
        self.library.configure(lib["folder"], lib["recursive"])

    def _schedule_next(self) -> None:
        pb = self.settings["playback"]
        self.next_at = time.time() + pb["interval_minutes"] * 60 if pb["enabled"] else None

    async def _scan_loop(self) -> None:
        while True:
            await asyncio.sleep(self.settings["library"]["scan_seconds"])
            try:
                added = await asyncio.to_thread(self.library.scan)
            except Exception:
                log.exception("Library scan failed")
                continue
            if added and self.settings["playback"]["show_new_immediately"]:
                newest = max(added, key=lambda p: p.mtime)
                await self.show([newest.path], reason="new photo")

    async def _rotate_loop(self) -> None:
        while True:
            timeout = max(1.0, self.next_at - time.time()) if self.next_at else 3600
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=timeout)
                self._wake.clear()
                continue
            except asyncio.TimeoutError:
                pass
            pb = self.settings["playback"]
            if not self.next_at or time.time() < self.next_at:
                continue
            if _in_quiet_hours(pb["quiet_start"], pb["quiet_end"]):
                log.debug("Quiet hours; skipping rotation")
                self._schedule_next()
                continue
            await self.show(reason="schedule")

    # ------------------------------------------------------------------ selection

    def _pick(self, exclude: set[str] | None = None) -> list[Photo]:
        photos = [p for p in self.library.all() if p.path not in (exclude or set())]
        if not photos:
            return []
        order = self.settings["playback"]["order"]
        shown = self.store.shown
        if order == "newest":
            photos.sort(key=lambda p: p.mtime, reverse=True)
        elif order == "name":
            photos.sort(key=lambda p: p.path.lower())
        else:
            random.shuffle(photos)

        fresh = [p for p in photos if p.path not in shown]
        if not fresh:  # everything has been shown: start a new cycle
            shown.clear()
            fresh = photos
        first = fresh[0]
        if order == "name" and self.current:
            # continue alphabetically after whatever is up now
            last = self.current.get("paths", [""])[-1].lower()
            later = [p for p in fresh if p.path.lower() > last]
            first = later[0] if later else fresh[0]
        return self._with_partner(first, fresh, photos)

    def _with_partner(self, first: Photo, fresh: list[Photo], photos: list[Photo]) -> list[Photo]:
        if not (first.portrait and self.settings["playback"]["pair_portraits"]):
            return [first]
        for pool in (fresh, photos):
            partner = next((p for p in pool if p.portrait and p.path != first.path), None)
            if partner:
                return [first, partner]
        return [first]

    # ------------------------------------------------------------------ rendering

    def render_key(self, photos: list[Photo]) -> str:
        payload = json.dumps({
            "photos": [[p.path, p.mtime] for p in photos],
            "frame": self.settings["frame"],
            "matte": self.settings["tv"]["tv_matte"],
        }, sort_keys=True)
        return hashlib.sha1(payload.encode()).hexdigest()

    def _render(self, photos: list[Photo], style: dict, size=renderer.CANVAS, quality=92) -> bytes:
        images = [open_photo(self.library.abspath(p.path)) for p in photos]
        img = renderer.render(images, style, size=size, key="|".join(p.path for p in photos))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality, optimize=size == renderer.CANVAS)
        return buf.getvalue()

    async def preview(self, paths: list[str] | None, style: dict | None, width: int = 1280) -> bytes:
        photos = self._resolve(paths)
        if not photos and self.current:
            photos = self._resolve(self.current.get("paths"))
        if not photos:
            photos = self._pick()
        if not photos:
            raise LookupError("No photos in the library yet")
        width = max(320, min(3840, width))
        size = (width, round(width * 9 / 16))
        merged = renderer.normalize_style({**self.settings["frame"], **(style or {})})
        return await asyncio.to_thread(self._render, photos, merged, size, 85)

    def _resolve(self, paths) -> list[Photo]:
        out = [self.library.get(p) for p in (paths or [])]
        return [p for p in out if p][:2]

    # ------------------------------------------------------------------ pushing

    async def show(self, paths: list[str] | None = None, reason: str = "manual") -> dict:
        async with self._push_lock:
            self.busy = True
            try:
                return await self._show(paths, reason)
            finally:
                self.busy = False
                self._schedule_next()

    async def _show(self, paths, reason) -> dict:
        photos = self._resolve(paths)
        if paths and len(photos) == 1 and photos[0].portrait:
            photos = self._with_partner(photos[0], [p for p in self.library.all()
                                                    if p.path not in self.store.shown], self.library.all())
        if not photos:
            photos = self._pick()
        if not photos:
            self.last_error = "No photos found in " + self.library.folder
            log.warning(self.last_error)
            return {"ok": False, "error": self.last_error}

        key = self.render_key(photos)
        tv = self.tv()
        names = [p.path for p in photos]
        log.info("Showing %s (%s)", " + ".join(names), reason)
        try:
            cached = self.store.uploads.get(key)
            reused = bool(cached) and await asyncio.to_thread(tv.select, cached["content_id"])
            if reused:
                content_id = cached["content_id"]
                cached["time"] = time.time()
            else:
                jpeg = await asyncio.to_thread(self._render, photos, self.settings["frame"])
                content_id = await asyncio.to_thread(tv.show, jpeg, self.settings["tv"]["tv_matte"])
                self.store.uploads[key] = {"content_id": content_id, "time": time.time()}
                await self._prune(tv, keep_id=content_id)
        except TVError as e:
            self.last_error = str(e)
            log.error("TV error: %s", e)
            return {"ok": False, "error": self.last_error}

        self.last_error = None
        for name in names:
            if name not in self.store.shown:
                self.store.shown.append(name)
        entry = {"paths": names, "content_id": content_id, "reason": reason,
                 "reused": reused, "time": time.time()}
        self.store.add_history(entry)
        self.current = entry
        if self.ha:
            asyncio.create_task(self.ha.publish(self.snapshot()))
        return {"ok": True, **entry}

    async def _prune(self, tv, keep_id: str) -> None:
        keep = self.settings["tv"]["keep_uploads"]
        if not keep or len(self.store.uploads) <= keep:
            self.store.save_state()
            return
        ordered = sorted(self.store.uploads.items(), key=lambda kv: kv[1]["time"], reverse=True)
        stale = [(k, v) for k, v in ordered[keep:] if v["content_id"] != keep_id]
        await asyncio.to_thread(tv.delete, [v["content_id"] for _, v in stale])
        for k, _ in stale:
            self.store.uploads.pop(k, None)
        self.store.save_state()
        log.info("Removed %d old upload(s) from the TV", len(stale))

    # ------------------------------------------------------------------ TV storage

    def _protected_ids(self, on_screen: str | None) -> set[str]:
        keep = {v["content_id"] for v in self.store.uploads.values()}
        if self.current:
            keep.add(self.current.get("content_id"))
        if on_screen:
            keep.add(on_screen)
        return keep

    async def storage(self) -> dict:
        """What's in the TV's My Photos, split into ours vs. leftovers from earlier versions."""
        try:
            ids, on_screen = await asyncio.to_thread(self.tv().my_photos)
        except TVError as e:
            return {"ok": False, "error": str(e)}
        keep = self._protected_ids(on_screen)
        others = [i for i in ids if i not in keep]
        return {"ok": True, "total": len(ids), "ours": len(ids) - len(others), "others": len(others)}

    async def cleanup(self) -> dict:
        """Delete every My Photos image Frame Art isn't tracking, except the one on screen."""
        async with self._push_lock:
            try:
                tv = self.tv()
                ids, on_screen = await asyncio.to_thread(tv.my_photos)
                keep = self._protected_ids(on_screen)
                doomed = [i for i in ids if i not in keep]
                if doomed:
                    await asyncio.to_thread(tv.delete_strict, doomed)
            except TVError as e:
                log.error("Cleanup failed: %s", e)
                return {"ok": False, "error": str(e)}
        log.info("Cleanup removed %d old photo(s) from the TV, kept %d", len(doomed), len(ids) - len(doomed))
        return {"ok": True, "deleted": len(doomed), "kept": len(ids) - len(doomed)}

    async def refresh_tv_status(self) -> dict:
        self.tv_status = await asyncio.to_thread(self.tv().status)
        return self.tv_status

    # ------------------------------------------------------------------ commands

    async def command(self, cmd) -> dict:
        """Commands from the UI or hassio.addon_stdin: next, pause, resume, rescan, cleanup, {"show": path}."""
        if isinstance(cmd, str):
            cmd = {"action": cmd.strip().lower()}
        action = cmd.get("action") or ("show" if "show" in cmd else "")
        if action in ("next", "show"):
            target = cmd.get("show") or cmd.get("path")
            return await self.show([target] if isinstance(target, str) else target, reason=action)
        if action in ("pause", "resume"):
            self.store.update_settings({"playback": {"enabled": action == "resume"}})
            self.settings_changed()
            return {"ok": True}
        if action == "cleanup":
            return await self.cleanup()
        if action == "rescan":
            await asyncio.to_thread(self.library.scan)
            return {"ok": True, "count": len(self.library.photos)}
        return {"ok": False, "error": f"unknown command {cmd!r}"}

    def snapshot(self) -> dict:
        return {
            "current": self.current,
            "next_at": self.next_at,
            "busy": self.busy,
            "last_error": self.last_error,
            "photo_count": len(self.library.photos),
            "folder": self.library.folder,
            "folder_exists": bool(self.library.folder) and os.path.isdir(self.library.folder),
            "tv": self.tv_status,
            "dry_run": self.settings["tv"]["dry_run"] or not self.settings["tv"]["host"],
            "enabled": self.settings["playback"]["enabled"],
        }
