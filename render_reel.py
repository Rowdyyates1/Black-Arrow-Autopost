#!/usr/bin/env python3
"""Render an animated Black Arrow reel (720x1280 MP4) from a spec.

spec = {
  "kicker": "SPEED TO LEAD",
  "hook":  ["Your competitor", "already texted", "your lead back."],   # lands fast
  "beats": [
     {"kicker": "9:14 PM", "lines": ["A homeowner fills out", "a form on two sites."]},
     {"kicker": "Business A", "lines": ["Texts back in", "90 seconds."], "emph": 1},
     ...
  ],
  "end":   {"lines": ["Same lead.", "Different system."], "cta": 'Comment "SCORE"'}
}
Needs ffmpeg on PATH. Returns the output mp4 path.
"""
import os, subprocess, tempfile, glob, random
from PIL import Image, ImageDraw
import brand  # reuse fonts + colors + triangle

MUSIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music")

def _audio_args(dur, mood=None):
    """The brain passes an audio `mood` that fits Black Arrow's branding. We match
    it to the music library (music/ — drop on-brand licensed tracks named by mood,
    e.g. dark-01.mp3, cinematic-02.mp3). If the library has a match we bake that
    real track under the reel; if it's empty we synthesize a bed tuned to the mood
    so reels are never silent. NOTE: Instagram's own trending sounds cannot be
    attached via the publishing API — this is baked-in audio."""
    mood = (mood or "dark minimal premium").lower()
    key = mood.split()[0]
    tracks = []
    for ext in ("*.mp3", "*.m4a", "*.wav", "*.aac"):
        tracks += glob.glob(os.path.join(MUSIC_DIR, ext))
    tagged = [t for t in tracks if key in os.path.basename(t).lower()]
    chosen = tagged or tracks
    fo = max(0.0, dur - 1.2)
    if chosen:
        t = random.choice(chosen)
        return (["-stream_loop", "-1", "-i", t],
                f"volume=0.55,afade=t=out:st={fo:.2f}:d=1.2")
    # No library yet: synth an on-brand bed in the requested mood.
    seed = random.randint(1, 99999)
    fades = f",afade=t=in:st=0:d=1.5,afade=t=out:st={max(0.0, dur - 1.5):.2f}:d=1.5"
    if any(w in mood for w in ("driv", "energ", "punch", "bold")):
        src = "sine=frequency=55:sample_rate=44100"
        filt = "tremolo=f=1.8:d=0.85,lowpass=f=210,volume=0.11" + fades
    elif any(w in mood for w in ("tens", "susp", "cinema", "build", "epic")):
        src = "sine=frequency=98:sample_rate=44100"
        filt = "tremolo=f=0.5:d=0.6,lowpass=f=185,volume=0.09" + fades
    else:  # dark / minimal / premium
        src = f"anoisesrc=color=brown:seed={seed}:amplitude=0.6"
        filt = "lowpass=f=170,volume=0.10" + fades
    return (["-f", "lavfi", "-i", src], filt)

W, H, FPS = 720, 1280, 24
BG, WHITE, MUTED, DIM = brand.BG, brand.WHITE, brand.MUTED, brand.DIM

def _blend(c, a):
    return tuple(int(BG[i] + (c[i]-BG[i]) * a) for i in range(3))

def _ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1-t)**3

def _ctext(d, cx, y, text, f, color, a, trk=0):
    w = sum(d.textlength(ch, font=f) for ch in text) + trk*max(0, len(text)-1)
    x = cx - w/2
    for ch in text:
        d.text((x, y), ch, font=f, fill=_blend(color, a))
        x += d.textlength(ch, font=f) + trk

def _kicker(d, cx, y, text, a):
    if not text:
        return
    _ctext(d, cx, y, text.upper(), brand.font(30), MUTED, a, trk=6)
    d.line([(cx-35, y+52), (cx+35, y+52)], fill=_blend(WHITE, a), width=3)

def _fit(d, text, start, lo=38, max_w=W - 120):
    fs = start
    while fs > lo and sum(d.textlength(ch, font=brand.font(fs)) for ch in text) > max_w:
        fs -= 4
    return fs

def _draw_scene(d, cx, lines, a, dy, top=580, big=74, small=46):
    y = top + dy
    for ln, style in lines:
        if style == "big":
            fs = _fit(d, ln, big)
            _ctext(d, cx, y, ln, brand.font(fs), WHITE, a); y += int(fs*1.18)
        elif style == "huge":
            _ctext(d, cx, y, ln, brand.font(200), WHITE, a); y += 250
        else:
            fs = _fit(d, ln, small)
            _ctext(d, cx, y, ln, brand.font(fs), MUTED, a); y += int(fs*1.3)

def _scenes_from_spec(spec):
    """Build a list of (duration, kicker, [(text,style)], emphmark) scenes."""
    scenes = []
    hook = spec.get("hook", [])
    scenes.append((3.4, spec.get("kicker", ""),
                   [(l, "big") for l in hook], None))
    for b in spec.get("beats", []):
        lines = [(l, "big") for l in b.get("lines", [])]
        scenes.append((2.6, b.get("kicker", ""), lines, b.get("mark")))
    end = spec.get("end", {})
    scenes.append((3.2, "", [(l, "big") for l in end.get("lines", [])], "triangle"))
    return scenes, end.get("cta", 'Comment "SCORE"')

def render_reel(spec, out_path):
    scenes, cta = _scenes_from_spec(spec)
    # timeline
    t0 = 0.0; timed = []
    for dur, kick, lines, mark in scenes:
        timed.append((t0, t0+dur, kick, lines, mark)); t0 += dur
    total_t = t0
    cx = W/2

    frames_dir = tempfile.mkdtemp(prefix="reel_")
    n = int(total_t * FPS)
    for i in range(n):
        t = i / FPS
        img = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(img)
        for (a0, a1, kick, lines, mark) in timed:
            if a0 <= t < a1:
                loc = t - a0
                intro = _ease(loc / 0.45)
                outro = _ease((a1 - t) / 0.35)
                a = max(0.0, min(intro, outro))
                dy = (1-intro) * 45
                _kicker(d, cx, 470+dy, kick, a)
                if mark == "check":
                    col = _blend(WHITE, a)
                    d.line([(cx-30, 770+dy),(cx-4,796+dy)], fill=col, width=9)
                    d.line([(cx-4,796+dy),(cx+38,752+dy)], fill=col, width=9)
                if mark == "triangle":
                    brand.triangle(d, cx, 640+dy, 90, _blend(WHITE, a))
                    _ctext(d, cx, 760+dy, cta, brand.font(44), WHITE, a)
                    d.rounded_rectangle([cx-260, 900+dy, cx+260, 1010+dy], radius=16, outline=_blend(WHITE,a), width=3)
                    _ctext(d, cx, 935+dy, "Send Rowdy a DM to start", brand.font(30), MUTED, a)
                else:
                    _draw_scene(d, cx, lines, a, dy)
                break
        _ctext(d, cx, H-96, "BLACKARROW.LTD", brand.font(26), DIM, 1.0, trk=5)
        img.save(f"{frames_dir}/f{i:04d}.png", compress_level=1)

    audio_in, afilter = _audio_args(total_t, spec.get("audio"))
    cmd = (["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{frames_dir}/f%04d.png"]
           + audio_in +
           ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k", "-af", afilter, "-shortest",
            "-movflags", "+faststart", out_path])
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path
