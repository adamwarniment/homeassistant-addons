from PIL import Image, ImageChops

from frameart import renderer


def photo(w, h, color=(200, 80, 40)):
    return Image.new("RGB", (w, h), color)


def test_output_is_canvas_size():
    out = renderer.render([photo(3000, 2000)], {}, size=(960, 540), key="a")
    assert out.size == (960, 540) and out.mode == "RGB"


def test_same_key_renders_identically():
    a = renderer.render([photo(3000, 2000)], {"imperfection": 1}, size=(640, 360), key="x")
    b = renderer.render([photo(3000, 2000)], {"imperfection": 1}, size=(640, 360), key="x")
    assert ImageChops.difference(a, b).getbbox() is None


def test_vary_per_photo_changes_flaws():
    st = {"imperfection": 1, "vary_per_photo": True}
    a = renderer.render([photo(3000, 2000)], st, size=(640, 360), key="one.jpg")
    b = renderer.render([photo(3000, 2000)], st, size=(640, 360), key="two.jpg")
    assert ImageChops.difference(a, b).getbbox() is not None


def test_zero_imperfection_gives_flat_mat_corner():
    st = {"imperfection": 0, "shadow": 0}
    out = renderer.render([photo(3000, 2000)], st, size=(640, 360), key="a")
    corner = out.crop((2, 2, 30, 30))
    assert len(corner.getcolors()) <= 2  # solid mat colour (gradient off with shadow 0)


def test_mat_surrounds_photo():
    st = {"mat_color": "#FFFFFF", "imperfection": 0, "shadow": 0}
    out = renderer.render([photo(3000, 2000, (255, 0, 0))], st, size=(960, 540), key="a")
    assert out.getpixel((5, 5))[1] > 200          # mat
    r, g, b = out.getpixel((480, 270))
    assert r > 200 and g < 60                     # photo in the middle


def test_portrait_pair_layout_side_by_side():
    wins = renderer.layout_windows([(2000, 3000), (2000, 3000)],
                                   renderer.normalize_style({"window": "match"}), 3840, 2160)
    (l0, _, l1, _), (r0, _, r1, _) = wins[0].bbox(), wins[1].bbox()
    assert l1 < r0 and abs((l1 - l0) - (r1 - r0)) < 1
    assert abs(l0 - (3840 - r1)) < 1  # centred


def test_single_portrait_is_not_cropped_to_landscape():
    win = renderer.layout_windows([(2000, 3000)], renderer.normalize_style({}), 3840, 2160)[0]
    x0, y0, x1, y1 = win.bbox()
    assert (y1 - y0) > (x1 - x0)


def test_normalize_clamps_and_ignores_junk():
    st = renderer.normalize_style({"imperfection": 9, "border": "abc", "style": "weird", "nope": 1})
    assert st["imperfection"] == 1.0
    assert st["border"] == renderer.DEFAULT_STYLE["border"]
    assert st["style"] == "bevel"
    assert "nope" not in st
