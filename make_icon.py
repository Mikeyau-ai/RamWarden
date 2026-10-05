"""
Generate RamWarden's icon and artwork from one vector drawing.

Design (Mikey, 2026-10-05): a warden's shield guarding a RAM stick, in the Sixth Day Studios
bright teal (#2CC4A8) on a dark rounded tile. Flat for the icon; the glow version is only for
marketing (website hero, Store banner), where there's room for it.

Writes:
  icon.ico           16-256 px (Windows window/taskbar/installer icon)
  logo.png           40 px shield without the tile (the app's top bar is already dark)
  icon_preview.png   256 px tile (README, Store package tiles)
  brand/             wordmark (flat + glow) and the Store hero banner

Sizes of 32 px and below use a simpler drawing (thicker shield, fewer chip details), because
fine detail turns to mush at taskbar size.

Run: python make_icon.py      (needs: python -m pip install resvg-py pillow; Montserrat installed)
"""
import io
import pathlib

import resvg_py
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
TEAL, BG, BG2 = "#2CC4A8", "#141414", "#24282b"
FONTS = [r"C:\Windows\Fonts\Montserrat-Bold.otf"]

# The shield, on a 512 grid, filling most of the tile.
SHIELD = ("M256 46 C306 72 370 86 428 86 L428 238 C428 356 356 436 256 482 "
          "C156 436 84 356 84 238 L84 86 C142 86 206 72 256 46 Z")


def stick(detail=True):
    """The RAM stick, tilted like Mikey's design: a teal board and pins, with the chip windows and
    key notch CUT OUT (a mask), so whatever is behind shows through: the dark tile in the icon, the
    page itself in the light-mode wordmark."""
    chips = (-96, -48, 0, 48) if detail else (-80, 16)
    w = 36 if detail else 58
    holes = "".join(f'<rect x="{x}" y="-24" width="{w}" height="30" rx="4" fill="black"/>' for x in chips)
    pins = ("".join(f'<rect x="{x}" y="26" width="7" height="18" fill="{TEAL}"/>' for x in range(-108, 116, 14))
            if detail else "")
    notch = '<rect x="-10" y="18" width="16" height="26" fill="black"/>' if detail else ""
    board_h = 70 if detail else 76
    return (f'<g transform="translate(266 250) rotate(-35) scale(1.12)">'
            f'<mask id="rwcut" maskUnits="userSpaceOnUse" x="-140" y="-60" width="280" height="130">'
            f'<rect x="-140" y="-60" width="280" height="130" fill="white"/>{holes}{notch}</mask>'
            f'<g mask="url(#rwcut)"><rect x="-124" y="-42" width="248" height="{board_h}" rx="10" fill="{TEAL}"/>'
            f'{pins}</g></g>')


def mark(detail=True):
    """The shield and stick (no tile)."""
    stroke = 34 if detail else 50
    return (f'<path d="{SHIELD}" fill="none" stroke="{TEAL}" stroke-width="{stroke}" stroke-linejoin="round"/>'
            + stick(detail))


def tile(detail=True):
    """The app icon: the mark on a dark rounded tile."""
    return (f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{BG2}"/>'
            f'<stop offset="1" stop-color="{BG}"/></linearGradient></defs>'
            f'<rect width="512" height="512" rx="112" fill="url(#bg)"/>'
            f'<g transform="translate(256 256) scale(0.84) translate(-256 -256)">{mark(detail)}</g>')


GLOW = ('<defs><filter id="g" x="-20%" y="-20%" width="140%" height="140%">'
        '<feGaussianBlur stdDeviation="12" result="b"/><feMerge><feMergeNode in="b"/>'
        '<feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>')


def wordmark(glow=False):
    """The shield above stacked "RAM / WARDEN" lettering, flat or glowing (600 x 760 units)."""
    text = (f'<g fill="{TEAL}" font-family="Montserrat" font-weight="700" text-anchor="middle">'
            f'<text x="300" y="640" font-size="150" letter-spacing="6">RAM</text>'
            f'<text x="300" y="740" font-size="96" letter-spacing="6">WARDEN</text></g>')
    body = f'<g transform="translate(44 0)">{mark(True)}</g>{text}'
    return f'{GLOW}<g filter="url(#g)">{body}</g>' if glow else body


def render(body, w, h=None, view=(0, 0, 512, 512)):
    """An SVG body as a PIL image."""
    h = h or w
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{" ".join(map(str, view))}" '
           f'width="{w}" height="{h}">{body}</svg>')
    data = resvg_py.svg_to_bytes(svg_string=doc, width=w, height=h, font_files=FONTS)
    return Image.open(io.BytesIO(bytes(data))).convert("RGBA")


def main():
    """Write the icon set and the brand artwork."""
    sizes = [16, 20, 24, 32, 40, 48, 64, 128, 256]
    frames = {s: render(tile(detail=s > 32), s) for s in sizes}
    # Each size drawn on its own (not downscaled), so the small ones keep their simpler drawing.
    frames[256].save(HERE / "icon.ico", format="ICO", sizes=[(s, s) for s in sizes],
                     append_images=[frames[s] for s in sizes if s != 256])
    render(mark(detail=True), 40).save(HERE / "logo.png")
    frames[256].save(HERE / "icon_preview.png")

    brand = HERE / "brand"
    brand.mkdir(exist_ok=True)
    for s in (16, 24, 32, 48):                              # the small drawings, for checking by eye
        frames[s].save(brand / f"icon-{s}.png")
    render(tile(), 1024).save(brand / "icon-1024.png")
    render(wordmark(False), 600, 760, (0, 0, 600, 760)).save(brand / "wordmark.png")
    render(wordmark(True), 600, 760, (0, 0, 600, 760)).save(brand / "wordmark-glow.png")
    # Store hero / banner art (16:9): the glowing wordmark on dark.
    banner = (f'<rect width="1920" height="1080" fill="{BG}"/>'
              f'<g transform="translate(645 110) scale(1.1)">{wordmark(True)}</g>')
    render(banner, 1920, 1080, (0, 0, 1920, 1080)).save(brand / "store-hero-1920x1080.png")
    print("icon.ico, logo.png, icon_preview.png and brand/ saved")


if __name__ == "__main__":
    main()
