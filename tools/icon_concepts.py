"""RamWarden icon concepts (mock-ups to choose from, not the final icon).

Each concept is an SVG drawn on a 512 grid, rendered with resvg and laid out on one sheet
at app size (256) and taskbar sizes (48, 32, 24) so they can be judged where icons live.

Run: python tools/icon_concepts.py   ->  tools/icon_concepts.png (+ one SVG per concept)
Needs: python -m pip install resvg-py pillow
"""
import io
import pathlib

import resvg_py
from PIL import Image, ImageDraw, ImageFont

OUT = pathlib.Path(__file__).resolve().parent / "icon_concepts"
GREEN, GREEN_LT, BG, BG2 = "#4caf50", "#8bf58f", "#141414", "#232323"
STONE, STONE_DK, STONE_LT = "#5b6168", "#3a3f45", "#7c838b"

PLATE = (f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG2}"/>'
         f'<stop offset="1" stop-color="{BG}"/></linearGradient>'
         f'<radialGradient id="glow"><stop offset="0" stop-color="{GREEN_LT}"/><stop offset=".55" stop-color="{GREEN}"/>'
         f'<stop offset="1" stop-color="{GREEN}" stop-opacity="0"/></radialGradient></defs>'
         f'<rect width="512" height="512" rx="112" fill="url(#bg)"/>')


def eyes(y, xs, w=46, h=16):
    """Glowing slit eyes: a soft halo plus a bright core."""
    out = ""
    for x in xs:
        out += f'<ellipse cx="{x}" cy="{y}" rx="{w}" ry="{h * 2.2}" fill="url(#glow)" opacity=".55"/>'
        out += f'<rect x="{x - w / 2}" y="{y - h / 2}" width="{w}" height="{h}" rx="{h / 2}" fill="{GREEN_LT}"/>'
    return out


# 1. Chip golem: a stone head whose jaw is a RAM stick (the gold contacts are its teeth).
GOLEM = PLATE + (
    f'<path d="M136 120 L376 120 L404 176 L404 330 L108 330 L108 176 Z" fill="{STONE}"/>'
    f'<path d="M136 120 L376 120 L404 176 L108 176 Z" fill="{STONE_LT}"/>'                     # brow ridge
    f'<path d="M108 176 L404 176 L404 196 L108 196 Z" fill="{STONE_DK}"/>'
    f'<path d="M200 140 L214 170 L204 196 M318 300 L336 270 L330 246" stroke="{STONE_DK}" stroke-width="7" fill="none" stroke-linecap="round"/>'
    + eyes(248, (196, 316)) +
    # the RAM-stick jaw: green PCB with chips and gold teeth
    f'<rect x="120" y="330" width="272" height="86" rx="10" fill="#1f6b33"/>'
    + "".join(f'<rect x="{x}" y="344" width="44" height="34" rx="4" fill="#111"/>' for x in (138, 196, 254, 312))
    + "".join(f'<rect x="{x}" y="392" width="10" height="38" rx="2" fill="#d6a640"/>' for x in range(134, 382, 18))
)

# 2. Warden helm: a knight's great helm, T-visor glowing, a chip badge on the brow.
HELM = PLATE + (
    f'<path d="M256 84 C350 84 402 140 402 230 L402 360 C402 404 372 430 330 430 L182 430 C140 430 110 404 110 360 L110 230 C110 140 162 84 256 84 Z" fill="{STONE}"/>'
    f'<path d="M256 84 C350 84 402 140 402 230 L402 248 L110 248 L110 230 C110 140 162 84 256 84 Z" fill="{STONE_LT}"/>'
    f'<rect x="246" y="96" width="20" height="320" fill="{STONE_DK}" opacity=".55"/>'           # centre ridge
    f'<rect x="132" y="236" width="248" height="34" rx="8" fill="#0b0b0b"/>'                    # T visor
    f'<rect x="240" y="236" width="32" height="120" rx="8" fill="#0b0b0b"/>'
    f'<ellipse cx="256" cy="253" rx="150" ry="40" fill="url(#glow)" opacity=".45"/>'
    f'<rect x="146" y="246" width="220" height="14" rx="7" fill="{GREEN_LT}"/>'
    + "".join(f'<circle cx="{x}" cy="{y}" r="7" fill="{STONE_DK}"/>' for x, y in ((150, 320), (362, 320), (150, 380), (362, 380)))
    + f'<rect x="226" y="140" width="60" height="44" rx="6" fill="{GREEN}"/>'
    + "".join(f'<rect x="{x}" y="184" width="6" height="12" fill="{GREEN}"/>' for x in (234, 248, 262, 276))
)

