#!/usr/bin/env python3
"""The brain.

Each run it:
  1. reads blackarrow.ltd so content tracks the current business direction,
  2. pulls recent post performance from Instagram (best effort) to learn what's
     actually getting engagement,
  3. web-searches what's converting on Instagram right now,
  4. writes N fresh, on-brand posts as structured specs the renderer turns into
     images / carousels / reels.

Every post is held to the stop-slop rules (no AI tells) and conversion-copy /
psychology principles, drives a DM, and delivers real value.

Requires: ANTHROPIC_API_KEY.
Optional: MODEL (default claude-sonnet-5), POSTS_PER_RUN (default 1),
          IG_USER_ID + IG_ACCESS_TOKEN (to read past performance).
Prints a JSON array of post specs to stdout.
"""
import os, json, re, sys, html, urllib.parse, urllib.request

API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.environ.get("MODEL", "claude-sonnet-5")
N = int(os.environ.get("POSTS_PER_RUN", "1"))
HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------- #
# Live context: the website + recent post performance
# --------------------------------------------------------------------------- #
def fetch_site(url="https://blackarrow.ltd"):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "ignore")
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
        return text[:4000]
    except Exception as e:
        return f"(could not fetch site: {e})"

def fetch_performance():
    """Best-effort: what's getting engagement lately. Needs insights permission."""
    uid = os.environ.get("IG_USER_ID"); tok = os.environ.get("IG_ACCESS_TOKEN")
    if not (uid and tok):
        return "(no performance data yet)"
    try:
        q = urllib.parse.urlencode({
            "fields": "caption,media_type,like_count,comments_count,timestamp",
            "limit": "25", "access_token": tok})
        url = f"https://graph.instagram.com/v21.0/{uid}/media?{q}"
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r).get("data", [])
        scored = []
        for m in data:
            eng = (m.get("like_count") or 0) + (m.get("comments_count") or 0)
            cap = (m.get("caption") or "").split("\n")[0][:80]
            scored.append((eng, m.get("media_type", ""), cap))
        scored.sort(reverse=True)
        if not scored:
            return "(no posts yet)"
        top = "\n".join(f"- [{mt}] {eng} eng: {cap}" for eng, mt, cap in scored[:5])
        low = "\n".join(f"- [{mt}] {eng} eng: {cap}" for eng, mt, cap in scored[-3:])
        return f"BEST performers:\n{top}\n\nWEAKEST:\n{low}"
    except Exception as e:
        return f"(performance unavailable: {e})"

