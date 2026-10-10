"""Entry point: `python -m frameart`.

In the add-on everything lives under /data and /media. For local development
set FRAMEART_DATA (and optionally FRAMEART_PORT); with no TV host configured
uploads go to <data>/cache/dry-run instead of a television.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
import threading

from aiohttp import web

from .engine import Engine
from .store import Store
from .web import HomeAssistant, create_app

log = logging.getLogger("frameart")


def _addon_options(data_dir: str) -> dict:
    try:
        with open(os.path.join(data_dir, "options.json")) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _stdin_reader(loop: asyncio.AbstractEventLoop, engine: Engine) -> None:
    """hassio.addon_stdin writes one JSON value per line."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
        except ValueError:
            cmd = line
        log.info("stdin command: %s", cmd)
        asyncio.run_coroutine_threadsafe(engine.command(cmd), loop)


async def main() -> None:
    data_dir = os.environ.get("FRAMEART_DATA", "/data")
    options = _addon_options(data_dir)
    logging.basicConfig(
        level=getattr(logging, str(options.get("log_level", "info")).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("websocket").setLevel(logging.WARNING)

    token = os.environ.get("SUPERVISOR_TOKEN")
    store = Store(data_dir)
    if store.is_new:
        store.import_legacy(options)
    engine = Engine(store, os.path.join(data_dir, "cache"), HomeAssistant(token) if token else None)
    await engine.start()

    loop = asyncio.get_running_loop()
    if not sys.stdin.isatty():
        threading.Thread(target=_stdin_reader, args=(loop, engine), daemon=True).start()

    app = create_app(engine, restrict_to_ingress=bool(token))
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    port = int(os.environ.get("FRAMEART_PORT", "8099"))
    await web.TCPSite(runner, "0.0.0.0" if token else "127.0.0.1", port).start()
    log.info("Frame Art ready on port %d%s", port, "" if token else f" – open http://127.0.0.1:{port}")
    if engine.ha:
        await engine.ha.publish(engine.snapshot())

    stop = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    await stop.wait()
    await engine.stop()
    await runner.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
