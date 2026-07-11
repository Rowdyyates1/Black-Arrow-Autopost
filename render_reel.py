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
import os, subprocess, tempfile
from PIL import Image, ImageDraw
import brand  # reuse fonts + colors + triangle

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

def _draw_scene(d, cx, lines, a, dy, top=560, big=90, small=52):
    y = top + dy
    for ln, style in lines:
        if style == "big":
            _ctext(d, cx, y, ln, brand.font(big), WHITE, a); y += int(big*1.18)
        elif style == "huge":
            _ctext(d, cx, y, ln, brand.font(200), WHITE, a); y += 250
        else:
            _ctext(d, cx, y, ln, brand.font(small), MUTED, a); y += int(small*1.3)

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
                    _ctext(d, cx, 935+dy, "blackarrow.ltd/#assessment", brand.font(30), MUTED, a)
                else:
                    _draw_scene(d, cx, lines, a, dy)
                break
        _ctext(d, cx, H-96, "BLACKARROW.LTD", brand.font(26), DIM, 1.0, trk=5)
        img.save(f"{frames_dir}/f{i:04d}.png", compress_level=1)

    subprocess.run(["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{frames_dir}/f%04d.png",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart", out_path],
                   check=True, capture_output=True)
    return out_path
