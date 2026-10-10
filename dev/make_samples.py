"""Generate a few synthetic test photos (landscape + portraits) into dev/media."""
import os
import sys

from PIL import Image, ImageDraw

out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "media")
os.makedirs(out, exist_ok=True)

specs = [("landscape-sunset.jpg", (3000, 2000), [(250, 120, 60), (40, 30, 90)]),
         ("landscape-sea.jpg", (4032, 3024), [(120, 190, 230), (10, 60, 110)]),
         ("portrait-forest.jpg", (2000, 3000), [(60, 140, 70), (10, 40, 20)]),
         ("portrait-dusk.jpg", (3024, 4032), [(230, 160, 200), (50, 30, 80)])]
for name, (w, h), (top, bottom) in specs:
    img = Image.new("RGB", (w, h))
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        d.line([(0, y), (w, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    d.ellipse([w * 0.35, h * 0.3, w * 0.65, h * 0.3 + w * 0.3], fill=(255, 240, 200))
    d.rectangle([0, h * 0.75, w, h], fill=tuple(c // 2 for c in bottom))
    img.save(os.path.join(out, name), quality=90)
print("wrote samples to", out)
