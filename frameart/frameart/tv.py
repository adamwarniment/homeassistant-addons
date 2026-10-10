"""Thin wrapper over samsungtvws' Frame art-mode API (blocking; call from a thread)."""

from __future__ import annotations

import logging
import os
import time
import uuid

log = logging.getLogger(__name__)


class TVError(Exception):
    pass


class FrameTV:
    def __init__(self, host: str, port: int, token_file: str, timeout: float = 15):
        self.host, self.port, self.token_file, self.timeout = host, port, token_file, timeout

    def _art(self):
        if not self.host:
            raise TVError("No TV address configured")
        from samsungtvws import SamsungTVWS
        tv = SamsungTVWS(self.host, port=self.port, token_file=self.token_file,
                         timeout=self.timeout, name="FrameArt")
        return tv.art()

    def status(self) -> dict:
        try:
            art = self._art()
            if not art.supported():
                return {"reachable": True, "art_mode_supported": False}
            return {"reachable": True, "art_mode_supported": True, "art_mode": art.get_artmode()}
        except Exception as e:
            return {"reachable": False, "error": str(e)}

    def show(self, jpeg: bytes, matte: str = "none") -> str:
        try:
            art = self._art()
            content_id = art.upload(jpeg, file_type="JPEG", matte=matte, portrait_matte=matte)
            if not content_id:
                raise TVError("TV did not return a content id")
            art.select_image(content_id, show=True)
            return content_id
        except TVError:
            raise
        except Exception as e:
            raise TVError(f"Upload failed: {e}") from e

    def select(self, content_id: str) -> bool:
        try:
            art = self._art()
            available = {item.get("content_id") for item in (art.available() or [])}
            if content_id not in available:
                return False
            art.select_image(content_id, show=True)
            return True
        except Exception as e:
            raise TVError(f"Select failed: {e}") from e

    def delete(self, content_ids: list[str]) -> None:
        if content_ids:
            try:
                self._art().delete_list(content_ids)
            except Exception as e:
                log.warning("Could not delete old uploads %s: %s", content_ids, e)


class DryRunTV:
    """Stands in for the TV during local development: writes uploads to disk."""

    def __init__(self, out_dir: str):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.ids: set[str] = set(f[:-4] for f in os.listdir(out_dir) if f.endswith(".jpg"))

    def status(self) -> dict:
        return {"reachable": True, "art_mode_supported": True, "art_mode": "dry-run"}

    def show(self, jpeg: bytes, matte: str = "none") -> str:
        content_id = f"DRY_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        with open(os.path.join(self.out_dir, content_id + ".jpg"), "wb") as f:
            f.write(jpeg)
        self.ids.add(content_id)
        log.info("[dry-run] wrote %s", content_id)
        return content_id

    def select(self, content_id: str) -> bool:
        return content_id in self.ids

    def delete(self, content_ids: list[str]) -> None:
        for cid in content_ids:
            self.ids.discard(cid)
            try:
                os.remove(os.path.join(self.out_dir, cid + ".jpg"))
            except OSError:
                pass
