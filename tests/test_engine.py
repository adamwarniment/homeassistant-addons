import asyncio
import os

from PIL import Image

from frameart.engine import Engine, _in_quiet_hours
from frameart.store import Store, merge_settings, DEFAULT_SETTINGS
import datetime as dt


def make_library(tmp_path, specs):
    media = tmp_path / "media"
    media.mkdir()
    for name, size in specs:
        Image.new("RGB", size, (120, 120, 120)).save(media / name)
    return media


def make_engine(tmp_path, media, **playback):
    store = Store(str(tmp_path / "data"))
    store.update_settings({"library": {"folder": str(media)}, "tv": {"dry_run": True},
                           "playback": playback})
    return Engine(store, str(tmp_path / "data" / "cache"))


def test_show_uploads_then_reuses(tmp_path):
    media = make_library(tmp_path, [("a.jpg", (300, 200))])
    eng = make_engine(tmp_path, media)

    async def run():
        await eng.start()
        first = await eng.show(["a.jpg"])
        second = await eng.show(["a.jpg"])
        await eng.stop()
        return first, second

    first, second = asyncio.run(run())
    assert first["ok"] and not first["reused"]
    assert second["ok"] and second["reused"] and second["content_id"] == first["content_id"]
    assert len(os.listdir(tmp_path / "data" / "cache" / "dry-run")) == 1


def test_portraits_are_paired(tmp_path):
    media = make_library(tmp_path, [("p1.jpg", (200, 300)), ("p2.jpg", (200, 300)), ("l.jpg", (300, 200))])
    eng = make_engine(tmp_path, media, pair_portraits=True)

    async def run():
        await eng.start()
        r = await eng.show(["p1.jpg"])
        await eng.stop()
        return r

    r = asyncio.run(run())
    assert r["paths"] == ["p1.jpg", "p2.jpg"]


def test_shuffle_shows_everything_before_repeating(tmp_path):
    names = [f"{i}.jpg" for i in range(5)]
    media = make_library(tmp_path, [(n, (300, 200)) for n in names])
    eng = make_engine(tmp_path, media)

    async def run():
        await eng.start()
        seen = [(await eng.show())["paths"][0] for _ in names]
        await eng.stop()
        return seen

    assert sorted(asyncio.run(run())) == names


def test_pruning_keeps_limit(tmp_path):
    names = [f"{i}.jpg" for i in range(4)]
    media = make_library(tmp_path, [(n, (300, 200)) for n in names])
    eng = make_engine(tmp_path, media)
    eng.store.update_settings({"tv": {"keep_uploads": 2}})

    async def run():
        await eng.start()
        for n in names:
            await eng.show([n])
        await eng.stop()

    asyncio.run(run())
    assert len(eng.store.uploads) == 2
    assert len(os.listdir(tmp_path / "data" / "cache" / "dry-run")) == 2


def test_new_file_detected(tmp_path):
    media = make_library(tmp_path, [("a.jpg", (300, 200))])
    eng = make_engine(tmp_path, media)
    eng.library.configure(str(media), True)
    assert eng.library.scan() == []          # first scan seeds the index
    Image.new("RGB", (300, 200)).save(media / "b.jpg")
    assert [p.path for p in eng.library.scan()] == ["b.jpg"]


def test_quiet_hours_wraps_midnight():
    at = lambda h, m=0: dt.datetime(2026, 1, 1, h, m)
    assert _in_quiet_hours("22:00", "07:00", at(23))
    assert _in_quiet_hours("22:00", "07:00", at(6, 59))
    assert not _in_quiet_hours("22:00", "07:00", at(12))
    assert not _in_quiet_hours("", "", at(12))


def test_settings_merge_coerces_types():
    s = merge_settings(DEFAULT_SETTINGS, {"tv": {"port": "8001", "bogus": 1},
                                          "playback": {"enabled": "false", "interval_minutes": 0}})
    assert s["tv"]["port"] == 8001 and "bogus" not in s["tv"]
    assert s["playback"]["enabled"] is False and s["playback"]["interval_minutes"] == 1


def test_legacy_options_imported(tmp_path):
    store = Store(str(tmp_path / "data"))
    assert store.is_new
    store.import_legacy({"tv": "192.168.4.20,192.168.4.21", "media_folder_path": "/media/immich",
                         "google_art": True, "matte": "none"})
    again = Store(str(tmp_path / "data"))
    assert not again.is_new
    assert again.settings["tv"]["host"] == "192.168.4.20"
    assert again.settings["library"]["folder"] == "/media/immich"


def test_legacy_placeholder_ip_ignored(tmp_path):
    store = Store(str(tmp_path / "data"))
    store.import_legacy({"tv": "192.168.1.1"})
    assert store.settings["tv"]["host"] == ""


def test_cleanup_removes_leftovers_but_keeps_ours(tmp_path):
    media = make_library(tmp_path, [("a.jpg", (300, 200))])
    eng = make_engine(tmp_path, media)
    dry = tmp_path / "data" / "cache" / "dry-run"
    dry.mkdir(parents=True)
    for old in ("MY_F0001", "MY_F0002", "MY_F0003"):   # uploads from the 1.x add-on
        (dry / f"{old}.jpg").write_bytes(b"x")

    async def run():
        await eng.start()
        shown = await eng.show(["a.jpg"])
        before = await eng.storage()
        result = await eng.cleanup()
        after = await eng.storage()
        await eng.stop()
        return shown, before, result, after

    shown, before, result, after = asyncio.run(run())
    assert before == {"ok": True, "total": 4, "ours": 1, "others": 3}
    assert result == {"ok": True, "deleted": 3, "kept": 1}
    assert after["others"] == 0
    assert os.listdir(dry) == [shown["content_id"] + ".jpg"]
