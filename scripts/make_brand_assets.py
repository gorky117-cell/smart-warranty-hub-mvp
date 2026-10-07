"""Make the brand files in static/brand/: favicon (SVG + ICO), apple-touch icon and the share image.

Run: python scripts/make_brand_assets.py  (needs Pillow). The files are committed, so this only needs to run
again when the mark or the headline changes. Fonts: Inter Bold if installed, otherwise the first font found
in FONT_CANDIDATES, otherwise Pillow's built-in font.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "brand"

NAVY = (15, 27, 61)
NAVY_2 = (30, 58, 138)
TEAL_LIGHT = (94, 234, 212)
WHITE = (255, 255, 255)
SOFT = (226, 232, 248)

HEADLINE = "The after-purchase bridge between you and your brands."
WORDMARK = "Smart Warranty Hub"

FONT_CANDIDATES = [
    "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]

FAVICON_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
    '<rect width="32" height="32" rx="8" fill="#0F1B3D"/>'
    '<path d="M16 6l8 3v6c0 5-3.4 9.3-8 11-4.6-1.7-8-6-8-11V9l8-3z" fill="none" stroke="#FFFFFF" '
    'stroke-width="2" stroke-linejoin="round"/>'
    '<path d="M12.2 16.2l2.6 2.6 5-5.2" fill="none" stroke="#5EEAD4" stroke-width="2.2" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>\n'
)


def _font(size: int):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _cubic(p0, p1, p2, p3, steps: int = 16):
    out = []
    for i in range(1, steps + 1):
        t = i / steps
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return out


def _shield_points(scale: float):
    """The shield outline of the 32-unit SVG mark (same curves as favicon.svg)."""
    pts = [(16, 6), (24, 9), (24, 15)]
    pts += _cubic((24, 15), (24, 20), (20.6, 24.3), (16, 26))
    pts += _cubic((16, 26), (11.4, 24.3), (8, 20), (8, 15))
    pts += [(8, 9), (16, 6), (24, 9)]  # repeat the first edge so the line closes without a notch
    return [(x * scale, y * scale) for x, y in pts]


def draw_mark(size: int, *, background: bool = True) -> Image.Image:
    s = 4  # draw large, then shrink for smooth edges
    big = size * s
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    unit = big / 32
    if background:
        d.rounded_rectangle([0, 0, big - 1, big - 1], radius=8 * unit, fill=NAVY)
    d.line(_shield_points(unit), fill=WHITE, width=max(1, round(2 * unit)), joint="curve")
    tick = [(12.2 * unit, 16.2 * unit), (14.8 * unit, 18.8 * unit), (19.8 * unit, 13.6 * unit)]
    d.line(tick, fill=TEAL_LIGHT, width=max(1, round(2.2 * unit)), joint="curve")
    return img.resize((size, size), Image.LANCZOS)


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def share_image() -> Image.Image:
    w, h = 1200, 630
    img = Image.new("RGB", (w, h), NAVY)
    # Navy gradient, left to right.
    grad = Image.new("RGB", (w, 1))
    for x in range(w):
        t = x / (w - 1)
        grad.putpixel((x, 0), tuple(round(NAVY[i] + (NAVY_2[i] - NAVY[i]) * t) for i in range(3)))
    img.paste(grad.resize((w, h)))
    d = ImageDraw.Draw(img)
    mark = draw_mark(72)
    img.paste(mark, (80, 72), mark)
    d.text((172, 88), WORDMARK, font=_font(36), fill=WHITE)
    head_font = _font(64)
    y = 220
    for line in _wrap(d, HEADLINE, head_font, w - 160):
        d.text((80, y), line, font=head_font, fill=WHITE)
        y += 80
    d.text((80, h - 96), "Warranty  ·  Care tips  ·  Early warnings  ·  Claims", font=_font(28), fill=SOFT)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "favicon.svg").write_text(FAVICON_SVG, encoding="utf-8")
    draw_mark(256).save(OUT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    draw_mark(180).save(OUT / "apple-touch-icon.png")
    share_image().save(OUT / "og-image.png", optimize=True)
    for name in ("favicon.svg", "favicon.ico", "apple-touch-icon.png", "og-image.png"):
        print(name, (OUT / name).stat().st_size, "bytes")


if __name__ == "__main__":
    main()
