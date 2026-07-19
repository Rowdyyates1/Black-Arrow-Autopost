"""Black Arrow brand rendering. Portable Pillow templates -> 1080x1350 PNG.
Monochrome, premium, matches blackarrow.ltd (#0A0A0A + the triangle mark).

v2 changes (2026-07-18):
  * reel_canvas(): fits any feed image onto a native 1080x1920 canvas so reel
    covers are never the 4:5 art blown up to fill 9:16 (the over-scale bug).
  * check_mark(): crisp anti-aliased vector checkmark (supersampled), shared by
    all renderers. No more raw 9px lines that read as a pixel drawing.
  * promo_card(): kicker/sub/cta are parameters now; the kicker no longer says
    "DM to start" (the CTA pill is the single DM mention on the card).
  * slide_cta(): the foot line no longer repeats the DM instruction.
"""
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350
BG    = (10, 10, 10)
PANEL = (22, 22, 22)
WHITE = (244, 244, 244)
MUTED = (150, 150, 150)
DIM   = (74, 74, 74)
LINE  = (38, 38, 38)

# Font resolution: works on Ubuntu (GitHub Actions installs fonts-liberation)
_CANDIDATES_BOLD = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
_CANDIDATES_REG = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
def _first(paths):
    for p in paths:
        if os.path.exists(p):
            return p
    return None
_FB = _first(_CANDIDATES_BOLD)
_FR = _first(_CANDIDATES_REG)
_cache = {}
def font(sz, bold=True):
    key = (sz, bold)
    if key not in _cache:
        path = (_FB if bold else _FR) or None
        _cache[key] = ImageFont.truetype(path, sz) if path else ImageFont.load_default()
    return _cache[key]

def _tw(d, text, f, trk=0):
    return sum(d.textlength(c, font=f) for c in text) + trk * max(0, len(text) - 1)

def tracked(d, xy, text, f, fill, trk=0, center_x=None):
    x, y = xy
    if center_x is not None:
        x = center_x - _tw(d, text, f, trk) / 2
    for c in text:
        d.text((x, y), c, font=f, fill=fill)
        x += d.textlength(c, font=f) + trk

def wrap(d, text, f, max_w):
    out, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= max_w:
            cur = t
        else:
            if cur: out.append(cur)
            cur = w
    if cur: out.append(cur)
    return out

def block(d, text, f, fill, x, y, max_w, leading):
    for ln in wrap(d, text, f, max_w):
        d.text((x, y), ln, font=f, fill=fill)
        y += leading
    return y

def triangle(d, cx, cy, size, fill):
    h = size * 0.87
    d.polygon([(cx, cy - h/2), (cx - size/2, cy + h/2), (cx + size/2, cy + h/2)], fill=fill)

# ---- Crisp vector checkmark ------------------------------------------------
_CK_CACHE = {}
def check_tile(size, color=WHITE, ss=4):
    """Anti-aliased checkmark on a transparent tile, rendered at ss-times
    resolution and downsampled (Pillow lines aren't anti-aliased natively —
    drawing them 1:1 is what produced the pixel-drawing look)."""
    key = (size, color)
    if key not in _CK_CACHE:
        s = size * ss
        t = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        td = ImageDraw.Draw(t)
        wdt = max(ss * 2, int(s * 0.13))
        p1 = (s * 0.14, s * 0.55)
        p2 = (s * 0.40, s * 0.80)
        p3 = (s * 0.86, s * 0.22)
        td.line([p1, p2], fill=color + (255,), width=wdt)
        td.line([p2, p3], fill=color + (255,), width=wdt)
        r = wdt / 2
        for (px, py) in (p1, p2, p3):                     # round caps/joint
            td.ellipse([px - r, py - r, px + r, py + r], fill=color + (255,))
        _CK_CACHE[key] = t.resize((size, size), Image.LANCZOS)
    return _CK_CACHE[key]

def check_mark(img, cx, cy, size, color=WHITE, alpha=1.0):
    """Paste a crisp checkmark centered on (cx, cy) of an RGB image."""
    tile = check_tile(size, color)
    if alpha < 1.0:
        tile = tile.copy()
        tile.putalpha(tile.getchannel("A").point(lambda a: int(a * alpha)))
    img.paste(tile, (int(cx - size / 2), int(cy - size / 2)), tile)

