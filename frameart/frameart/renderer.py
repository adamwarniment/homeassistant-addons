"""Renders photos into a 16:9 canvas behind a bevel-cut paper mat.

All geometry is expressed as fractions of the canvas height so a small
preview render and the full 4K upload look the same. Every random choice
comes from a seeded RNG, so the same photo + style always renders the same
way (the preview you approve is the image that gets uploaded).

The "imperfection" controls exist to stop the mat looking computer-drawn:
real mat board has paper grain, faint mottling, stray fibres, a colour that
is never quite the swatch, and hand-cut openings that are a hair off-square.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, ImageStat

CANVAS = (3840, 2160)

DEFAULT_STYLE: dict = {
    "style": "bevel",          # "bevel" | "flat" | "none"
    "mat_color": "#E8E6DF",
    "core_color": "#F6F4EE",   # colour of the exposed board core on the bevel
    "border": 0.11,            # mat width around the opening(s), fraction of height
    "bottom_weight": 0.0,      # extra mat at the bottom, fraction of height
    "window": "fill",          # "fill" = crop photo to opening, "match" = opening follows photo
    "portrait_gap": 0.07,      # mat between two paired portraits
    "bevel": 0.0065,           # bevel width, fraction of height
    "bevel_contrast": 0.55,    # 0..1 how strongly the light shades the four bevel sides
    "light_angle": 110,        # degrees the light comes from (90 = straight above)
    "shadow": 0.5,             # 0..1 depth shadow the mat casts onto the photo
    "emboss_line": False,      # debossed rule around the opening
    "emboss_offset": 0.022,    # distance of the rule from the bevel, fraction of height
    "imperfection": 0.35,      # master 0..1 for everything below
    "grain": 0.6,
    "mottle": 0.5,
    "tint_drift": 0.5,
    "cut_wobble": 0.5,
    "fibers": 0.35,
    "seed": 0,
    "vary_per_photo": True,
}

PORTRAIT_RATIO = 1.15  # height / width beyond which a photo counts as portrait


def is_portrait(width: int, height: int) -> bool:
    return height > width * PORTRAIT_RATIO


def normalize_style(style: dict | None) -> dict:
    out = dict(DEFAULT_STYLE)
    for key, default in DEFAULT_STYLE.items():
        if not style or key not in style:
            continue
        value = style[key]
        try:
            if isinstance(default, bool):
                out[key] = bool(value)
            elif isinstance(default, int):
                out[key] = int(value)
            elif isinstance(default, float):
                out[key] = float(value)
            else:
                out[key] = str(value)
        except (TypeError, ValueError):
            pass
    for key in ("bevel_contrast", "shadow", "imperfection", "grain", "mottle",
                "tint_drift", "cut_wobble", "fibers"):
        out[key] = min(1.0, max(0.0, out[key]))
    out["border"] = min(0.4, max(0.0, out["border"]))
    out["bottom_weight"] = min(0.2, max(0.0, out["bottom_weight"]))
    out["portrait_gap"] = min(0.3, max(0.0, out["portrait_gap"]))
    out["bevel"] = min(0.03, max(0.0, out["bevel"]))
    if out["style"] not in ("bevel", "flat", "none"):
        out["style"] = "bevel"
    if out["window"] not in ("fill", "match"):
        out["window"] = "fill"
    return out


def style_seed(style: dict, key: str) -> int:
    base = f"{style['seed']}|{key if style['vary_per_photo'] else ''}"
    return int.from_bytes(hashlib.sha256(base.encode()).digest()[:8], "big")


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(c * 2 for c in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (232, 230, 223)


# --------------------------------------------------------------------------- geometry

@dataclass
class Quad:
    """Four corners, clockwise from top-left: tl, tr, br, bl."""
    pts: list[tuple[float, float]]

    @classmethod
    def rect(cls, x0, y0, x1, y1):
        return cls([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])

    def bbox(self):
        xs = [p[0] for p in self.pts]
        ys = [p[1] for p in self.pts]
        return min(xs), min(ys), max(xs), max(ys)

    def scaled(self, s):
        return Quad([(x * s, y * s) for x, y in self.pts])

    def jittered(self, rng, amount):
        return Quad([(x + rng.gauss(0, amount), y + rng.gauss(0, amount)) for x, y in self.pts])

    def expanded(self, top, right, bottom, left):
        (tlx, tly), (trx, try_), (brx, bry), (blx, bly) = self.pts
        return Quad([(tlx - left, tly - top), (trx + right, try_ - top),
                     (brx + right, bry + bottom), (blx - left, bly + bottom)])


def _fit(aspect, box_w, box_h):
    if box_w / box_h > aspect:
        return box_h * aspect, box_h
    return box_w, box_w / aspect


def layout_windows(sizes: list[tuple[int, int]], style: dict, w: int, h: int) -> list[Quad]:
    """Return one opening per photo, in canvas pixels, before imperfections."""
    if style["style"] == "none":
        if len(sizes) == 2:
            return [Quad.rect(0, 0, w / 2, h), Quad.rect(w / 2, 0, w, h)]
        return [Quad.rect(0, 0, w, h)]

    b = style["border"] * h
    bw = style["bottom_weight"] * h
    ax0, ay0, ax1, ay1 = b, b, w - b, h - b - bw
    aw, ah = ax1 - ax0, ay1 - ay0

    if len(sizes) == 2:
        gap = style["portrait_gap"] * h
        if style["window"] == "fill":
            cw = (aw - gap) / 2
            return [Quad.rect(ax0, ay0, ax0 + cw, ay1), Quad.rect(ax1 - cw, ay0, ax1, ay1)]
        dims = [_fit(sw / sh, (aw - gap) / 2, ah) for sw, sh in sizes]
        total = dims[0][0] + gap + dims[1][0]
        x = ax0 + (aw - total) / 2
        out = []
        for dw, dh in dims:
            y = ay0 + (ah - dh) / 2
            out.append(Quad.rect(x, y, x + dw, y + dh))
            x += dw + gap
        return out

    sw, sh = sizes[0]
    if style["window"] == "fill" and not is_portrait(sw, sh):
        return [Quad.rect(ax0, ay0, ax1, ay1)]
    dw, dh = _fit(sw / sh, aw, ah)
    x = ax0 + (aw - dw) / 2
    y = ay0 + (ah - dh) / 2
    return [Quad.rect(x, y, x + dw, y + dh)]


# --------------------------------------------------------------------------- textures

def _noise(rng: random.Random, size: tuple[int, int], sigma: float) -> Image.Image:
    """Seeded noise centred on 128 with roughly the given std-dev in levels."""
    w, h = size
    img = Image.frombytes("L", (w, h), rng.randbytes(w * h))
    scale = sigma / 73.9  # std of uniform 0..255
    return img.point(lambda v: max(0, min(255, round(128 + (v - 128) * scale))))


def _smooth_noise(rng, size, sigma, cell):
    """Low-frequency blotches (paper mottling) normalised to ~sigma levels."""
    w, h = size
    small = Image.frombytes("L", (max(2, w // cell), max(2, h // cell)),
                            rng.randbytes(max(2, w // cell) * max(2, h // cell)))
    big = small.resize((w, h), Image.BICUBIC).filter(ImageFilter.GaussianBlur(cell * 0.6))
    stat = ImageStat.Stat(big)
    mean, std = stat.mean[0], max(stat.stddev[0], 0.01)
    return big.point(lambda v: max(0, min(255, round(128 + (v - mean) * sigma / std))))


def _gradient(size, angle_deg, amplitude):
    """Linear light falloff, brighter toward the light, centred on 128."""
    w, h = size
    # linear_gradient brightens downward; rotate so it brightens toward the light
    grad = Image.linear_gradient("L").rotate(angle_deg + 90, resample=Image.BICUBIC,
                                             expand=False, fillcolor=128)
    grad = grad.crop((48, 48, 208, 208)).resize((w, h), Image.BICUBIC)
    return grad.point(lambda v: round(128 + (v - 128) * amplitude / 80))


def _add_signed(img: Image.Image, offset_l: Image.Image) -> Image.Image:
    """img + (offset - 128) per channel, clipped."""
    rgb = Image.merge("RGB", (offset_l, offset_l, offset_l))
    return ImageChops.add(img, rgb, scale=1.0, offset=-128)


def _combine(*layers):
    out = layers[0]
    for layer in layers[1:]:
        out = ImageChops.add(out, layer, scale=1.0, offset=-128)
    return out


# --------------------------------------------------------------------------- photo

def cover(photo: Image.Image, w: int, h: int) -> Image.Image:
    """Scale and crop to exactly w x h. Tall photos crop a little above centre (faces)."""
    w, h = max(1, round(w)), max(1, round(h))
    scale = max(w / photo.width, h / photo.height)
    nw, nh = max(w, round(photo.width * scale)), max(h, round(photo.height * scale))
    resized = photo.resize((nw, nh), Image.LANCZOS)
    left = (nw - w) // 2
    top = round((nh - h) * (0.4 if photo.height > photo.width else 0.5))
    return resized.crop((left, top, left + w, top + h))


# --------------------------------------------------------------------------- main entry

def render(photos: list[Image.Image], style: dict | None = None, size: tuple[int, int] = CANVAS,
           key: str = "") -> Image.Image:
    """Compose 1 or 2 RGB photos onto a mat. `key` (usually the file paths) seeds the variation."""
    st = normalize_style(style)
    w, h = size
    rng = random.Random(style_seed(st, key))
    k = st["imperfection"]

    windows = layout_windows([p.size for p in photos], st, w, h)

    if st["style"] == "none":
        canvas = Image.new("RGB", (w, h), (0, 0, 0))
        for photo, win in zip(photos, windows):
            x0, y0, x1, y1 = win.bbox()
            canvas.paste(cover(photo, x1 - x0, y1 - y0), (round(x0), round(y0)))
        return canvas

    # ---- mat surface
    base = list(hex_to_rgb(st["mat_color"]))
    drift = k * st["tint_drift"]
    shift = rng.gauss(0, 1.2 * drift)
    base = [max(0, min(255, round(c + shift + rng.gauss(0, 1.5 * drift)))) for c in base]
    mat = Image.new("RGB", (w, h), tuple(base))

    light = st["light_angle"] + rng.gauss(0, 6 * k)
    layers = [_gradient((w, h), light, 1.5 + 3.0 * st["shadow"])]
    if k * st["grain"] > 0:
        layers.append(_noise(rng, (w, h), 3.2 * k * st["grain"] * max(0.5, h / 2160))
                      .filter(ImageFilter.GaussianBlur(0.55 * h / 2160)))
    if k * st["mottle"] > 0:
        layers.append(_smooth_noise(rng, (w, h), 2.0 * k * st["mottle"], max(8, h // 24)))
    texture = _combine(*layers)
    mat = _add_signed(mat, texture)
    _draw_fibers(mat, rng, base, k * st["fibers"], h)

    # ---- openings, with hand-cut wobble
    wobble = k * st["cut_wobble"]
    inner = []
    for win in windows:
        dx, dy = rng.gauss(0, 0.0012 * h * wobble), rng.gauss(0, 0.0012 * h * wobble)
        q = Quad([(x + dx, y + dy) for x, y in win.pts])
        inner.append(q.jittered(rng, 0.0007 * h * wobble))

    bevel_px = st["bevel"] * h if st["style"] == "bevel" else 0
    outer = []
    for q in inner:
        sides = [max(0.0, bevel_px * (1 + rng.gauss(0, 0.12 * wobble))) for _ in range(4)]
        outer.append(q.expanded(*sides).jittered(rng, 0.0004 * h * wobble))

    ss = 2  # supersample masks for anti-aliased cut edges
    inner_mask = _poly_mask((w, h), [q.pts for q in inner], ss)
    canvas = mat

    if bevel_px > 0:
        canvas = _apply_bevel(canvas, inner, outer, st, light, rng, k, ss)
        _draw_overcuts(canvas, outer, rng, k * st["cut_wobble"], h)

    if st["emboss_line"]:
        _draw_emboss(canvas, outer, st, light, h)

    # ---- photos, with the mat's shadow falling on them
    photo_layer = Image.new("RGB", (w, h), (0, 0, 0))
    for photo, q in zip(photos, inner):
        x0, y0, x1, y1 = q.bbox()
        x0, y0 = math.floor(x0), math.floor(y0)
        x1, y1 = math.ceil(x1), math.ceil(y1)
        photo_layer.paste(cover(photo, x1 - x0, y1 - y0), (x0, y0))

    if st["shadow"] > 0:
        photo_layer = _cast_shadow(photo_layer, inner_mask, light, st["shadow"], h)

    canvas.paste(photo_layer, (0, 0), inner_mask)
    return canvas


def _poly_mask(size, polys, ss):
    w, h = size
    big = Image.new("L", (w * ss, h * ss), 0)
    d = ImageDraw.Draw(big)
    for pts in polys:
        d.polygon([(x * ss, y * ss) for x, y in pts], fill=255)
    return big.resize((w, h), Image.BOX)


def _apply_bevel(canvas, inner, outer, st, light, rng, k, ss):
    w, h = canvas.size
    lx, ly = math.cos(math.radians(light)), -math.sin(math.radians(light))
    # Bevel faces lean in toward the opening: top face looks down, left looks right, ...
    normals = {"top": (0, 1), "right": (-1, 0), "bottom": (0, -1), "left": (1, 0)}
    contrast = st["bevel_contrast"]
    shades = {}
    for side, (nx, ny) in normals.items():
        lit = nx * lx + ny * ly                      # -1..1
        shades[side] = 1.0 - contrast * 0.13 * (1 - lit) + rng.gauss(0, 0.006 * k)
    peak = max(shades.values())
    mean = sum(shades.values()) / 4

    big = Image.new("L", (w * ss, h * ss), round(255 * mean / peak))
    d = ImageDraw.Draw(big)
    for qi, qo in zip(inner, outer):
        i = [(x * ss, y * ss) for x, y in qi.pts]
        o = [(x * ss, y * ss) for x, y in qo.pts]
        faces = {"top": [o[0], o[1], i[1], i[0]], "right": [o[1], o[2], i[2], i[1]],
                 "bottom": [o[2], o[3], i[3], i[2]], "left": [o[3], o[0], i[0], i[3]]}
        for side, poly in faces.items():
            d.polygon(poly, fill=round(255 * shades[side] / peak))
    shade = big.resize((w, h), Image.BOX)
    del big, d

    core = Image.new("RGB", (w, h), hex_to_rgb(st["core_color"]))
    if k * st["grain"] > 0:
        core = _add_signed(core, _noise(rng, (w, h), 2.0 * k * st["grain"]))
    # shade is normalised so the best-lit face shows the true core colour
    lit_core = ImageChops.multiply(core, Image.merge("RGB", (shade, shade, shade)))

    outer_mask = _poly_mask((w, h), [q.pts for q in outer], ss)
    canvas.paste(lit_core, (0, 0), outer_mask)
    return canvas


def _cast_shadow(photo_layer, inner_mask, light, depth, h):
    w = photo_layer.width
    lx, ly = math.cos(math.radians(light)), -math.sin(math.radians(light))
    outside = ImageOps.invert(inner_mask)

    dist = (0.002 + 0.004 * depth) * h
    shifted = Image.new("L", outside.size, 255)
    shifted.paste(outside, (round(-lx * dist), round(-ly * dist)))
    cast = shifted.filter(ImageFilter.GaussianBlur(dist * 1.2))
    contact = outside.filter(ImageFilter.GaussianBlur(max(1.0, 0.0012 * h)))
    shadow = ImageChops.lighter(cast.point(lambda v: round(v * 0.55 * depth)),
                                contact.point(lambda v: round(v * 0.35 * depth)))
    return Image.composite(Image.new("RGB", (w, h), (0, 0, 0)), photo_layer, shadow)


def _draw_fibers(mat, rng, base, amount, h):
    if amount <= 0:
        return
    w = mat.width
    layer = Image.new("RGBA", mat.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    count = round(90 * amount * (w * h) / (3840 * 2160))
    for _ in range(count):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        length = rng.uniform(0.003, 0.012) * h
        ang = rng.uniform(0, math.pi)
        bend = rng.gauss(0, 0.25)
        pts = []
        for t in (0, 0.5, 1):
            a = ang + bend * t
            pts.append((x + math.cos(a) * length * t, y + math.sin(a) * length * t))
        tone = rng.choice([-1, -1, -1, 1])
        delta = rng.uniform(6, 14) * tone
        tint = rng.choice([(0, 0, 0), (0, 0, 0), (6, -2, -6), (-4, -2, 6)])
        color = tuple(max(0, min(255, round(c + delta + t))) for c, t in zip(base, tint))
        d.line(pts, fill=color + (round(rng.uniform(40, 90)),), width=max(1, round(h / 1800)))
    layer = layer.filter(ImageFilter.GaussianBlur(0.5 * h / 2160))
    mat.paste(layer, (0, 0), layer)


def _draw_overcuts(canvas, outer, rng, amount, h):
    """Mat cutters often run a hair past the corner; leave a faint score line."""
    if amount < 0.15:
        return
    d = ImageDraw.Draw(canvas, "RGBA")
    for q in outer:
        tl, tr, br, bl = q.pts
        corners = [(tl, (-1, 0), (0, -1)), (tr, (1, 0), (0, -1)),
                   (br, (1, 0), (0, 1)), (bl, (-1, 0), (0, 1))]
        for (cx, cy), hdir, vdir in corners:
            for dx, dy in (hdir, vdir):
                if rng.random() > 0.35 * amount + 0.1:
                    continue
                length = rng.uniform(0.0015, 0.005) * h * amount
                d.line([(cx, cy), (cx + dx * length, cy + dy * length)],
                       fill=(0, 0, 0, round(28 * amount + 8)), width=1)


def _draw_emboss(canvas, outer, st, light, h):
    off = st["emboss_offset"] * h
    lx, ly = math.cos(math.radians(light)), -math.sin(math.radians(light))
    width = max(1, round(0.0011 * h))
    hi = Image.new("L", canvas.size, 0)
    lo = Image.new("L", canvas.size, 0)
    dh, dl = ImageDraw.Draw(hi), ImageDraw.Draw(lo)
    shift = max(1.0, 0.0008 * h)
    for q in outer:
        ring = q.expanded(off, off, off, off).pts
        ring = ring + [ring[0]]
        # a debossed groove: the edge facing the light is shadowed, the far edge catches light
        dl.line([(x + lx * shift, y + ly * shift) for x, y in ring], fill=255, width=width)
        dh.line([(x - lx * shift, y - ly * shift) for x, y in ring], fill=255, width=width)
    blur = ImageFilter.GaussianBlur(0.0006 * h)
    canvas.paste((255, 255, 255), (0, 0), hi.filter(blur).point(lambda v: round(v * 0.45)))
    canvas.paste((0, 0, 0), (0, 0), lo.filter(blur).point(lambda v: round(v * 0.16)))
