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

v2 changes (2026-07-18):
  * Fixed keyword system: TOOLS / TRIAL / SCALE only. No more per-post invented
    keywords.
  * Single DM mention per post (the CTA line itself; never a second "DM the
    keyword to start" style instruction).
  * Done-for-you services: NO pricing anywhere, ever. Meeting first.
  * Offer stack context: free tools are lead magnets; the platform
    (blackarrow.ltd/app) has a 14-day no-card trial and a give-a-month-get-a-
    month referral; /app added to the default company pages.
"""
import os, json, re, sys, html, urllib.parse, urllib.request

try:
    import brain                      # strategic decision layer (optional/feature-flagged)
except Exception:
    brain = None

API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = os.environ.get("MODEL", "claude-sonnet-5")
N = int(os.environ.get("POSTS_PER_RUN", "1"))
HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------- #
# Live context: the website + recent post performance
# --------------------------------------------------------------------------- #
def _company_pages():
    """Which pages the Brain reads as the source of truth. Editable via
    brain_config.json -> "company_pages". Defaults include /tools and /app so
    new lead magnets and the platform are picked up automatically."""
    try:
        cfg = json.load(open(os.path.join(HERE, "brain_config.json")))
        if cfg.get("company_pages"):
            return cfg["company_pages"]
    except Exception:
        pass
    return ["https://blackarrow.ltd", "https://blackarrow.ltd/tools",
            "https://blackarrow.ltd/app"]

def _fetch_one(url, cap=3000):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode("utf-8", "ignore")
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
        return text[:cap]
    except Exception as e:
        return f"(could not fetch: {e})"

def fetch_site():
    """Read every configured company page (homepage + /tools + /app by default)
    so the Brain sees current offers, tools, and lead magnets — and notices new
    ones."""
    return "\n\n".join(f"[{u}]\n{_fetch_one(u)}" for u in _company_pages())[:10000]

def fetch_media_struct():
    """Structured recent-post metrics for the Brain's attribution (Phase C)."""
    uid = os.environ.get("IG_USER_ID"); tok = os.environ.get("IG_ACCESS_TOKEN")
    if not (uid and tok):
        return []
    try:
        q = urllib.parse.urlencode({"fields": "like_count,comments_count",
                                    "limit": "50", "access_token": tok})
        url = f"https://graph.instagram.com/v21.0/{uid}/media?{q}"
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.load(r).get("data", [])
        return [{"id": m.get("id"), "like": m.get("like_count") or 0,
                 "comments": m.get("comments_count") or 0} for m in data]
    except Exception:
        return []

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

THE OFFER STACK (what the CTAs point at — read the live site context for the
current details, but these are the fixed rails):
1. FREE TOOLS = LEAD MAGNETS (blackarrow.ltd/tools). Everything on that page is
   free value and is used as a lead magnet: the calculators, the audits, the AI
   builders, and Black Arrow OS (the free pocket CRM tool). No signup, no card.
   Feature them generously — they ARE the top of the funnel.
2. THE PLATFORM (blackarrow.ltd/app). The all-in-one Black Arrow platform: CRM,
   unified inbox, two-way texting, booking, quiz funnels, automated missed-call
   callbacks, review collection, win-backs, referral tracking, revenue
   reporting. Promote with its real offers: 14-day free trial, full access, no
   card needed, cancel anytime; and the referral deal (refer a business, when
   they subscribe you both get a free month, tracked automatically).
3. DONE-FOR-YOU SERVICES. Black Arrow builds the whole system for clients.
   HARD RULE: NEVER state, estimate, or hint at pricing for done-for-you
   services — no dollar amounts, no ranges, no ad-spend tiers, no "starting
   at". The only path is: request a meeting, Black Arrow diagnoses the
   pipeline, then scope and pricing are discussed there. Requests are reviewed
   personally with a response within one business day.

CONTENT MIX: most posts are pure free value. Lead-magnet posts featuring the
free tools and the platform's free trial are a first-class category — cycle
them in regularly (the category system handles ratios). Regularly (about 1 in
4) teach what Black Arrow actually builds and why it works — the four systems
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

CTA RULES — exactly one DM call to action per post, and the account uses ONLY
THREE KEYWORDS, ever. Do not invent new keywords. Route by intent:
- TOOLS  -> any free tool / lead magnet / calculator / Black Arrow OS.
- TRIAL  -> the platform: the 14-day no-card free trial or the referral deal.
- SCALE  -> done-for-you: the reader wants Black Arrow to build it for them
            (leads to a meeting request; remember: no pricing in the post).
Write the CTA as a natural line that ends with the keyword in quotes, e.g.:
- "The calculator takes four numbers. DM 'TOOLS'."
- "See it with your own pipeline. 14 days free. DM 'TRIAL'."
- "Want it built around your numbers? DM 'SCALE'."
THE KEYWORD APPEARS EXACTLY ONCE in the entire post (caption + on-graphic text
combined, counting both). The DM line IS the instruction. NEVER add a second
instruction like "DM the keyword to start", "send us the word above", or any
restatement of how to DM. One mention. Never use "link in bio". The account is
the sender, so "DM" means DMing this account. NEVER name a person. Only "Black
Arrow" or "the Black Arrow team".

EVIDENCE GOVERNANCE — every claim must be grounded in one of these classes:
- verified_company_fact / verified_company_capability (only from the Black Arrow
  website/context provided; things the business genuinely does),
- first_party_demonstration (a clearly-labeled EXAMPLE of a system Black Arrow can
  build: a follow-up sequence, missed-call text-back, CRM pipeline, etc.),
- third_party_research (a credible external study, attributed, in qualified language),
- informed_interpretation ("this could...", "owners should consider..."),
- general_pattern (honest "most shops..." framing, never a fabricated percentage).
PROHIBITED under any framing: invented revenue / lead / conversion / booked-call
numbers, invented client names or testimonials, screenshots implied to be a real
client account, invented case studies or campaign results, invented founder stories
or quotes, claims that Black Arrow produced a third-party study's result, unsupported
guarantees, or any specific outcome Black Arrow "achieved" without verified evidence.
Also prohibited: any price, cost range, or budget tier for done-for-you services.
If a useful angle would need a prohibited claim, REWRITE it into a supportable form
(a labeled demonstration, a qualified citation, or an honest general pattern) rather
than dropping it. Demonstrations/mockups must carry a short disclosure such as
"Example workflow" or "Illustrative — not a client account"."""

SCHEMA = r"""
OUTPUT: only the raw JSON array of exactly {N} object(s) — no markdown code
fences, nothing before or after it. Keep each "rationale" to one short sentence.
Vary formats over time. Reels win reach; carousels win saves/depth; single
images are quick value. Pick the format that best fits today's angle and what
the research says is working.

Every caption is formatted to be scannable, never a wall of text. Use real line
breaks (\n): a punchy first line, then 2-4 short chunks separated by a blank line
(\n\n), each chunk one or two short sentences. Then the ONE keyword DM CTA on its
own line (keyword must be TOOLS, TRIAL, or SCALE; it appears once in the whole
post and is never followed by a second "how to DM" instruction). Then EXACTLY 5
relevant hashtags on the final line. Numbered steps get their own lines. Keep it
teaching something genuinely useful.

Every post ALSO includes an "evidence" object recording how its claims are grounded:
"evidence": {"class": "<evidence class>", "disclosure": "<short label or empty>",
 "claims": [{"text": "the material claim", "status": "verified|qualified|illustrative|third_party|rewritten"}]}
and a "topic" object: {"chosen": "the angle", "score": 0-100, "rejected": ["alt angle", "alt angle"]}.
If it's a demonstration/mockup, also put the disclosure text into the caption. Shapes:

IMAGE:
{"format":"image","template":"stat|quote|myth|list|promo","params":{...},
 "caption":"useful caption, one keyword DM CTA, then exactly 5 hashtags",
 "rationale":"one line: the current trend/insight + the value this delivers"}
  stat  params: {"kicker","big","sub"}
  quote params: {"white","muted"}
  myth  params: {"myth","truth"}
  list  params: {"kicker","title","items":[4 short items]}
  promo params: {"kicker","white","muted","sub","cta"}
    kicker: short label like "Free tool" or "14 days free" (NEVER a DM
    instruction — the cta pill is the card's single DM mention).
    sub: one supporting line about the specific offer.
    cta: 'DM "TOOLS"' or 'DM "TRIAL"' or 'DM "SCALE"'.
    If the caption already contains the keyword CTA, the on-card cta pill counts
    as the graphic's mention — do not also write the keyword in the caption
    body a second time; put it in ONE place only.

CAROUSEL (5-8 slides, hook first, real value in the middle, DM CTA last):
{"format":"carousel","slides":[
  {"kind":"cover","params":{"kicker","lines":["hook 1","hook 2"]}},
  {"kind":"point","params":{"n":"01","kicker","title","sub"}},
  {"kind":"stat","params":{"kicker","big","sub"}},
  {"kind":"quote","params":{"white","muted"}},
  {"kind":"cta","params":{"white":"one short question hook","button":"DM \"TOOLS|TRIAL|SCALE\"","foot":"one supporting line that does NOT mention DMing"}}],
 "caption":"...","rationale":"..."}
The cta slide has ONE call to action only: the button. Do not repeat "DM me"
anywhere else on that slide (the foot line supports, it never re-instructs).

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
  "end":{"lines":["payoff line","second line"],"cta":"DM \"TOOLS|TRIAL|SCALE\""},
  "audio":"one of: dark | minimal premium | cinematic tension | driving bold"},
 "caption":"...","rationale":"..."}
