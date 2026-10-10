# Home Assistant add-ons

| Add-on | |
| --- | --- |
| [Frame Art](frameart/) | Watches a photo folder and shows it on a Samsung Frame TV in a realistic paper mat, with a web UI for the frame design. |

## Install

Settings → Add-ons → Add-on store → ⋮ → **Repositories** → add this repository's
git URL. Home Assistant builds the add-on on your machine from the `Dockerfile`;
there is no container registry involved.

User documentation lives in [frameart/DOCS.md](frameart/DOCS.md) (also shown on the add-on's Documentation tab).

## Development

```
frameart/                 the add-on (what Home Assistant builds)
  config.yaml             add-on manifest – bump `version` to release
  Dockerfile, build.yaml  build recipe (HA base-python image + pip wheels)
  frameart/               Python package
    renderer.py           mat/bevel/imperfection rendering (Pillow only)
    library.py            folder polling, EXIF-aware dimensions, thumbnails
    engine.py             selection, scheduling, upload cache, pruning
    tv.py                 Samsung Frame art-mode client + dry-run stand-in
    web.py                aiohttp API for the ingress UI, HA sensor
    static/               UI – plain HTML/CSS/JS, no build step
tests/                    pytest
dev/                      local run, deploy-to-HA and release scripts
```

### Run it on your laptop

```bash
make dev
```

Opens on <http://127.0.0.1:8099> with sample photos in `dev/media` and dry-run
mode on – "uploads" are written to `.dev/data/cache/dry-run/` so you can see the
exact 3840×2160 JPEG the TV would get. Put real photos in `dev/media` to tune the
frame. Point it at your actual TV by turning dry run off in Settings.

### Try it on Home Assistant without releasing

```bash
HA_SSH=root@homeassistant.local make deploy
```

Copies the working tree to `/addons/frameart_dev` over SSH (needs the SSH add-on
with your public key) and rebuilds it as a local add-on called **Frame Art (dev)**.
Stop the released add-on while testing so they don't both drive the TV.

### Release

1. Add a `## x.y.z` section to `frameart/CHANGELOG.md` and commit.
2. `make release V=x.y.z` – runs tests, bumps `config.yaml`, tags, pushes.
3. In HA: Add-on store → ⋮ → **Check for updates** → Update. HA rebuilds locally (a minute or two on a Pi).

CI (`.github/workflows/ci.yml`) runs the tests and a real Docker build on every
push; it works unchanged on GitHub Actions and Gitea/Forgejo Actions.
