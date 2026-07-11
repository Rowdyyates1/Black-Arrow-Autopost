#!/usr/bin/env python3
"""Compose a short, dark, on-brand instrumental loop (no downloads, no licensing
issues — generated from scratch). Pad chord progression + arpeggio + soft kick.
Pure standard library. Writes a 16-bit mono WAV.

Used as the reel soundtrack when the music/ folder has no real tracks. Not a
licensed pop song — an original cinematic bed with actual movement, not a hum.
"""
import math, wave, struct, tempfile, os

SR = 44100

# chord voicings as absolute frequencies (Hz), minor / cinematic feel
_A, _C, _D, _E, _F, _G, _Bb = 110.0, 130.81, 146.83, 164.81, 87.31, 98.00, 116.54
_CHORDS = {
    "Am": [_A, _C, _E],
    "F":  [_F, _A, _C],
    "C":  [_C, _E, _G * 2],
    "G":  [_G, 123.47, _D],
    "Dm": [_D, _F, _A],
    "Em": [_E, _G, 123.47],
}
_MOODS = {
    "dark":      (["Am", "F", "C", "G"],   0.5),   # beat seconds (120 bpm)
    "cinematic": (["Am", "F", "Dm", "Em"], 0.6),
    "driving":   (["Am", "Am", "F", "G"],  0.4),
    "minimal":   (["Am", "C", "F", "G"],   0.55),
}

def _mood_key(mood):
    m = (mood or "dark").lower()
    if any(w in m for w in ("cinema", "tens", "susp", "build", "epic")): return "cinematic"
    if any(w in m for w in ("driv", "energ", "bold", "punch")):          return "driving"
    if "minim" in m:                                                     return "minimal"
    return "dark"

def _add_pluck(buf, start, freq, dur, amp):
    n = int(dur * SR); s0 = int(start * SR)
    for i in range(n):
        idx = s0 + i
        if idx >= len(buf): break
        env = math.exp(-5.0 * i / n)
        buf[idx] += amp * env * (math.sin(2*math.pi*freq*i/SR)
                                 + 0.25*math.sin(4*math.pi*freq*i/SR))

def _add_kick(buf, start, amp):
    dur = 0.18; n = int(dur * SR); s0 = int(start * SR)
    for i in range(n):
        idx = s0 + i
        if idx >= len(buf): break
        t = i / SR
        f = 90.0 * math.exp(-30 * t) + 45.0        # pitch drop
        env = math.exp(-16 * t)
        buf[idx] += amp * env * math.sin(2*math.pi*f*t)

def generate(mood, path=None, seconds=8.0):
    prog, beat = _MOODS[_mood_key(mood)]
    N = int(seconds * SR)
    buf = [0.0] * N
    fade = 0.35                              # crossfade between chords
    chord_dur = (seconds - fade) / len(prog)

    # smooth, crossfaded pad — each chord fades in/out and overlaps the next,
    # and starts at phase 0, so there are no clicks or gaps between chords.
    for ci in range(len(prog)):
        chord = _CHORDS[prog[ci]]
        start = int(ci * chord_dur * SR)
        seg_n = int((chord_dur + fade) * SR)
        for i in range(seg_n):
            idx = start + i
            if idx >= N:
                break
            t = i / SR
            if t < fade:
                a = 0.5 * (1 - math.cos(math.pi * t / fade))                   # fade in
            elif t > chord_dur:
                a = 0.5 * (1 - math.cos(math.pi * (chord_dur + fade - t) / fade))  # fade out
            else:
                a = 1.0
            val = 0.0
            for f in chord:
                val += math.sin(2 * math.pi * f * t)     # phase from segment start
            buf[idx] += 0.05 * a * val

    # arpeggio (eighth notes, up an octave)
    step = beat / 2; t = 0.0; ai = 0
    while t < seconds:
        chord = _CHORDS[prog[int(t / chord_dur) % len(prog)]]
        _add_pluck(buf, t, chord[ai % len(chord)] * 2, 0.22, 0.11)
        ai += 1; t += step

    # soft kick on the beat
    t = 0.0
    while t < seconds:
        _add_kick(buf, t, 0.22)
        t += beat

    peak = max(1e-6, max(abs(x) for x in buf))
    scale = 0.9 / peak
    path = path or tempfile.mktemp(suffix=".wav")
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b"".join(struct.pack("<h", int(max(-1, min(1, x*scale)) * 32767))
                               for x in buf))
    return path

if __name__ == "__main__":
    print(generate("dark", "sample_music.wav"))
