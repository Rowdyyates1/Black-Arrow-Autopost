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

_CHORDS = {  # low, dark, on-brand chord voicings (Hz)
    "dark":      [55.00, 110.00, 130.81, 164.81],   # Am
    "cinematic": [49.00, 98.00, 146.83, 196.00],    # G open fifth, epic
    "driving":   [55.00, 110.00, 164.81, 220.00],   # A power
}

def _mood_key(mood):
    if any(w in mood for w in ("cinema", "tens", "susp", "build", "epic")): return "cinematic"
    if any(w in mood for w in ("driv", "energ", "bold", "punch")):          return "driving"
    return "dark"

def _audio_plan(dur, mood=None):
    """Returns a dict describing the audio to bake under the reel.
    Priority: a real licensed track from music/ (named by mood) -> else an
    original generated chord pad (royalty-free, on-brand). Never a hum."""
    mood = (mood or "dark").lower()
    key = _mood_key(mood)
    tracks = []
    for ext in ("*.mp3", "*.m4a", "*.wav", "*.aac"):
        tracks += glob.glob(os.path.join(MUSIC_DIR, ext))
    fo = max(0.0, dur - 1.3)
    if tracks:
        tagged = [t for t in tracks if key.split()[0] in os.path.basename(t).lower()]
        t = random.choice(tagged or tracks)
        return {"mode": "track", "input": ["-stream_loop", "-1", "-i", t],
                "af": f"volume=0.6,afade=t=out:st={fo:.2f}:d=1.3"}
    # no real tracks: compose an original dark loop (pad + arp + kick) and use it
    import music_gen
    wav = music_gen.generate(mood, seconds=8.0)
    return {"mode": "track", "input": ["-stream_loop", "-1", "-i", wav],
            "af": f"volume=0.5,afade=t=in:st=0:d=1,afade=t=out:st={fo:.2f}:d=1.3"}

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

def _layout(d, lines, big, small):
    """Resolve each line to (font_size, [wrapped sub-lines], color, line_height).
    Fits to width, then wraps anything still too long — never runs off-screen."""
    out = []
    for ln, style in lines:
        if style == "huge":
            out.append((200, [ln], WHITE, 250)); continue
        base = big if style == "big" else small
        fs = _fit(d, ln, base)
        subs = brand.wrap_balanced(d, ln, brand.font(fs), W - 100) or [ln]
        col = WHITE if style == "big" else MUTED
        out.append((fs, subs, col, int(fs * 1.18)))
    return out

def _draw_scene(d, cx, lines, a, dy, center=650, big=74, small=46):
    laid = _layout(d, lines, big, small)
    total = sum(lh * len(subs) for _, subs, _, lh in laid)
    y = center - total / 2 + dy          # vertically center the block
    for fs, subs, col, lh in laid:
        for s in subs:
            _ctext(d, cx, y, s, brand.font(fs), col, a); y += lh

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
                    _ctext(d, cx, 760+dy, cta, brand.font(_fit(d, cta, 44)), WHITE, a)
                    d.rounded_rectangle([cx-260, 900+dy, cx+260, 1010+dy], radius=16, outline=_blend(WHITE,a), width=3)
                    _ctext(d, cx, 935+dy, "DM the keyword to start", brand.font(30), MUTED, a)
                else:
                    _draw_scene(d, cx, lines, a, dy)
                break
        _ctext(d, cx, H-96, "BLACKARROW.LTD", brand.font(26), DIM, 1.0, trk=5)
        img.save(f"{frames_dir}/f{i:04d}.png", compress_level=1)

    return _encode(frames_dir, total_t, out_path, spec.get("audio"))

def _encode(frames_dir, total_t, out_path, mood):
    """Encode a folder of f%04d.png frames to MP4 with on-brand audio."""
    plan = _audio_plan(total_t, mood)
    base = ["ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{frames_dir}/f%04d.png"]
    vopts = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p"]
    aopts = ["-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", out_path]
    if plan["mode"] == "track":
        cmd = base + plan["input"] + vopts + ["-af", plan["af"]] + aopts
    else:  # synth chord pad via filter_complex
        cmd = (base + plan["input"] + ["-filter_complex", plan["filter_complex"],
               "-map", "0:v", "-map", plan["amap"]] + vopts + aopts)
    subprocess.run(cmd, check=True, capture_output=True)
    return out_path

def _slide_words(slide):
    n = 0
    for v in (slide.get("params", {}) or {}).values():
        if isinstance(v, str):
            n += len(v.split())
        elif isinstance(v, list):
            n += sum(len(x.split()) for x in v if isinstance(x, str))
    return n

def render_slideshow(spec, out_path, xfade=0.45):
    """Render carousel-style slides as a music-backed vertical video (posted as a
    reel). Each slide stays on screen long enough to read (paced to its text)."""
    slides = spec["slides"]
    imgs = brand.render_carousel(slides, video=True)   # 1080x1350, no swipe/index
    canvases = []
    for im in imgs:
        s = im.resize((W, int(W * im.height / im.width)))     # fit width
        cv = Image.new("RGB", (W, H), BG)
        cv.paste(s, (0, (H - s.height) // 2))                 # center vertically
        canvases.append(cv)
    if not canvases:
        raise ValueError("slideshow needs slides")
    frames_dir = tempfile.mkdtemp(prefix="slide_")
    idx = 0
    def _save(img):
        nonlocal idx
        img.save(f"{frames_dir}/f{idx:04d}.png", compress_level=1); idx += 1
    xf_n = int(xfade * FPS)
    for i, cv in enumerate(canvases):
        words = _slide_words(slides[i]) if i < len(slides) else 8
        hold = max(3.0, min(7.0, 2.0 + words * 0.34))   # ~reading time, comfortable floor
        for _ in range(int(hold * FPS)):
            _save(cv)
        if i < len(canvases) - 1:
            for k in range(xf_n):
                _save(Image.blend(cv, canvases[i + 1], (k + 1) / xf_n))
    return _encode(frames_dir, idx / FPS, out_path, spec.get("audio"))
