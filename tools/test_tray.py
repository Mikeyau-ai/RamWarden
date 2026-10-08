"""Tests for tray.py (the tray icon) and autostart.py's start-up command. The last test shows a
real tray icon for about a second.

Run: python tools/test_tray.py
"""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import autostart   # noqa: E402
import tray        # noqa: E402


def pixel(data, size, x, y):
    """(b, g, r, a) of one pixel in render() output."""
    i = (y * size + x) * 4
    return tuple(data[i:i + 4])


def test_render_size_corners_and_colour_steps():
    for size in (16, 20, 24, 32):
        data = tray.render(50, size)
        assert len(data) == size * size * 4
        assert pixel(data, size, 0, 0)[3] == 0                    # rounded corner is clear
    teal, amber, red = (0xa8, 0xc4, 0x2c, 255), (0x40, 0xa0, 0xe0, 255), (0x52, 0x52, 0xe0, 255)
    assert pixel(tray.render(59, 16), 16, 8, 1) == teal           # top edge: tile colour
    assert pixel(tray.render(60, 16), 16, 8, 1) == amber
    assert pixel(tray.render(85, 16), 16, 8, 1) == red


def test_render_draws_digits_and_caps_at_99():
    dark_ink = bytes((0x1a, 0x1a, 0x0b, 255))                    # digit colour on the teal tile
    data = tray.render(1, 16)
    lit = sum(1 for i in range(0, len(data), 4) if data[i:i + 4] == dark_ink)
    assert lit == 8 * 4                                           # the "1" glyph: 8 cells at 2×2 px
    assert tray.render(100, 16) == tray.render(99, 16)
    assert tray.render(8, 16) != tray.render(88, 16)


def test_autostart_command_forms():
    assert autostart.command(store=True).endswith(r'\Microsoft\WindowsApps\RamWarden.exe" --tray')
    cmd = autostart.command(store=False)                          # from source
    assert 'pythonw.exe' in cmd and cmd.endswith('main.pyw" --tray')


def test_real_icon_starts_answers_a_second_copy_and_goes_away():
    t = tray.Tray()
    t.update(42, "RamWarden test")
    assert tray.show_running_copy()
    time.sleep(0.3)
    assert t.events.get(timeout=2) == 'open'
    t.stop()
    assert not tray.show_running_copy()


if __name__ == "__main__":
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print("PASS", name)
        except Exception as e:                       # noqa: BLE001 (report and carry on)
            failed += 1
            print("FAIL", name, repr(e))
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
