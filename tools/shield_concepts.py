"""RamWarden shield icon: three takes on Mikey's shield + RAM-stick design, rendered at real
icon sizes so the line weight / fill choice can be judged where icons live.

Run: python tools/shield_concepts.py  ->  tools/shield_concepts.png
"""
import io
import pathlib

import resvg_py
from PIL import Image, ImageDraw, ImageFont

OUT = pathlib.Path(__file__).resolve().parent / "shield_concepts.png"
CREAM, BG, BG2, GREEN, GREEN_DK, GREEN_LT = "#efe7d2", "#141414", "#262626", "#4caf50", "#2e7d32", "#8bf58f"

SHIELD = "M256 70 C300 92 356 104 404 104 L404 236 C404 336 342 404 256 446 C170 404 108 336 108 236 L108 104 C156 104 212 92 256 70 Z"


def stick(fill, holes, pins):
    """A RAM stick rotated -35 deg about the shield centre: board, chips (holes) and gold-ish pins."""
    chips = "".join(f'<rect x="{x}" y="-22" width="34" height="30" rx="3" fill="{holes}"/>' for x in (-92, -46, 0, 46))
    teeth = "".join(f'<rect x="{x}" y="22" width="7" height="16" fill="{pins}"/>' for x in range(-104, 112, 14))
    notch = f'<rect x="-12" y="18" width="14" height="22" fill="{holes}"/>'
    return (f'<g transform="translate(256 252) rotate(-35)">'
            f'<rect x="-118" y="-38" width="236" height="62" rx="8" fill="{fill}"/>{chips}{teeth}{notch}</g>')


def plate(inner):
    """The rounded dark app tile behind each take."""
    return (f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG2}"/>'
            f'<stop offset="1" stop-color="{BG}"/></linearGradient>'
            f'<linearGradient id="gr" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{GREEN_LT}"/>'
            f'<stop offset="1" stop-color="{GREEN_DK}"/></linearGradient></defs>'
            f'<rect width="512" height="512" rx="112" fill="url(#bg)"/>{inner}')


TAKES = [
    ("A. Your design, bolder lines", plate(
        f'<path d="{SHIELD}" fill="none" stroke="{CREAM}" stroke-width="30" stroke-linejoin="round"/>'
        + stick(CREAM, BG, CREAM))),
    ("B. Filled shield, stick cut out", plate(
        f'<path d="{SHIELD}" fill="url(#gr)"/>' + stick(BG, GREEN, BG))),
    ("C. Green outline, cream stick", plate(
        f'<path d="{SHIELD}" fill="none" stroke="url(#gr)" stroke-width="30" stroke-linejoin="round"/>'
        + stick(CREAM, BG, CREAM))),
]


def render(svg, size):
    """One take at size x size."""
    doc = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="{size}" height="{size}">{svg}</svg>'
    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=doc, width=size, height=size)))).convert("RGBA")


def main():
    """Comparison sheet: each take at 256 / 64 / 48 / 32 / 24 / 16 on dark and light taskbar strips."""
    font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 26)
    small = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 18)
    row = 330
    sheet = Image.new("RGB", (1200, 30 + row * len(TAKES)), "#0f1115")
    d = ImageDraw.Draw(sheet)
    for i, (name, svg) in enumerate(TAKES):
        y = 25 + i * row
        d.text((40, y), name, font=font, fill="#e8ebef")
        big = render(svg, 256)
        sheet.paste(big, (40, y + 40), big)
        x = 340
        for s in (64, 48, 32, 24, 16):
            im = render(svg, s)
            sheet.paste(im, (x, y + 40 + 200 - s), im)
            d.text((x, y + 250), f"{s}px", font=small, fill="#98a2ad")
            x += s + 36
        for j, bgc in enumerate(("#202020", "#f3f3f3")):
            bx, by = 800, y + 60 + j * 100
            d.rounded_rectangle((bx, by, bx + 340, by + 64), 12, fill=bgc)
            for k, s in enumerate((24, 32, 24)):
                im = render(svg, s)
                sheet.paste(im, (bx + 40 + k * 90, by + 32 - s // 2), im)
        d.text((800, y + 35), "taskbar, light and dark", font=small, fill="#98a2ad")
    sheet.save(OUT)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
