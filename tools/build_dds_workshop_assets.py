from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
PNG = ASSETS / "DDSWorkshop_RSS.png"
ICO = ASSETS / "DDSWorkshop_RSS.ico"
SIZES = [16, 24, 32, 48, 64, 128, 256]
CANVAS = 256


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default()


def text_center(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, fnt, fill, stroke_width=0, stroke_fill=None) -> None:
    bbox = draw.textbbox((0, 0), text, font=fnt, stroke_width=stroke_width)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x0, y0, x1, y1 = box
    x = x0 + (x1 - x0 - tw) / 2 - bbox[0]
    y = y0 + (y1 - y0 - th) / 2 - bbox[1]
    draw.text((x, y), text, font=fnt, fill=fill, stroke_width=stroke_width, stroke_fill=stroke_fill)


def make_icon() -> Image.Image:
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    mask = Image.new("L", (CANVAS, CANVAS), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((10, 10, 246, 246), radius=42, fill=255)
    tile = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    tile_draw = ImageDraw.Draw(tile)
    for y in range(10, 247):
        t = (y - 10) / 236
        r = int(31 + 18 * t)
        g = int(44 + 16 * t)
        b = int(58 + 28 * t)
        tile_draw.line([(10, y), (246, y)], fill=(r, g, b, 255))
    img.alpha_composite(Image.composite(tile, Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0)), mask))

    # RSS/ORZIP-family gold border.
    draw.rounded_rectangle((10, 10, 246, 246), radius=42, outline=(226, 150, 61, 255), width=7)
    draw.rounded_rectangle((22, 22, 234, 234), radius=32, outline=(255, 221, 141, 125), width=3)

    # Rail perspective, retained from the ORZIP family style.
    rail_shadow = (7, 16, 22, 190)
    rail = (235, 239, 231, 255)
    draw.line([(69, 204), (103, 76)], fill=rail_shadow, width=16)
    draw.line([(187, 204), (153, 76)], fill=rail_shadow, width=16)
    draw.line([(69, 204), (103, 76)], fill=rail, width=9)
    draw.line([(187, 204), (153, 76)], fill=rail, width=9)
    for y, w in [(195, 124), (171, 100), (147, 76), (123, 58), (101, 42)]:
        cx = 128
        draw.rounded_rectangle((cx - w // 2, y - 5, cx + w // 2, y + 5), radius=3, fill=(213, 132, 48, 255))
        draw.line([(cx - w // 2 + 5, y + 5), (cx + w // 2 - 5, y + 5)], fill=(93, 48, 19, 140), width=1)

    # Texture tile: checker/photo source being turned into a DDS asset.
    draw.rounded_rectangle((48, 40, 196, 136), radius=12, fill=(244, 239, 224, 255), outline=(23, 35, 47, 230), width=4)
    colors = [(123, 75, 47, 255), (219, 190, 124, 255), (86, 123, 91, 255), (206, 207, 188, 255)]
    for row in range(2):
        for col in range(4):
            x0 = 62 + col * 28
            y0 = 58 + row * 28
            draw.rectangle((x0, y0, x0 + 28, y0 + 28), fill=colors[(row + col) % len(colors)])
    draw.rounded_rectangle((137, 53, 183, 94), radius=5, fill=(40, 54, 67, 230))
    text_center(draw, (137, 51, 183, 94), "DDS", font(17, True), fill=(255, 230, 154, 255))

    text_center(draw, (36, 132, 220, 176), "DDS", font(44, True), fill=(255, 241, 203, 255), stroke_width=3, stroke_fill=(34, 22, 17, 220))
    text_center(draw, (24, 172, 232, 216), "Workshop", font(31, True), fill=(255, 185, 78, 255), stroke_width=3, stroke_fill=(34, 22, 17, 230))

    return img


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    icon = make_icon()
    icon.save(PNG)
    icon.save(ICO, sizes=[(size, size) for size in SIZES])
    print(PNG)
    print(ICO)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
