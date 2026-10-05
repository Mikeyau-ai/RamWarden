"""Generate RamWarden's two UI sounds as plain synthesised tones (no samples, nothing to license).

  Close.wav    a soft, short "tick": a process was closed
  Blocked.wav  a muted low two-note "thunk": Windows refused, or it was already gone

Replaces the old gunshot / ricochet / kill-streak announcer clips (2026-10-05, Mikey: "no more
gunshots or voice lines"). Writes 44.1 kHz mono 16-bit WAV into assets/sfx/ (what winsound plays).

Run: python tools/generate_ui_sounds.py
"""
import array
import math
import pathlib
import wave

RATE = 44100
OUT = pathlib.Path(__file__).resolve().parents[1] / "assets" / "sfx"


def tone(f_start, f_end, ms, peak, attack_ms=4, decay=7.0):
    """A sine that glides from f_start to f_end, with a short fade-in and an exponential fade-out."""
    n = int(RATE * ms / 1000)
    out, phase = [], 0.0
    for i in range(n):
        t = i / n
        freq = f_start + (f_end - f_start) * t
        phase += 2 * math.pi * freq / RATE
        env = min(1.0, i / (RATE * attack_ms / 1000)) * math.exp(-decay * t)
        # A touch of the octave makes it read as a "tick" rather than a pure beep.
        out.append(peak * env * (0.85 * math.sin(phase) + 0.15 * math.sin(2 * phase)))
    return out


def silence(ms):
    """Quiet gap."""
    return [0.0] * int(RATE * ms / 1000)


def write(name, samples):
    """Save as 16-bit mono WAV."""
    pcm = array.array("h", (int(max(-1.0, min(1.0, s)) * 32767) for s in samples + silence(20)))
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())


def main():
    """Write both sounds."""
    OUT.mkdir(parents=True, exist_ok=True)
    write("Close.wav", tone(1180, 760, 70, 0.32))
    write("Blocked.wav", tone(330, 320, 75, 0.30, decay=5.0) + silence(25) + tone(250, 240, 90, 0.30, decay=5.0))
    print("wrote", OUT / "Close.wav", "and", OUT / "Blocked.wav")


if __name__ == "__main__":
    main()
