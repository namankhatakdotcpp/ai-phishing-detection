"""Generate placeholder [PROJECT_NAME] extension icons (16/48/128px).

These are simple, programmatically-drawn shield icons -- adequate to
make the extension installable/presentable and to unblock Web Store
submission's icon requirement, but a real design pass (a designer, or at
least a hand-crafted vector) should replace these before public release.
Stated as a placeholder deliberately, not presented as final art.

Usage:
    python scripts/generate_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent.parent / "extension" / "icons"
SIZES = [16, 48, 128]

BG = (26, 26, 26, 255)  # matches popup.css's dark button color
SHIELD_FILL = (255, 255, 255, 255)
ACCENT = (160, 36, 25, 255)  # matches popup.css's --high color


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    pad = max(1, size // 12)
    draw.rounded_rectangle([pad, pad, size - pad, size - pad], radius=size // 5, fill=BG)

    # Simple shield silhouette: a rounded-top pentagon, centered.
    cx = size / 2
    top = size * 0.22
    bottom = size * 0.82
    left = size * 0.30
    right = size * 0.70
    mid = size * 0.60
    shield_points = [
        (left, top),
        (right, top),
        (right, mid),
        (cx, bottom),
        (left, mid),
    ]
    draw.polygon(shield_points, fill=SHIELD_FILL)

    # Small accent dot to hint at the "risk indicator" concept without
    # trying to render legible text at 16px.
    if size >= 48:
        r = size * 0.06
        draw.ellipse([cx - r, size * 0.42 - r, cx + r, size * 0.42 + r], fill=ACCENT)

    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        icon = draw_icon(size)
        out_path = OUT_DIR / f"icon{size}.png"
        icon.save(out_path)
        print(f"wrote {out_path} ({size}x{size})")


if __name__ == "__main__":
    main()