The end card shows the cta pill as its single call to action. If the cta pill
carries the keyword, the caption's CTA line should carry it instead and the end
card cta can be a short action phrase; either way the keyword appears exactly
once across the whole post. Choose "audio" to match the post's emotion AND
Black Arrow's brand (confident, premium, a little dark). The renderer lays a
track of that mood under the reel. Keep every on-screen line to a few words.
Deliver the actual tip inside the reel.
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
    """Find the JSON array. Tolerates markdown code fences and a truncated tail
    (salvages the completed objects rather than crashing)."""
    start = text.find("[")
    if start == -1:
        raise ValueError("no JSON array in model output:\n" + text[:2000])
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    # truncated before the array closed — salvage complete objects
    frag = text[start + 1:]
    objs, d, s = [], 0, None
    for i, c in enumerate(frag):
        if c == "{":
            if d == 0:
                s = i
            d += 1
        elif c == "}":
            d -= 1
            if d == 0 and s is not None:
                try:
                    objs.append(json.loads(frag[s:i + 1]))
                except Exception:
                    pass
    if objs:
        sys.stderr.write(f"warning: output was truncated; salvaged {len(objs)} post(s)\n")
        return objs
    raise ValueError("no complete JSON array (output truncated):\n" + text[-2000:])

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
- CLAIM VALIDATION: extract every material claim in the post. Each must map to an
  allowed evidence class. Auto-REWRITE any unsupported or prohibited claim (invented
  metrics, fake client results/testimonials, unearned outcomes) into a supportable
  form: a clearly-labeled demonstration, a qualified third-party citation, or an
  honest general pattern. Never delete the post, never fabricate. Fill each post's
  "evidence" object honestly and mark any rewritten claim status "rewritten".
