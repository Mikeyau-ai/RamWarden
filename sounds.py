"""
sounds.py: RamWarden's two UI sounds.

A soft tick when a process closes, a muted low thunk when Windows refuses (or it was already
gone), so the outcome is audible without reading the status bar. Both are plain synthesised
tones made by tools/generate_ui_sounds.py (they replaced gunshots and a kill-streak announcer).

Stdlib only: winsound ships with CPython on Windows and plays a 16-bit PCM
WAV asynchronously, which is all this needs.

Public API: play_kill(), play_blocked().
"""
import os
import random
import sys
import winsound

_VARIANTS = {
    'kill':    ('Close.wav',),
    'blocked': ('Blocked.wav',),
}

# Last variant played per group, so the same take is never heard twice running.
_last = {}


def _sfx_dir():
    """assets/sfx, both from source and from inside a PyInstaller bundle."""
    base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, 'assets', 'sfx')


def _play(group):
    """Play a random take from `group`, never raising.

    Audio is cosmetic feedback layered on top of killing processes: a missing
    file, a machine with no sound device, or a locked audio session must not
    turn into an error dialog on top of a kill that otherwise worked.
    """
    names = _VARIANTS.get(group)
    if not names:
        return

    # Avoid an immediate repeat, but only when there is something else to pick.
    choices = [n for n in names if n != _last.get(group)] or list(names)
    name = random.choice(choices)
    _last[group] = name

    path = os.path.join(_sfx_dir(), name)
    try:
        # ASYNC so the UI thread does not block for the length of the clip;
        # NODEFAULT so a missing file is silent rather than the Windows beep.
        winsound.PlaySound(
            path, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
    except Exception:
        pass


def play_kill():
    """Soft tick: one or more processes were closed."""
    _play('kill')


def play_blocked():
    """Muted thunk: the kill was refused, denied, or the process was already gone."""
    _play('blocked')

