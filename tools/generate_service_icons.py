"""
Generate local service icons used by the accounts screen.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


OUT = Path(__file__).resolve().parents[1] / "app" / "assets" / "service_icons"
SIZE = 96


def _font(size: int, bold: bool = True):
    candidates = [
        "C:/Windows/Fonts/seguisb.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _center_text(draw: ImageDraw.ImageDraw, text: str, font, fill, xy=(48, 48)):
    bbox = draw.textbbox((0, 0), text, font=font)
    x = xy[0] - (bbox[2] - bbox[0]) / 2
    y = xy[1] - (bbox[3] - bbox[1]) / 2 - 2
    draw.text((x, y), text, font=font, fill=fill)


def youtube():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((10, 22, 86, 74), radius=14, fill="#ff0033")
    draw.polygon([(42, 35), (42, 61), (64, 48)], fill="white")
    img.save(OUT / "youtube.png")


def tiktok():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((8, 8, 88, 88), fill="#111111")
    font = _font(54)
    _center_text(draw, "♪", font, "#25f4ee", (45, 48))
    _center_text(draw, "♪", font, "#fe2c55", (51, 52))
    _center_text(draw, "♪", font, "white", (48, 50))
    img.save(OUT / "tiktok.png")


def twitch():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((14, 14, 82, 72), radius=8, fill="#9146ff")
    draw.polygon([(26, 72), (26, 86), (42, 72)], fill="#9146ff")
    draw.rectangle((30, 30, 38, 52), fill="white")
    draw.rectangle((56, 30, 64, 52), fill="white")
    draw.rectangle((26, 20, 70, 26), fill="#ffffff")
    img.save(OUT / "twitch.png")


def soundcloud():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((8, 8, 88, 88), radius=22, fill="#ff7700")
    draw.rectangle((20, 52, 42, 70), fill="white")
    for x, h in [(20, 10), (26, 20), (32, 26), (38, 34)]:
        draw.rounded_rectangle((x, 70 - h, x + 4, 70), radius=2, fill="white")
    draw.ellipse((38, 38, 66, 66), fill="white")
    draw.ellipse((56, 44, 78, 66), fill="white")
    draw.rectangle((40, 56, 78, 66), fill="white")
    img.save(OUT / "soundcloud.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    youtube()
    tiktok()
    twitch()
    soundcloud()
    print(OUT)


if __name__ == "__main__":
    main()