def _new():
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)

def _kicker(d, text, y=120, color=MUTED):
    tracked(d, (80, y), text.upper(), font(24), color, 6)
    d.line([(80, y + 48), (140, y + 48)], fill=WHITE, width=3)

def _footer(d, handle="blackarrow.ltd"):
    tracked(d, (80, H - 70), handle.upper(), font(24, bold=False), DIM, 4)

def _wordmark(d, cx, y, scale=0.9):
    f = font(int(30 * scale)); ts = int(26 * scale); trk = 8 * scale
    lw = _tw(d, "BLACK", f, trk); rw = _tw(d, "ARROW", f, trk); gap = int(28 * scale)
    total = lw + gap + ts + gap + rw
    x = cx - total / 2
    tracked(d, (x, y), "BLACK", f, WHITE, trk); x += lw + gap
    triangle(d, x + ts/2, y + int(15*scale), ts, WHITE); x += ts + gap
    tracked(d, (x, y), "ARROW", f, WHITE, trk)

# ---- Layout engine (overflow-safe) -----------------------------------------
def wrap_balanced(d, text, f, max_w):
    """Wrap to width, but avoid ending on a single stranded word (a 'widow')."""
    lines = wrap(d, text, f, max_w)
    if len(lines) >= 2 and len(lines[-1].split()) == 1:
        prev = lines[-2].split()
        if len(prev) >= 3:
            candidate = prev[-1] + " " + lines[-1]
            if d.textlength(candidate, font=f) <= max_w:
                lines[-1] = candidate
                lines[-2] = " ".join(prev[:-1])
    return lines

def _fitw(d, text, start, max_w, lo=28, bold=True):
    """Largest font <= start whose LONGEST word fits max_w (so wrapping never clips)."""
    fs = start
    longest = max(text.split(), key=len) if text.split() else text
    while fs > lo and _tw(d, longest, font(fs, bold)) > max_w:
        fs -= 2
    return fs

def _measure(d, items, max_w, scale):
    laid, total = [], 0
    for it in items:
        bold = it.get("bold", True)
        fs = max(22, int(it["size"] * scale))
        fs = _fitw(d, it["text"], fs, max_w, lo=max(20, int(it.get("lo", 28) * scale)), bold=bold)
        lines = wrap_balanced(d, it["text"], font(fs, bold), max_w) or [""]
        lh = int(fs * it.get("lead", 1.16))
        ga = it.get("gap_after", 32)
        laid.append((lines, fs, bold, it["color"], lh, ga))
        total += lh * len(lines) + ga
    if laid:
        total -= laid[-1][5]
    return laid, total