# 3. Sentinel: a golem's head and shoulders, a glowing memory-chip core in its chest.
SENTINEL = PLATE + (
    f'<path d="M80 470 L104 360 C112 326 140 308 176 304 L336 304 C372 308 400 326 408 360 L432 470 Z" fill="{STONE}"/>'
    f'<path d="M180 92 L332 92 L360 140 L352 270 L310 300 L202 300 L160 270 L152 140 Z" fill="{STONE_LT}"/>'
    f'<path d="M160 270 L202 300 L310 300 L352 270 L352 250 L160 250 Z" fill="{STONE}"/>'
    + eyes(196, (212, 300), w=40, h=14) +
    f'<circle cx="256" cy="398" r="70" fill="url(#glow)" opacity=".6"/>'
    f'<rect x="216" y="360" width="80" height="76" rx="8" fill="#0b0b0b" stroke="{GREEN_LT}" stroke-width="6"/>'
    + "".join(f'<rect x="{x}" y="346" width="8" height="14" fill="{GREEN_LT}"/><rect x="{x}" y="436" width="8" height="14" fill="{GREEN_LT}"/>' for x in (228, 244, 260, 276))
    + f'<rect x="236" y="380" width="40" height="36" rx="4" fill="{GREEN}"/>'
)

# 4. Hooded warden: a deep hood, the face in shadow, two eyes and a chip clasp at the throat.
HOOD = PLATE + (
    f'<path d="M256 70 C356 70 420 160 420 270 C420 360 400 420 380 460 L132 460 C112 420 92 360 92 270 C92 160 156 70 256 70 Z" fill="#2c3a2e"/>'
    f'<path d="M256 120 C328 120 372 186 372 262 C372 330 330 380 256 380 C182 380 140 330 140 262 C140 186 184 120 256 120 Z" fill="#070707"/>'
    f'<path d="M256 70 C300 70 340 92 366 126 C330 104 296 96 256 96 C216 96 182 104 146 126 C172 92 212 70 256 70 Z" fill="#3b4d3d"/>'
    + eyes(262, (210, 302), w=38, h=13) +
    f'<rect x="226" y="400" width="60" height="40" rx="6" fill="{GREEN}"/>'
    + "".join(f'<rect x="{x}" y="440" width="6" height="10" fill="{GREEN}"/>' for x in (234, 248, 262, 276))
)

CONCEPTS = [("1. Chip golem", GOLEM), ("2. Warden helm", HELM), ("3. Sentinel core", SENTINEL), ("4. Hooded warden", HOOD)]


def render(svg, size):
    """An SVG body (512 grid) as a PIL image at size x size."""
    doc = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="{size}" height="{size}">{svg}</svg>'
    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=doc, width=size, height=size)))).convert("RGBA")


def main():
    """Write each concept's SVG and a comparison sheet."""
    OUT.mkdir(exist_ok=True)
    W, row_h = 1200, 330
    sheet = Image.new("RGB", (W, 40 + row_h * len(CONCEPTS)), "#0f1115")
    d = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 26)
    small = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 18)
    for i, (name, svg) in enumerate(CONCEPTS):
        (OUT / f"concept_{i + 1}.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">{svg}</svg>', encoding="utf-8")
        y = 30 + i * row_h
        d.text((40, y), name, font=font, fill="#e8ebef")
        sheet.paste(big := render(svg, 256), (40, y + 40), big)
        x = 340
        for s in (64, 48, 32, 24):
            im = render(svg, s)
            sheet.paste(im, (x, y + 40 + 256 - s), im)
            d.text((x, y + 40 + 262), f"{s}px", font=small, fill="#98a2ad")
            x += s + 40
        # a fake taskbar strip on light and dark, at real 24/32 px
        for j, bg in enumerate(("#202020", "#f3f3f3")):
            bx, by = 760, y + 70 + j * 110
            d.rounded_rectangle((bx, by, bx + 380, by + 70), 12, fill=bg)
            for k, s in enumerate((32, 24, 32)):
                im = render(CONCEPTS[(i + k) % len(CONCEPTS)][1] if k != 1 else svg, s) if k != 1 else render(svg, 32)
                sheet.paste(im, (bx + 30 + k * 60, by + 19), im)
        d.text((760, y + 40), "taskbar (middle icon = this one)", font=small, fill="#98a2ad")
    sheet.save(OUT.parent / "icon_concepts.png")
    print("wrote", OUT.parent / "icon_concepts.png")


if __name__ == "__main__":
    main()
