"""Draw the Solar Clock web page icon: approved idea A, "Sun Path".

Writes solar_clock/web/icons/: icon.svg, favicon-32.png, apple-touch-icon.png,
icon-192.png, icon-512.png and icon-maskable-512.png. The geometry, in
100 x 100 units, is the spec's (docs/superpowers/specs/
2026-10-08-web-page-design.md, "App icon"). PNGs are drawn at 4x and scaled
down for smooth edges; homelab has no SVG rasteriser.

    ./venv/bin/python tools/make_icons.py
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "solar_clock" / "web" / "icons"
SUPERSAMPLE = 4

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]
Point = tuple[float, float]

BACKGROUND: RGB = (0, 0, 0)
HORIZON: RGB = (128, 128, 128)
DAY: RGB = (255, 220, 50)
NIGHT: RGB = (60, 60, 168)
GLOW: RGB = (255, 140, 0)
SUN_AT: Point = (42, 34.6)


def curve_y(x: float) -> float:
    """The sun's path: above the horizon (y = 62) between x = 30 and x = 80."""
    s = math.sin(2 * math.pi * (x - 30) / 100)
    return 62 - 40 * s if s > 0 else 62 - 22 * s


def curve(x0: float, x1: float, step: float = 0.5) -> list[Point]:
    count = round((x1 - x0) / step)
    return [(x0 + i * step, curve_y(x0 + i * step)) for i in range(count + 1)]


# (points, colour, stroke width), drawn in this order
SEGMENTS: list[tuple[list[Point], RGB, float]] = [
    (curve(8, 30), NIGHT, 4.5),
    (curve(80, 92), NIGHT, 4.5),
    (curve(30, 80), DAY, 5.0),
]


def hex_color(rgb: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def svg() -> str:
    def path(points: list[Point]) -> str:
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)

    lines = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">',
        f'<rect width="100" height="100" fill="{hex_color(BACKGROUND)}"/>',
        f'<line x1="6" y1="62" x2="94" y2="62" stroke="{hex_color(HORIZON)}" stroke-width="2.5"/>',
    ]
    for points, colour, width in SEGMENTS:
        lines.append(
            f'<path d="{path(points)}" fill="none" stroke="{hex_color(colour)}" '
            f'stroke-width="{width:g}" stroke-linecap="round"/>'
        )
    x, y = SUN_AT
    lines.append(
        f'<circle cx="{x:g}" cy="{y:g}" r="11" fill="{hex_color(GLOW)}" opacity="0.35"/>'
    )
    lines.append(f'<circle cx="{x:g}" cy="{y:g}" r="7.5" fill="{hex_color(DAY)}"/>')
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def png(size: int, scale: float = 1.0) -> Image.Image:
    """The icon at `size` px; `scale` < 1 shrinks the picture about the centre."""
    big = size * SUPERSAMPLE
    unit = big / 100

    def at(x: float, y: float) -> Point:
        return (((x - 50) * scale + 50) * unit, ((y - 50) * scale + 50) * unit)

    def px(length: float) -> float:
        return length * scale * unit

    def disc(
        draw: ImageDraw.ImageDraw, centre: Point, radius: float, fill: RGBA | RGB
    ) -> None:
        cx, cy = centre
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=fill)

    image = Image.new("RGBA", (big, big), BACKGROUND + (255,))
    draw = ImageDraw.Draw(image)
    draw.line([at(6, 62), at(94, 62)], fill=HORIZON, width=max(1, round(px(2.5))))
    for points, colour, width in SEGMENTS:
        scaled = [at(x, y) for x, y in points]
        draw.line(scaled, fill=colour, width=max(1, round(px(width))))
        for point in scaled:  # round joins and caps; Pillow's own joins notch
            disc(draw, point, px(width) / 2, colour)

    glow = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    disc(ImageDraw.Draw(glow), at(*SUN_AT), px(11), GLOW + (round(0.35 * 255),))
    image = Image.alpha_composite(image, glow)
    disc(ImageDraw.Draw(image), at(*SUN_AT), px(7.5), DAY)
    return image.resize((size, size), Image.Resampling.LANCZOS).convert("RGB")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "icon.svg").write_text(svg())
    outputs = {
        "favicon-32.png": png(32),
        "apple-touch-icon.png": png(180),
        "icon-192.png": png(192),
        "icon-512.png": png(512),
        "icon-maskable-512.png": png(512, scale=0.8),
    }
    for name, image in outputs.items():
        image.save(OUT / name, optimize=True)
    print(f"Wrote {len(outputs) + 1} files to {OUT}")


if __name__ == "__main__":
    main()