def _compose(d, items, area, x=80, max_w=920, center_x=None, valign="center", top=None):
    """Lay text items top-down, wrapping to width and auto-shrinking to fit the
    vertical area. Overlap is impossible by construction. Returns ending y."""
    a0, a1 = area
    scale = 1.0
    while True:
        laid, total = _measure(d, items, max_w, scale)
        if total <= (a1 - a0) or scale <= 0.45:
            break
        scale -= 0.06
    y = top if top is not None else (a0 + max(0, (a1 - a0) - total) // 2 if valign == "center" else a0)
    for lines, fs, bold, color, lh, ga in laid:
        for ln in lines:
            if center_x is not None:
                tracked(d, (0, y), ln, font(fs, bold), color, 0, center_x=center_x)
            else:
                d.text((x, y), ln, font=font(fs, bold), fill=color)
            y += lh
        y += ga
    return y

# ---- Templates -------------------------------------------------------------
def stat_card(kicker, big, sub):
    img, d = _new()
    _kicker(d, kicker)
    _compose(d, [
        {"text": big, "size": 210, "lo": 80, "color": WHITE, "lead": 1.02, "gap_after": 44},
        {"text": sub, "size": 46, "bold": False, "color": MUTED},
    ], area=(300, 1170), max_w=920)
    _footer(d); return img

def quote_card(line_white, line_muted=None):
    img, d = _new()
    d.line([(80, 300), (80, 1050)], fill=LINE, width=3)
    tracked(d, (130, 300), "“", font(160), DIM)
    items = [{"text": line_white, "size": 84, "color": WHITE, "gap_after": 24}]
    if line_muted:
        items.append({"text": line_muted, "size": 52, "bold": False, "color": MUTED})
    _compose(d, items, area=(470, 1050), x=130, max_w=860, valign="top", top=470)
    _wordmark(d, W/2, 1180); return img

def list_card(kicker, title, items):
    img, d = _new()
    _kicker(d, kicker)
    ty = _compose(d, [{"text": title, "size": 70, "color": WHITE}],
                  area=(300, 620), max_w=920, valign="top", top=300)
    y0 = ty + 40
    avail = 1160 - y0
    fs = 44
    while fs > 26:
        h = sum(int(fs * 1.16) * len(wrap(d, it, font(fs, False), 820)) + 26 for it in items)
        if h <= avail:
            break
        fs -= 2
    y = y0
    for it in items:
        f = font(fs, False)
        triangle(d, 100, y + fs * 0.5, 20, DIM)
        for ln in wrap_balanced(d, it, f, 820):
            d.text((140, y), ln, font=f, fill=WHITE); y += int(fs * 1.16)
        y += 26
    _footer(d); return img

def myth_truth(myth, truth):
    img, d = _new()
    _kicker(d, "Myth")
    my = _compose(d, [{"text": myth, "size": 62, "bold": False, "color": MUTED}],
                  area=(280, 640), max_w=920, valign="top", top=280)
    dy = my + 46
    d.line([(80, dy), (W - 80, dy)], fill=LINE, width=2)
    tracked(d, (80, dy + 40), "TRUTH", font(24), WHITE, 6)
    d.line([(80, dy + 88), (140, dy + 88)], fill=WHITE, width=3)
    _compose(d, [{"text": truth, "size": 62, "color": WHITE}],
             area=(dy + 120, 1170), max_w=920, valign="top", top=dy + 120)
    _footer(d); return img

def clean_cta(cta, fallback="DM TOOLS"):
    """Minimal CTA text: quotes stripped ("DM TRIAL", not 'DM "TRIAL"'),
    never empty — a card without a visible CTA is a bug."""
    c = (cta or "").replace('"', "").replace("“", "").replace("”", "").strip()
    return c or fallback

def promo_card(title_white, title_muted, cta="DM TOOLS", sub=None, kicker="Free tool"):
    """Offer/lead-magnet card. The CTA pill is the ONE DM mention on the card —
    the kicker never says 'DM to start' (that was the double-mention bug)."""
    img, d = _new()
    cta = clean_cta(cta)
    _kicker(d, kicker)
    _compose(d, [
        {"text": title_white, "size": 80, "color": WHITE, "gap_after": 10},
        {"text": title_muted, "size": 80, "color": MUTED, "gap_after": 40},
        {"text": sub or "Free from Black Arrow. No signup, no card.",
         "size": 42, "bold": False, "color": MUTED},
    ], area=(300, 1060), max_w=920)
    d.rounded_rectangle([80, 1120, W - 80, 1240], radius=18, fill=WHITE)
    tracked(d, (0, 1152), cta, font(_fitw(d, cta, 46, W - 240)), BG, 2, center_x=W/2)
    _footer(d); return img

def render(post):
    """Dispatch a content-bank dict to the right template. Returns a PIL image."""
    t = post["template"]
    p = post["params"]
    if t == "stat":  return stat_card(p["kicker"], p["big"], p["sub"])
    if t == "quote": return quote_card(p["white"], p.get("muted"))
    if t == "list":  return list_card(p["kicker"], p["title"], p["items"])
    if t == "myth":  return myth_truth(p["myth"], p["truth"])
    if t == "promo": return promo_card(p["white"], p["muted"], p.get("cta", "DM TOOLS"),
                                       p.get("sub"), p.get("kicker", "Free tool"))
    raise ValueError(f"unknown template {t}")

# ---- Carousel slides -------------------------------------------------------
_SLIDESHOW = False   # True while rendering slides for a video (drops swipe/index)

def _swipe(d, y):
    triangle(d, 108, y + 22, 40, WHITE)
    tracked(d, (150, y), "SWIPE", font(28), MUTED, 6)

def slide_cover(p, idx, total):
    img, d = _new()
    _kicker(d, p.get("kicker", ""))
    lines = p.get("lines", []) or ["Black Arrow"]
    items = [{"text": ln, "size": 82, "color": WHITE if i == 0 else MUTED, "gap_after": 8}
             for i, ln in enumerate(lines)]
    endy = _compose(d, items, area=(320, 1000), max_w=940, valign="top", top=360)
    if not _SLIDESHOW:
        _swipe(d, min(endy + 24, 1120))
    _footer_idx(d, idx, total)
    return img

def slide_stat(p, idx, total):
    img, d = _new()
    _kicker(d, p.get("kicker", "The data"))
    _compose(d, [
        {"text": p["big"], "size": 210, "lo": 80, "color": WHITE, "lead": 1.02, "gap_after": 44},
        {"text": p["sub"], "size": 46, "bold": False, "color": MUTED},
    ], area=(320, 1170), max_w=920)
    _footer_idx(d, idx, total)
    return img

def slide_point(p, idx, total):
    img, d = _new()
    tracked(d, (80, 150), p.get("n", ""), font(120), LINE)
    _kicker(d, p.get("kicker", ""), y=300)
    _compose(d, [
        {"text": p["title"], "size": 76, "color": WHITE, "gap_after": 30},
        {"text": p.get("sub", ""), "size": 44, "bold": False, "color": MUTED},
    ], area=(400, 1170), max_w=900, valign="top", top=400)
    _footer_idx(d, idx, total)
    return img

def slide_quote(p, idx, total):
    img, d = _new()
    tracked(d, (80, 320), "“", font(160), DIM)
    items = [{"text": p["white"], "size": 80, "color": WHITE, "gap_after": 22}]
    if p.get("muted"):
        items.append({"text": p["muted"], "size": 52, "bold": False, "color": MUTED})
    _compose(d, items, area=(500, 1120), max_w=940, valign="top", top=500)
    _footer_idx(d, idx, total)
    return img

def slide_cta(p, idx, total):
    """One CTA only: a headline question + a single DM button. The foot line
    supports the button; it never repeats the DM instruction."""
    img = Image.new("RGB", (W, H), PANEL); d = ImageDraw.Draw(img)
    _wordmark(d, W/2, 160)
    head = p.get("white") or p.get("headline") or "Want this built for your business?"
    _compose(d, [{"text": head, "size": 56, "color": WHITE}],
             area=(320, 660), max_w=860, center_x=W/2)
    button = clean_cta(p.get("button"))
    d.rounded_rectangle([150, 720, W-150, 846], radius=18, fill=WHITE)
    tracked(d, (0, 760), button,
            font(_fitw(d, button, 48, W - 360)), BG, 0, center_x=W/2)
    block_center(d, p.get("foot", "The Black Arrow team maps it for your business."),
                 font(34, bold=False), MUTED, 910, 900)
    _footer_idx(d, idx, total)
    return img

def block_center(d, text, f, fill, y, max_w):
    lines = wrap(d, text, f, max_w)
    for ln in lines:
        tracked(d, (0, y), ln, f, fill, 0, center_x=W/2)
        y += int(f.size * 1.3)

def _footer_idx(d, idx, total):
    tracked(d, (80, H - 70), "BLACKARROW.LTD", font(24, bold=False), DIM, 4)
    if _SLIDESHOW:
        return  # no page counter on a video
    lab = f"{idx:02d} / {total:02d}"
    w = _tw(d, lab, font(24, bold=False), 4)
    tracked(d, (W - 80 - w, H - 70), lab, font(24, bold=False), DIM, 4)

_SLIDE = {"cover": slide_cover, "stat": slide_stat, "point": slide_point,
          "quote": slide_quote, "cta": slide_cta}

def hook_card(kicker, lines):
    """Clean 1080x1350 card (kicker + hook) used as the Story source for reels."""
    img, d = _new()
    _kicker(d, kicker or "")
    items = [{"text": ln, "size": 82, "color": WHITE if i == 0 else MUTED, "gap_after": 8}
             for i, ln in enumerate(lines or ["Black Arrow"])]
    _compose(d, items, area=(340, 1060), max_w=940)
    _footer(d)
    return img

def story_canvas(im, prompt="SEE FULL POST ON PROFILE"):
    """Fit a feed image onto a 1080x1920 Story frame, centered on the dark
    background (no zoom/crop), with a 'see full post' prompt near the bottom."""
    SW, SH = 1080, 1920
    c = Image.new("RGB", (SW, SH), BG); d = ImageDraw.Draw(c)
    w, h = SW, int(im.height * SW / im.width)
    if h > SH:
        h, w = SH, int(im.width * SH / im.height)
    c.paste(im.resize((w, h)), ((SW - w) // 2, (SH - h) // 2))
    if prompt:
        f = font(30); tw = _tw(d, prompt.upper(), f, 4)
        x0, x1, y0, y1 = (SW - tw) // 2 - 44, (SW + tw) // 2 + 44, 1740, 1828
        d.rounded_rectangle([x0, y0, x1, y1], radius=44, outline=WHITE, width=3)
        tracked(d, (0, y0 + 27), prompt.upper(), f, WHITE, 4, center_x=SW / 2)
    return c

def reel_canvas(im):
    """Fit ANY feed-ratio image onto a native 1080x1920 canvas, centered on the
    brand background with the wordmark up top. Use this for every reel cover
    that starts life as 4:5 art. Never hand Instagram a 4:5 image as a reel
    cover directly — it scales it to fill 9:16 and the cover lands over-zoomed
    in the Reels tab (the bug this function fixes)."""
    SW, SH = 1080, 1920
    c = Image.new("RGB", (SW, SH), BG)
    d = ImageDraw.Draw(c)
    # scale to fit INSIDE the safe center area, preserving ratio (no crop/zoom)
    max_w, max_h = SW, 1350
    w = max_w; h = int(im.height * w / im.width)
    if h > max_h:
        h = max_h; w = int(im.width * h / im.height)
    c.paste(im.resize((w, h)), ((SW - w) // 2, (SH - h) // 2))
    _wordmark(d, SW / 2, 150, scale=0.9)
    return c

def reel_cover(spec):
    """Branded 1080x1920 cover for a reel. Content is centered so the grid's
    center-crop still reads. spec = the reel 'spec' dict (kicker, hook)."""
    CW, CH = 1080, 1920
    img = Image.new("RGB", (CW, CH), BG); d = ImageDraw.Draw(img)
    cx = CW / 2
    kick = spec.get("kicker", "")
    if kick:
        tracked(d, (0, 760), kick.upper(), font(30), MUTED, 6, center_x=cx)
        d.line([(cx-35, 812), (cx+35, 812)], fill=WHITE, width=3)
    hook = spec.get("hook", []) or ["Black Arrow"]
    # auto-fit each hook line to width
    y = 900
    for ln in hook[:3]:
        fs = 84
        while fs > 44 and _tw(d, ln, font(fs)) > CW - 120:
            fs -= 4
        tracked(d, (0, y), ln, font(fs), WHITE, 0, center_x=cx)
        y += int(fs * 1.2)
    triangle(d, cx, y + 70, 60, WHITE)
    _wordmark(d, cx, 1770, scale=1.0)
    return img

def render_carousel(slides, video=False):
    """slides: list of {kind, params}. Returns list of PIL images.
    video=True drops the swipe hint and page counter (for slideshow videos)."""
    global _SLIDESHOW
    _SLIDESHOW = video
    try:
        total = len(slides)
        out = []
        for i, s in enumerate(slides, start=1):
            fn = _SLIDE.get(s["kind"], slide_point)
            out.append(fn(s.get("params", {}), i, total))
        return out
    finally:
        _SLIDESHOW = False