# --------------------------------------------------------------------------- #
# The standard the copy is held to
# --------------------------------------------------------------------------- #
BRAND = """You write for BLACK ARROW (blackarrow.ltd) — a growth-infrastructure
agency that builds paid advertising, automated lead follow-up, and CRM systems
for service businesses: contractors, home services, roofing, HVAC, car
dealerships, medical/dental, legal. Core line: "Advertising creates
opportunities. Systems create revenue." Signature facts: only ~17% of service
businesses answer a lead within an hour; answering in under 5 minutes roughly
doubles the close rate. The account speaks AS Black Arrow. Refer to the team only
as "Black Arrow" or "the Black Arrow team". NEVER name an individual person.

MISSION OF THIS ACCOUNT: be the most useful account a service-business owner
follows. Build trust by giving away real, usable value — specific things an
owner can do this week to make more money — then convert that trust into DM
conversations that can become clients. Nurture first. Sell second.

CONTENT MIX: most posts are pure free value. But regularly (about 1 in 4) teach
what Black Arrow actually builds and why it works — the four systems
(acquisition, instant/automated follow-up, CRM operations, retention), the
under-5-minute speed-to-lead advantage, missed-call recovery, review and
reactivation systems. People can only hire you for what they understand, so
inform them about the offer. Even these posts lead with value and teach, they
never hard-sell. Also mix in genuinely useful, current marketing and software
news and updates relevant to service businesses (pull from your research) —
explained plainly with the clear "so what does this mean for your shop".

STANDARD — this account is for elite operators and owners serious about growth.
Every post must read like it came from a top strategist, not a content mill.
Non-negotiable:
- Coherent and complete. Every line makes sense on its own. Nothing half-baked.
- Polished and professional. No tacky hype, no gimmicks, no clickbait you don't
  pay off, no cheesy motivational-poster lines, no emoji spam, no fake urgency,
  no "hustle" cringe.
- Specific and true. Never invent statistics. Use the known Black Arrow facts or
  frame patterns honestly ("most shops...", not a fabricated percentage).
- Worth paying for. Every post must be so useful the reader thinks "I'd have paid
  for this." Give the real steps, numbers, scripts, and settings, not vague advice.
- Logically airtight. Any tactic or test must actually work in the real world as
  described. Spell out who does what. Example: to test your own response time, a
  friend or secret shopper submits a lead or calls in, NOT the owner "calling
  themselves". Never ship a tip or test with a logic hole.
- If an angle isn't genuinely useful and clearly on-brand, do not ship it. Pick a
  sharper one. Quiet and sharp beats loud and tacky, every time.
The reader should think "this account is elite" within one second.

VOICE — hold every word to these rules (stop-slop):
- Active voice, human subject doing something. No passive.
- Cut adverbs and filler. No throat-clearing openers ("Here's the thing").
- Be specific. Real numbers, real steps. No vague declaratives, no "streamline
  / optimize / leverage / unlock / elevate / game-changer / supercharge".
- Talk to one person as "you". Put them in the room.
- Vary sentence length. Two beats three. No em dashes anywhere. No emojis in the
  on-graphic text (a rare one in the caption is fine).
- No "not X, but Y" contrast crutch. State Y.
- Nothing that sounds like an AI pull-quote. If it sounds like a LinkedIn
  motivational line, rewrite it.
- Simple words: "use" not "utilize", "help" not "facilitate".

COPY & PSYCHOLOGY:
- Hook must land its idea in the first second (first line / first frame).
- Open a curiosity loop early; close it by the end (never leave them cheated).
- Lead with the specific outcome or the named problem the owner already feels.
- Give the real tactic in the post. Don't tease value and withhold it. Trust is
  built by actually helping. Then the CTA earns the DM.
- Every post ends by inviting a DM to start a conversation (see CTA rules).

CTA RULES — one DM call to action per post, tied to the topic, using a single
relevant keyword. The account is the sender, so "DM" means DMing this account.
NEVER name a person. Only "Black Arrow" or "the Black Arrow team". Shape (write
your own; match the keyword to the post's topic):
- "Want fast lead-nurture automations running in your business? DM 'SPEED'."
- "Want this exact follow-up system built for your shop? DM 'SYSTEM'."
- "Want us to find where your leads are leaking? DM 'LEAKS'."
Never use "link in bio". Exactly one CTA per post."""

SCHEMA = r"""
OUTPUT: only a JSON array of exactly {N} object(s). No prose outside the JSON.
Vary formats over time. Reels win reach; carousels win saves/depth; single
images are quick value. Pick the format that best fits today's angle and what
the research says is working.

Every caption: teach something genuinely useful, then ONE keyword DM CTA, then
EXACTLY 5 relevant hashtags (no more, no less). Shapes:

IMAGE:
{"format":"image","template":"stat|quote|myth|list|promo","params":{...},
 "caption":"useful caption, one keyword DM CTA, then exactly 5 hashtags",
 "rationale":"one line: the current trend/insight + the value this delivers"}
  stat  params: {"kicker","big","sub"}
  quote params: {"white","muted"}
  myth  params: {"myth","truth"}
  list  params: {"kicker","title","items":[4 short items]}
  promo params: {"white","muted"}

CAROUSEL (5-8 slides, hook first, real value in the middle, DM CTA last):
{"format":"carousel","slides":[
  {"kind":"cover","params":{"kicker","lines":["hook 1","hook 2"]}},
  {"kind":"point","params":{"n":"01","kicker","title","sub"}},
  {"kind":"stat","params":{"kicker","big","sub"}},
  {"kind":"quote","params":{"white","muted"}},
  {"kind":"cta","params":{"white":"one short question hook","button":"DM \"WORD\"","foot":"one supporting line"}}],
 "caption":"...","rationale":"..."}
The cta slide has ONE call to action only: the button. Do not repeat "DM me"
elsewhere on that slide. Pick a single memorable keyword for the DM.

SLIDESHOW (the same slides as a carousel, but rendered as a vertical VIDEO with
on-brand music and posted as a reel). Choose this over a carousel when the topic
benefits from music, motion, and reach; choose a plain carousel when depth and
saves matter more (it stays swipeable and silent):
{"format":"slideshow","slides":[ ...same slide kinds as a carousel... ],
 "audio":"dark | minimal premium | cinematic tension | driving bold",
 "caption":"...","rationale":"..."}

REEL (animated text; hook lands in ~1s; open a loop, close it):
{"format":"reel","spec":{
  "kicker":"SHORT LABEL",
  "hook":["punchy line 1","line 2"],
  "beats":[{"kicker":"","lines":["short","short"],"mark":"check?"}, ... 3-5 beats],
  "end":{"lines":["payoff line","second line"],"cta":"DM me"},
  "audio":"one of: dark | minimal premium | cinematic tension | driving bold"},
 "caption":"...","rationale":"..."}
Choose "audio" to match the post's emotion AND Black Arrow's brand (confident,
premium, a little dark). The renderer lays a track of that mood under the reel.
Keep every on-screen line to a few words. Deliver the actual tip inside the reel.
"""

