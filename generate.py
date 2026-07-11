#!/usr/bin/env python3
"""The brain. Researches what's converting on Instagram right now (web search),
then writes 3 fresh, on-brand Black Arrow posts as structured specs the renderer
can turn into images / carousels / reels.

Requires: ANTHROPIC_API_KEY. Optional: MODEL (default claude-sonnet-5).
Outputs: prints a JSON array of 3 post specs to stdout (run_daily.py captures it).
"""
import os, json, re, sys, urllib.request

API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.environ.get("MODEL", "claude-sonnet-5")

BRAND = """You are the content engine for BLACK ARROW (blackarrow.ltd), a growth-
infrastructure agency that builds paid advertising, automated lead follow-up, and
CRM systems for service businesses — contractors, home services, roofing, HVAC,
car dealerships, medical/dental practices, legal. Core message: "Advertising
creates opportunities. Systems create revenue." Signature stats: only 17% of
service businesses respond to a lead within an hour; responding in under 5 minutes
nearly doubles close rate. The offer/CTA is always the free Revenue Infrastructure
Score at blackarrow.ltd/#assessment, driven by a comment-to-DM mechanic
("Comment SCORE").

BRAND VOICE: direct, confident, no fluff, no hype, no emojis in the graphic text.
BRAND LOOK is fixed and monochrome (near-black #0A0A0A background, white + grey
text, a small triangle mark). You only write copy + choose format — the renderer
applies the look, so keep text tight and punchy.

AUDIENCE: owners/operators of local service businesses in the US."""

SCHEMA = r"""
Return ONLY a JSON array of exactly 3 objects. No prose outside the JSON.
Vary the formats across the 3 (roughly 2 reels + 1 carousel is ideal, since reels
win reach and carousels win conversions — but adapt to what your research says is
working right now). Each object is one of these shapes:

IMAGE (single graphic):
{
  "format": "image",
  "template": "stat" | "quote" | "myth" | "list" | "promo",
  "params": {
     // stat:  {"kicker": "...", "big": "17%", "sub": "one supporting sentence"}
     // quote: {"white": "main line", "muted": "second line"}
     // myth:  {"myth": "\"quoted myth\"", "truth": "the correction"}
     // list:  {"kicker":"...", "title":"headline", "items":["i1","i2","i3","i4"]}
     // promo: {"white":"line one", "muted":"line two"}
  },
  "caption": "full IG caption, ends with a Comment SCORE CTA + 8-10 hashtags",
  "rationale": "one line: what current trend/insight this is based on"
}

CAROUSEL (5-8 slides, hook first, CTA last):
{
  "format": "carousel",
  "slides": [
    {"kind":"cover","params":{"kicker":"...","lines":["Hook line 1","hook line 2"]}},
    {"kind":"stat","params":{"kicker":"...","big":"5 MIN","sub":"..."}},
    {"kind":"point","params":{"n":"01","kicker":"...","title":"...","sub":"..."}},
    {"kind":"quote","params":{"white":"...","muted":"..."}},
    {"kind":"cta","params":{"white":"SCORE YOUR SYSTEM","muted":"in 60 seconds.","foot":"..."}}
  ],
  "caption": "full IG caption + Comment SCORE CTA + hashtags",
  "rationale": "..."
}

REEL (animated text video, hook must land in ~1 second):
{
  "format": "reel",
  "spec": {
    "kicker": "SHORT LABEL",
    "hook": ["punchy line 1","line 2","line 3"],
    "beats": [
       {"kicker":"9:14 PM","lines":["short line","short line"]},
       {"kicker":"Business A","lines":["Texts back in","90 seconds."],"mark":"check"}
    ],
    "end": {"lines":["Same lead.","Different system."],"cta":"Comment \"SCORE\""}
  },
  "caption": "full IG caption + Comment SCORE CTA + hashtags",
  "rationale": "..."
}
Keep every on-screen line short (a few words) so it renders cleanly. Reels: 3-5 beats.
"""

def _call(messages, tools=None, max_tokens=4096):
    body = {"model": MODEL, "max_tokens": max_tokens, "system": BRAND, "messages": messages}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
        method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.load(r)

def _text(resp):
    return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")

def _extract_json(text):
    # grab the last top-level JSON array in the text
    depth, start = 0, None
    best = None
    for i, ch in enumerate(text):
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0 and start is not None:
                best = text[start:i+1]
    if not best:
        raise ValueError("no JSON array in model output:\n" + text[:2000])
    return json.loads(best)

def main():
    history = []
    hp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "history.json")
    if os.path.exists(hp):
        history = json.load(open(hp)).get("recent", [])[-50:]

    avoid = "\n".join(f"- {h}" for h in history) or "(none yet)"
    user = (
        "First, use web search to research what is performing and converting on "
        "Instagram RIGHT NOW (this week): trending reel formats and hooks, what "
        "content styles are getting reach and saves, and what works for local "
        "service-business / B2B marketing accounts. Do 3-6 searches.\n\n"
        "Then write 3 Black Arrow posts for today that apply those current, "
        "high-performing formats and hook styles to our message — while staying "
        "strictly on-brand. Make each post distinct.\n\n"
        "DO NOT repeat or lightly reword any of these previously used angles:\n"
        f"{avoid}\n\n"
        + SCHEMA
    )
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]
    resp = _call([{"role": "user", "content": user}], tools=tools, max_tokens=6000)
    specs = _extract_json(_text(resp))
    if not isinstance(specs, list) or len(specs) < 1:
        raise ValueError("expected a non-empty list of specs")
    print(json.dumps(specs, indent=2))

if __name__ == "__main__":
    main()