- PRICING CHECK: done-for-you services never carry a price, range, or budget
  tier. If a draft mentions one, strip it and route the reader to a meeting.
- KEYWORD CHECK: the only DM keywords that exist are TOOLS, TRIAL, and SCALE.
  Replace any other keyword with the right one of the three (TOOLS = free
  tools/lead magnets, TRIAL = the platform/free trial/referral, SCALE =
  done-for-you). The keyword must appear EXACTLY ONCE across the caption and
  all on-graphic text combined. Delete any second mention and any "DM the
  keyword to start" style re-instruction — the CTA line is the instruction.
- The post must be worth paying for — real steps/numbers/scripts, not vague tips.
- Keep it unmistakably Black Arrow: confident, premium, a little dark, useful.
- Never name a person. Only "Black Arrow" or "the Black Arrow team".
- Exactly one keyword DM call to action, and exactly 5 relevant hashtags.
- Caption must be scannable: short chunks separated by blank lines (\n\n), not a
  wall of text. CTA on its own line, hashtags on the final line.
- Keep every on-screen video line short (a few words) so nothing runs off-frame.
Return ONLY the final JSON array, nothing else."""

def review(specs):
    """Second pass: grade against the elite bar and rewrite/replace weak posts."""
    try:
        msg = ("Draft post spec(s) to edit to the elite standard:\n\n"
               + json.dumps(specs, indent=2))
        resp = _call([{"role": "user", "content": msg}], max_tokens=12000,
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

    # THE BRAIN — decide category + experiment + repurpose before generating
    decision, state, experiment, repurpose = None, None, None, None
    if brain and brain.enabled():
        try:
            cfg = brain.load_config(); state = brain.load_state()
            media_struct = fetch_media_struct()
            brain.monitor_site(site, state)                 # Phase E: eligibility auto-updates
            brain.score_experiments(cfg, media_struct)      # conclude any ready experiment
            brain.update_memory(cfg, media_struct, state)   # Phase F: distil what works
            decision = brain.decide(cfg, state, media_struct)
            experiment = brain.pick_experiment(cfg, state, media_struct)
            repurpose = brain.pick_repurpose(cfg, state, media_struct)
            if repurpose and decision and repurpose.get("category"):
                decision["category"] = repurpose["category"]   # keep the derivative coherent
                decision["category_label"] = cfg.get("categories", {}).get(
                    repurpose["category"], {}).get("label", repurpose["category"])
        except Exception as e:
            sys.stderr.write(f"brain decision skipped: {e}\n")
            decision, state, experiment, repurpose = None, None, None, None

    user = (
        "STEP 1 — Research with web search (3-6 searches): (a) what reel/carousel "
        "formats, hooks, and angles are getting the most engagement on Instagram "
        "RIGHT NOW for local service-business / B2B owners, and (b) any genuinely "
        "recent, relevant marketing or software developments (platform/algorithm "
        "changes, new tools) worth interpreting for these owners. Then brainstorm "
        "3-5 candidate angles for today and score each 0-100 on importance, novelty, "
        "audience + brand relevance, actionability, evidence availability, and risk. "
        "Pick the highest-scoring angle that fits today's category. Record it in the "
        "post's 'topic' field with the score and the rejected alternatives. For any "
        "news angle: verify it is current, cite the source, and be the interpreter "
        "('what this means for your shop'), never a generic reposter.\n\n"
        "STEP 2 — Read this current context:\n\n"
        f"BLACK ARROW WEBSITE (source of truth for what the business does today):\n{site}\n\n"
        f"RECENT POST PERFORMANCE (do more of what worked, drop what didn't):\n{perf}\n\n"
        "DO NOT repeat or reword these past angles:\n" f"{avoid}\n\n"
        f"STEP 3 — Write {N} post(s) for today. Each must deliver a real, usable "
        "tactic an owner can act on this week to make more money, be built on a "
        "currently-working format, hold to every voice rule, open and close an "
        "attention loop, and end on a DM CTA."
        + (brain.prompt_directive(decision) if decision else "")
        + (brain.experiment_prompt(experiment) if experiment else "")
        + (brain.repurpose_prompt(repurpose) if repurpose else "")
        + (brain.memory_directive(state) if (brain and decision) else "")
        + (brain.research_directive(cfg) if (brain and decision) else "")
        + "\n\n" + SCHEMA.replace("{N}", str(N))
    )
    tools = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}]
    resp = _call([{"role": "user", "content": user}], tools=tools, max_tokens=12000)
    specs = _extract_json(_text(resp))
    if not isinstance(specs, list) or not specs:
        raise ValueError("expected a non-empty list of specs")
    specs = review(specs)          # elite-standard editor pass before anything ships
    if not isinstance(specs, list) or not specs:
        raise ValueError("editor returned no specs")

    # stamp category + experiment onto each spec so publishing can attribute them
    if decision:
        for s in specs:
            s.setdefault("_category", decision["category"])
    if experiment:
        for s in specs:
            s["_experiment"] = {"experiment_id": experiment["experiment_id"],
                                "variant": experiment["variant"]}

    if brain and decision:         # log the strategic decision + update state + report
        try:
            brain.record(decision, specs, state)
        except Exception as e:
            sys.stderr.write(f"brain record skipped: {e}\n")
    if brain and brain.enabled():  # Phase B/D: log evidence + scored topics
        try:
            brain.log_evidence(specs)
            brain.log_topics(specs)
        except Exception as e:
            sys.stderr.write(f"brain evidence/topic log skipped: {e}\n")
    if brain and experiment:       # Phase C: advance experiment variant assignment
        try:
            brain.note_experiment_assignment(experiment)
        except Exception as e:
            sys.stderr.write(f"brain experiment note skipped: {e}\n")

    print(json.dumps(specs, indent=2))

if __name__ == "__main__":
    main()
