"""HTTP API + static UI, served through Home Assistant ingress."""

from __future__ import annotations

import asyncio
import json
import logging
import os

from aiohttp import web

from .engine import Engine

log = logging.getLogger(__name__)
STATIC = os.path.join(os.path.dirname(__file__), "static")
INGRESS_PEER = "172.30.32.2"


def create_app(engine: Engine, restrict_to_ingress: bool) -> web.Application:
    @web.middleware
    async def guard(request: web.Request, handler):
        if restrict_to_ingress and request.remote != INGRESS_PEER:
            raise web.HTTPForbidden(text="Use the add-on through Home Assistant")
        resp = await handler(request)
        if request.path.startswith("/api/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    app = web.Application(middlewares=[guard], client_max_size=2 * 1024 * 1024)
    routes = web.RouteTableDef()

    @routes.get("/")
    async def index(_):
        return web.FileResponse(os.path.join(STATIC, "index.html"),
                                headers={"Cache-Control": "no-cache"})

    @routes.get("/api/status")
    async def status(_):
        return web.json_response(engine.snapshot())

    @routes.get("/api/settings")
    async def get_settings(_):
        return web.json_response(engine.settings)

    @routes.put("/api/settings")
    async def put_settings(request):
        patch = await request.json()
        tv_before = dict(engine.settings["tv"])
        settings = engine.store.update_settings(patch)
        engine.settings_changed()
        if settings["tv"] != tv_before:
            engine.tv_status = {}
        return web.json_response(settings)

    @routes.get("/api/photos")
    async def photos(_):
        items = sorted(engine.library.all(), key=lambda p: p.mtime, reverse=True)
        shown = set(engine.store.shown)
        return web.json_response([{**p.to_dict(), "shown": p.path in shown} for p in items])

    @routes.get("/api/thumb")
    async def thumb(request):
        try:
            path = await asyncio.to_thread(engine.library.thumbnail, request.query["path"])
        except (KeyError, ValueError):
            raise web.HTTPNotFound()
        return web.FileResponse(path, headers={"Cache-Control": "max-age=86400"})

    @routes.post("/api/preview")
    async def preview(request):
        body = await request.json()
        try:
            jpeg = await engine.preview(body.get("paths"), body.get("style"),
                                        int(body.get("width", 1280)))
        except LookupError as e:
            return web.json_response({"error": str(e)}, status=404)
        return web.Response(body=jpeg, content_type="image/jpeg")

    @routes.post("/api/command")
    async def command(request):
        body = await request.json()
        return web.json_response(await engine.command(body))

    @routes.get("/api/history")
    async def history(_):
        return web.json_response(list(reversed(engine.store.history[-100:])))

    @routes.get("/api/tv/storage")
    async def tv_storage(_):
        return web.json_response(await engine.storage())

    @routes.post("/api/tv/test")
    async def tv_test(_):
        return web.json_response(await engine.refresh_tv_status())

    app.add_routes(routes)
    app.router.add_static("/static/", STATIC)
    return app


class HomeAssistant:
    """Mirrors what's on the Frame into a sensor entity via the Supervisor proxy."""

    URL = "http://supervisor/core/api/states/sensor.frame_art"

    def __init__(self, token: str):
        self.token = token

    async def publish(self, snap: dict) -> None:
        import aiohttp
        cur = snap.get("current") or {}
        paths = cur.get("paths") or []
        body = {
            "state": " + ".join(os.path.basename(p) for p in paths)[:255] or "idle",
            "attributes": {
                "friendly_name": "Frame Art",
                "icon": "mdi:image-frame",
                "paths": paths,
                "content_id": cur.get("content_id"),
                "reason": cur.get("reason"),
                "photo_count": snap.get("photo_count"),
                "rotation_enabled": snap.get("enabled"),
            },
        }
        try:
            async with aiohttp.ClientSession() as s:
                await s.post(self.URL, data=json.dumps(body), timeout=aiohttp.ClientTimeout(total=10),
                             headers={"Authorization": f"Bearer {self.token}",
                                      "Content-Type": "application/json"})
        except Exception as e:
            log.debug("Could not update sensor: %s", e)