def _call(messages, tools=None, max_tokens=6000, system_override=None):
    body = {"model": MODEL, "max_tokens": max_tokens,
            "system": system_override or BRAND, "messages": messages}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"x-api-key": API_KEY, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.load(r)

def _text(resp):
    return "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")

def _extract_json(text):
    depth, start, best = 0, None, None
    for i, ch in enumerate(text):
        if ch == "[":
            if depth == 0: start = i
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0 and start is not None:
                best = text[start:i+1]
    if not best:
        raise ValueError("no JSON array in model output:\n" + text[:2000])
    return json.loads(best)

EDITOR = """You are the ruthless brand editor for Black Arrow. Elite operators
read this account. Your job is to make sure nothing tacky, gimmicky, incoherent,
generic, or off-brand ever ships.

Score each draft post 1-10 on: coherence, polish/professionalism, real usable
value, on-brand fit, hook strength, and stop-slop cleanliness (no adverbs, no em
dashes, active voice, specific, no AI-pull-quote cadence, no "not X but Y").

Then return the FINAL posts as a JSON array in the exact same schema. Rules:
- Rewrite any weak line until it clears the bar. If a whole post can't clear an
  8+, replace its angle with a stronger, genuinely useful one.
- Kill every gimmick, hype word, fake stat, cheesy motivational line, and any
  sentence that doesn't quite make sense.
- LOGIC CHECK: every tactic or test must actually work as described. If a "test"
  requires the owner to do something impossible or nonsensical (e.g. call
  themselves to test response time), fix the logic or replace it. Airtight only.
- The post must be worth paying for — real steps/numbers/scripts, not vague tips.
- Keep it unmistakably Black Arrow: confident, premium, a little dark, useful.
- Never name a person. Only "Black Arrow" or "the Black Arrow team".
- Exactly one keyword DM call to action, and exactly 5 relevant hashtags.
Return ONLY the final JSON array, nothing else."""

def review(specs):
    """Second pass: grade against the elite bar and rewrite/replace weak posts."""
    try:
        msg = ("Draft post spec(s) to edit to the elite standard:\n\n"
               + json.dumps(specs, indent=2))
        resp = _call([{"role": "user", "content": msg}], max_tokens=6000,
                     system_override=EDITOR)
        return _extract_json(_text(resp))
    except Exception as e:
        sys.stderr.write(f"editor pass skipped: {e}\n")
        return specs

def main():
    history = []
    hp = os.path.join(HERE, "history.json")
    if os.path.exists(hp):
        history = json.load(open(hp)).get("recent", [])[-60:]
    avoid = "\n".join(f"- {h}" for h in history) or "(none yet)"

    site = fetch_site()
    perf = fetch_performance()

    user = (
        "STEP 1 — Research with web search (3-6 searches): what reel/carousel "
        "formats, hooks, and content angles are getting the most engagement on "
        "Instagram RIGHT NOW, especially for local service-business / B2B owners. "
        "Note what's driving comments, shares and saves this week.\n\n"
        "STEP 2 — Read this current context:\n\n"
        f"BLACK ARROW WEBSITE (source of truth for what the business does today):\n{site}\n\n"
        f"RECENT POST PERFORMANCE (do more of what worked, drop what didn't):\n{perf}\n\n"
        "DO NOT repeat or reword these past angles:\n" f"{avoid}\n\n"
        f"STEP 3 — Write {N} post(s) for today. Each must deliver a real, usable "
        "tactic an owner can act on this week to make more money, be built on a "
        "currently-working format, hold to every voice rule, open and close an "
        "attention loop, and end on a DM CTA.\n\n"
        + SCHEMA.replace("{N}", str(N))
    )
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]
    resp = _call([{"role": "user", "content": user}], tools=tools)
    specs = _extract_json(_text(resp))
    if not isinstance(specs, list) or not specs:
        raise ValueError("expected a non-empty list of specs")
    specs = review(specs)          # elite-standard editor pass before anything ships
    if not isinstance(specs, list) or not specs:
        raise ValueError("editor returned no specs")
    print(json.dumps(specs, indent=2))

if __name__ == "__main__":
    main()
