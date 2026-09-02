"""One-off script: procedurally draws the extension's toolbar icon (a shield with a magnifying
glass) at each required size, since there's no designer asset to start from. Rerun only if the
icon design needs to change -- the output PNGs are what's actually committed and used."""

from pathlib import Path

from PIL import Image, ImageDraw

OUT_DIR = Path(__file__).resolve().parent.parent / "extension" / "icons"
BG = (37, 47, 79)  # deep indigo -- reads as "security" without being alarmist red
ACCENT = (255, 255, 255)


def draw_icon(size: int) -> Image.Image:
    scale = 4  # draw big, then downsample for clean anti-aliasing
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # rounded-square background
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=s * 0.22, fill=BG)

    # shield outline (simple polygon: pointed bottom, flat top with a notch)
    cx, top, bottom, half_w = s / 2, s * 0.16, s * 0.86, s * 0.28
    shield = [
        (cx - half_w, top),
        (cx + half_w, top),
        (cx + half_w, s * 0.5),
        (cx, bottom),
        (cx - half_w, s * 0.5),
    ]
    d.polygon(shield, outline=ACCENT, width=max(2, s // 24))

    # magnifying glass over the shield -- circle + handle
    glass_cx, glass_cy, r = cx - s * 0.03, s * 0.42, s * 0.14
    d.ellipse([glass_cx - r, glass_cy - r, glass_cx + r, glass_cy + r], outline=ACCENT, width=max(2, s // 26))
    handle_start = (glass_cx + r * 0.7, glass_cy + r * 0.7)
    handle_end = (glass_cx + r * 1.6, glass_cy + r * 1.6)
    d.line([handle_start, handle_end], fill=ACCENT, width=max(2, s // 22))

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for size in (16, 48, 128):
        icon = draw_icon(size)
        path = OUT_DIR / f"icon{size}.png"
        icon.save(path)
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
