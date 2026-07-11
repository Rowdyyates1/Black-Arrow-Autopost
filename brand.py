"""Black Arrow brand rendering. Portable Pillow templates -> 1080x1350 PNG.
Monochrome, premium, matches blackarrow.ltd (#0A0A0A + the triangle mark)."""
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

# ---- Templates -------------------------------------------------------------
def stat_card(kicker, big, sub):
    img, d = _new()
    _kicker(d, kicker)
    tracked(d, (80, 470), big, font(220 if len(big) <= 4 else 150), WHITE)
    block(d, sub, font(46, bold=False), MUTED, 80, 820, 920, 62)
    _footer(d); return img

def quote_card(line_white, line_muted=None):
    img, d = _new()
    d.line([(80, 300), (80, 1050)], fill=LINE, width=3)
    tracked(d, (130, 300), "“", font(200), DIM)
    y = block(d, line_white, font(88), WHITE, 130, 500, 900, 104)
    if line_muted:
        block(d, line_muted, font(56, bold=False), MUTED, 130, y + 20, 900, 74)
    _wordmark(d, W/2, 1180); return img

def list_card(kicker, title, items):
    img, d = _new()
    _kicker(d, kicker)
    block(d, title, font(72), WHITE, 80, 300, 920, 88)
    y = 560
    for it in items:
        triangle(d, 100, y + 22, 22, DIM)
        block(d, it, font(42, bold=False), WHITE, 140, y, 840, 56)
        y += 130
    _footer(d); return img

def myth_truth(myth, truth):
    img, d = _new()
    _kicker(d, "Myth")
    block(d, myth, font(64), MUTED, 80, 300, 920, 82)
    d.line([(80, 690), (W - 80, 690)], fill=LINE, width=2)
    tracked(d, (80, 740), "TRUTH", font(24), WHITE, 6)
    d.line([(80, 788), (140, 788)], fill=WHITE, width=3)
    block(d, truth, font(64), WHITE, 80, 840, 920, 82)
    _footer(d); return img

def promo_card(title_white, title_muted, cta='DM ME ▲'):
    img, d = _new()
    _kicker(d, "Free · DM to start")
    block(d, title_white, font(84), WHITE, 80, 320, 920, 100)
    block(d, title_muted, font(84), MUTED, 80, 520, 920, 100)
    block(d, "Get scored across Acquisition, Conversion, Operations and Retention.",
          font(42, bold=False), MUTED, 80, 780, 920, 58)
    d.rounded_rectangle([80, 1120, W - 80, 1240], radius=18, fill=WHITE)
    tracked(d, (0, 1152), cta, font(46), BG, 2, center_x=W/2)
    _footer(d); return img

def render(post):
    """Dispatch a content-bank dict to the right template. Returns a PIL image."""
    t = post["template"]
    p = post["params"]
    if t == "stat":  return stat_card(p["kicker"], p["big"], p["sub"])
    if t == "quote": return quote_card(p["white"], p.get("muted"))
    if t == "list":  return list_card(p["kicker"], p["title"], p["items"])
    if t == "myth":  return myth_truth(p["myth"], p["truth"])
    if t == "promo": return promo_card(p["white"], p["muted"], p.get("cta", 'DM ME ▲'))
    raise ValueError(f"unknown template {t}")

# ---- Carousel slides -------------------------------------------------------
def _swipe(d, y):
    triangle(d, 108, y + 22, 40, WHITE)
    tracked(d, (150, y), "SWIPE", font(28), MUTED, 6)

def slide_cover(p, idx, total):
    img, d = _new()
    _kicker(d, p.get("kicker", ""))
    y = 360
    for ln in p["lines"]:
        block(d, ln, font(84), WHITE if ln == p["lines"][0] else MUTED, 80, y, 940, 100)
        y += 104 * (len(wrap(d, ln, font(84), 940)))
    _swipe(d, y + 20)
    _footer_idx(d, idx, total)
    return img

def slide_stat(p, idx, total):
    img, d = _new()
    _kicker(d, p.get("kicker", "The data"))
    big = p["big"]
    tracked(d, (80, 460), big, font(210 if len(big) <= 4 else 140), WHITE)
    block(d, p["sub"], font(46, bold=False), MUTED, 80, 820, 920, 62)
    _footer_idx(d, idx, total)
    return img

def slide_point(p, idx, total):
    img, d = _new()
    tracked(d, (80, 150), p.get("n", ""), font(120), LINE)
    _kicker(d, p.get("kicker", ""), y=300)
    block(d, p["title"], font(78), WHITE, 80, 400, 900, 92)
    block(d, p.get("sub", ""), font(44, bold=False), MUTED, 80, 580, 900, 62)
    _footer_idx(d, idx, total)
    return img

def slide_quote(p, idx, total):
    img, d = _new()
    tracked(d, (80, 320), "“", font(180), DIM)
    y = block(d, p["white"], font(80), WHITE, 80, 520, 940, 96)
    if p.get("muted"):
        block(d, p["muted"], font(52, bold=False), MUTED, 80, y + 20, 940, 70)
    _footer_idx(d, idx, total)
    return img

def slide_cta(p, idx, total):
    """One CTA only: a headline question + a single DM button."""
    img = Image.new("RGB", (W, H), PANEL); d = ImageDraw.Draw(img)
    _wordmark(d, W/2, 160)
    head = p.get("white") or p.get("headline") or "Want this built for your business?"
    f = font(56)
    lines = wrap(d, head, f, 860)
    y = 450 - (len(lines) - 1) * 34
    for ln in lines:
        tracked(d, (0, y), ln, f, WHITE, 0, center_x=W/2); y += 74
    d.rounded_rectangle([150, 720, W-150, 846], radius=18, outline=WHITE, width=3)
    tracked(d, (0, 760), p.get("button", 'DM "START"'), font(48), WHITE, 0, center_x=W/2)
    block_center(d, p.get("foot", "DM us and we'll map it for your business."),
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
    lab = f"{idx:02d} / {total:02d}"
    w = _tw(d, lab, font(24, bold=False), 4)
    tracked(d, (W - 80 - w, H - 70), lab, font(24, bold=False), DIM, 4)

_SLIDE = {"cover": slide_cover, "stat": slide_stat, "point": slide_point,
          "quote": slide_quote, "cta": slide_cta}

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

def render_carousel(slides):
    """slides: list of {kind, params}. Returns list of PIL images."""
    total = len(slides)
    out = []
    for i, s in enumerate(slides, start=1):
        fn = _SLIDE.get(s["kind"], slide_point)
        out.append(fn(s.get("params", s.get("params", {})), i, total))
    return out
