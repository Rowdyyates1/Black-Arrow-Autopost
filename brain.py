#!/usr/bin/env python3
"""The Brain — strategic decision layer (Phase A).

Additive and feature-flagged: if brain_config.json is absent, enabled() is False
and generate.py behaves exactly as before. When present, before each post the
Brain picks an ELIGIBLE content category by balancing toward target ratios (with
a small exploration budget), records the decision with its reasoning/confidence,
updates strategy state, and appends a human-readable daily report.

State is stored as committed JSON (git is the database): every decision is a
commit, fully auditable. Later phases add evidence governance, claim validation,
experiments, performance-weighted optimization, news scoring, and repurposing.
"""
import os, json, random, datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(ROOT, "brain_config.json")
STATE = os.path.join(ROOT, "brain_state.json")
LOG = os.path.join(ROOT, "brain_log")
PUB = os.path.join(LOG, "published.json")          # media_id -> category/experiment
EXP = os.path.join(ROOT, "brain_experiments.json")  # experiment ledger

_ELIGIBLE = ("fully_eligible", "partially_eligible",
             "demonstration_only", "third_party_support_only")

def enabled():
    return os.path.exists(CONF)

def _load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default

def load_config():
    return _load(CONF, {})

def load_state():
    return _load(STATE, {"history": []})

def _effective_categories(cfg, state):
    """Categories with any auto-detected eligibility overrides (Phase E) applied."""
    cats = {k: dict(v) for k, v in cfg.get("categories", {}).items()}
    for k, o in (state or {}).get("eligibility_overrides", {}).items():
        cats.setdefault(k, {}).update(o)
    return cats

def _eligible_targets(cfg, state=None):
    cats = _effective_categories(cfg, state)
    elig = {k: v for k, v in cats.items()
            if v.get("eligibility", "fully_eligible") in _ELIGIBLE}
    total = sum(v.get("target_ratio", 0) for v in elig.values()) or 1.0
    targets = {k: v.get("target_ratio", 0) / total for k, v in elig.items()}
    return targets, elig

def _recent_distribution(state, keys, window=30):
    hist = [h.get("category") for h in state.get("history", [])[-window:] if h.get("category")]
    n = len(hist) or 1
    return {c: hist.count(c) / n for c in keys}

def decide(cfg, state, media_perf=None):
    """Choose the content category for this run. Returns a decision dict or None.
    media_perf (Phase C): [{id, like, comments}] used to attribute performance to
    categories and gently shift the mix toward what advances the objective."""
    base, elig = _eligible_targets(cfg, state)
    if not base:
        return None
    scores = category_scores(cfg, media_perf or [])
    targets, adjustment = optimized_targets(cfg, base, scores)
    dist = _recent_distribution(state, elig.keys())
    last = None
    for h in reversed(state.get("history", [])):
        if h.get("category"):
            last = h["category"]; break
    explore = float(cfg.get("exploration_budget", 0.08))

    if random.random() < explore:
        cat = random.choice(list(elig.keys()))
        reason = (f"Exploration ({explore:.0%} budget): sampling '{elig[cat].get('label', cat)}' "
                  f"to keep learning what performs, not just exploiting the current leader.")
        confidence = 0.4
        mode = "exploration"
    else:
        deficits = {c: targets[c] - dist.get(c, 0) for c in elig}
        ranked = sorted(deficits, key=lambda c: deficits[c], reverse=True)
        cat = ranked[0]
        if cat == last and len(ranked) > 1:      # avoid two in a row
            cat = ranked[1]
        reason = (f"Balancing the mix: '{elig[cat].get('label', cat)}' was the most under-served "
                  f"eligible category (target {targets[cat]:.0%}, recent {dist.get(cat, 0):.0%}).")
        confidence = 0.7
        mode = "mix-balancing"

    unavailable = [v.get("label", k) for k, v in _effective_categories(cfg, state).items()
                   if v.get("eligibility") in ("temporarily_unavailable", "prohibited")]
    c = elig[cat]
    return {
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "category": cat,
        "category_label": c.get("label", cat),
        "guidance": c.get("guidance", ""),
        "format_bias": c.get("format_bias"),
        "evidence_note": c.get("evidence_note", ""),
        "mode": mode,
        "reason": reason,
        "confidence": confidence,
        "objective": cfg.get("primary_objective", "balanced"),
        "targets": {k: round(v, 3) for k, v in targets.items()},
        "recent_distribution": {k: round(v, 3) for k, v in dist.items()},
        "performance_scores": {k: round(v, 1) for k, v in scores.items()},
        "allocation_adjustment": adjustment,
        "unavailable_categories": unavailable,
    }

def prompt_directive(decision):
    """The instruction injected into the generation prompt."""
    if not decision:
        return ""
    d = decision
    fmt = f" Prefer the {d['format_bias']} format when it fits." if d.get("format_bias") else ""
    ev = f"\nEvidence rule: {d['evidence_note']}" if d.get("evidence_note") else ""
    unavail = ", ".join(d["unavailable_categories"]) or "none"
    return (f"\n\nTODAY'S BRAIN DECISION — write this post in the category: "
            f"{d['category_label']}.\nWhy this category now: {d['reason']}\n"
            f"How to execute it: {d['guidance']}{fmt}{ev}\n"
            f"Categories currently unavailable (never use, never fabricate): {unavail}.")

_PROOF_SIGNALS = ["case study", "case studies", "testimonial", "success story",
                  "client results", "before and after", "% increase", "increased revenue",
                  "booked calls for", "results:", "here's what we did for"]
_FOUNDER_SIGNALS = ["founder", "my story", "i started", "about me", "meet the founder",
                    "our story", "why i built", "my journey"]

def monitor_site(site_text, state):
    """Phase E: hash the website; on a real change, scan for newly-published proof
    or founder material and AUTO-enable those categories (low ratio, grounded only
    in the site's own published text). Runs itself — no manual step. Returns notes."""
    import hashlib
    txt = (site_text or "").lower()
    h = hashlib.sha256(txt.encode()).hexdigest()[:16]
    if h == (state or {}).get("site_hash"):
        return None
    proof = [s for s in _PROOF_SIGNALS if s in txt]
    founder = [s for s in _FOUNDER_SIGNALS if s in txt]
    ov = dict((state or {}).get("eligibility_overrides", {}))
    notes = []
    if len(proof) >= 2 and "verified_proof" not in ov:
        ov["verified_proof"] = {"eligibility": "third_party_support_only", "target_ratio": 0.03,
            "guidance": "Reference ONLY case studies/results explicitly published on "
                        "blackarrow.ltd, quoting and attributing the site. Never extrapolate "
                        "or invent numbers.",
            "evidence_note": "verified_company_asset from the website; cite the site."}
        notes.append("Website appears to publish proof/case-study content — Verified Proof "
                     "auto-enabled at a low ratio, grounded strictly in the site's text.")
    if len(founder) >= 2 and "personal_founder" not in ov:
        ov["personal_founder"] = {"eligibility": "third_party_support_only", "target_ratio": 0.03,
            "guidance": "Use ONLY founder information explicitly published on blackarrow.ltd, "
                        "attributed. No invented stories or quotes.",
            "evidence_note": "verified_founder_information from the website; cite the site."}
        notes.append("Website appears to publish founder content — Personal / Founder "
                     "auto-enabled at a low ratio, grounded strictly in the site's text.")
    state["site_hash"] = h
    state["eligibility_overrides"] = ov
    os.makedirs(LOG, exist_ok=True)
    date = datetime.date.today().isoformat()
    with open(os.path.join(LOG, f"company_changes_{date}.json"), "a") as f:
        f.write(json.dumps({"date": date, "hash": h, "proof_signals": proof,
                            "founder_signals": founder, "actions": notes}) + "\n")
    if notes:
        with open(os.path.join(LOG, f"report_{date}.md"), "a") as f:
            for n in notes:
                f.write(f"  - company knowledge: {n}\n")
    return notes

def research_directive(cfg):
    """Phase D: bias research toward the configured sources and niche keywords."""
    r = cfg.get("research") or {}
    src, kw = r.get("monitor_sources", []), r.get("niche_keywords", [])
    parts = []
    if src:
        parts.append("Prioritize these sources for news/research: " + ", ".join(src) + ".")
    if kw:
        parts.append("Core niche keywords that define relevance: " + ", ".join(kw) + ".")
    return ("\n\n" + " ".join(parts)) if parts else ""

def record(decision, specs, state):
    """Persist the decision, update state, append the daily report."""
    if not decision:
        return
    os.makedirs(LOG, exist_ok=True)
    date = datetime.date.today().isoformat()
    fmt = specs[0].get("format") if specs else None
    entry = {**decision, "chosen_format": fmt,
             "post_rationale": (specs[0].get("rationale", "") if specs else "")}

    dp = os.path.join(LOG, f"decisions_{date}.json")
    day = _load(dp, [])
    day.append(entry)
    with open(dp, "w") as f:
        json.dump(day, f, indent=2)

    state.setdefault("history", []).append({"date": date, "category": decision["category"], "format": fmt})
    state["history"] = state["history"][-400:]
    with open(STATE, "w") as f:
        json.dump(state, f, indent=2)

    rp = os.path.join(LOG, f"report_{date}.md")
    new = not os.path.exists(rp)
    with open(rp, "a") as f:
        if new:
            f.write(f"# Black Arrow — Brain decisions · {date}\n\n")
        f.write(f"- **{entry['timestamp']}** — **{entry['category_label']}** "
                f"({entry['mode']}, confidence {entry['confidence']:.0%}, format {fmt}). "
                f"{entry['reason']}\n")
        adj = entry.get("allocation_adjustment")
        if adj:
            up = ", ".join(f"{c} {v:+.0%}" for c, v in adj.items())
            f.write(f"  - mix optimization (objective: {entry.get('objective')}): {up} "
                    f"based on measured performance.\n")

# ---- Phase C: performance attribution, mix optimization, experiments ---------
def _obj_engagement(m, weights):
    """Objective-weighted engagement from the metrics the API actually returns."""
    return (m.get("like", 0) * weights.get("like", 1.0)
            + m.get("comments", 0) * weights.get("comments", 3.0))

def record_published(media_id, category, fmt, experiment=None, angle=None):
    """Called at publish time to link a live media id to its category / experiment /
    angle (angle enables the repurposing flywheel)."""
    if not media_id:
        return
    os.makedirs(LOG, exist_ok=True)
    led = _load(PUB, [])
    led.append({"media_id": str(media_id), "category": category, "format": fmt,
                "experiment": experiment, "angle": angle,
                "date": datetime.date.today().isoformat()})
    with open(PUB, "w") as f:
        json.dump(led[-500:], f, indent=2)

def update_memory(cfg, media_perf, state):
    """Phase F: distil what's working into strategic memory fed back to generation."""
    mem = {}
    scores = category_scores(cfg, media_perf or [])
    eff = _effective_categories(cfg, state)
    if scores:
        top = sorted(scores, key=scores.get, reverse=True)[:3]
        mem["top_categories"] = [eff.get(c, {}).get("label", c) for c in top]
    completed = _load_exp().get("completed", [])
    if completed:
        mem["experiment_findings"] = [{"variable": e["variable"], "winner": e["winner"]}
                                      for e in completed[-5:]]
    led = {p["media_id"]: p for p in _load(PUB, [])}
    w = cfg.get("objective_metric_weights", {"like": 1.0, "comments": 3.0})
    fmt_agg = {}
    for m in (media_perf or []):
        p = led.get(str(m.get("id")))
        if p and p.get("format"):
            fmt_agg.setdefault(p["format"], []).append(_obj_engagement(m, w))
    favg = {f: sum(v) / len(v) for f, v in fmt_agg.items() if len(v) >= 3}
    if favg:
        mem["best_format"] = max(favg, key=favg.get)
    state["memory"] = mem
    return mem

def memory_directive(state):
    mem = (state or {}).get("memory") or {}
    bits = []
    if mem.get("top_categories"):
        bits.append("Top-performing categories so far: " + ", ".join(mem["top_categories"]) + ".")
    if mem.get("best_format"):
        bits.append("Best-performing format so far: " + mem["best_format"] + ".")
    if mem.get("experiment_findings"):
        f = mem["experiment_findings"][-1]
        bits.append(f"Recent experiment lean: for {f['variable']}, '{f['winner']}' did better.")
    return ("\n\nWHAT'S WORKED SO FAR (lean into these, but stay varied): " + " ".join(bits)) if bits else ""

def top_performers(cfg, media_perf, state):
    rcfg = cfg.get("repurposing", {})
    if not rcfg.get("enabled", True) or not media_perf:
        return []
    w = cfg.get("objective_metric_weights", {"like": 1.0, "comments": 3.0})
    led = {p["media_id"]: p for p in _load(PUB, [])}
    done = set((state or {}).get("repurposed", []))
    min_eng = rcfg.get("min_engagement", 50)
    scored = []
    for m in media_perf:
        p = led.get(str(m.get("id")))
        if p and p.get("angle") and p["media_id"] not in done:
            eng = _obj_engagement(m, w)
            if eng >= min_eng:
                scored.append((eng, p))
    scored.sort(reverse=True, key=lambda x: x[0])
    return [p for _, p in scored[:5]]

def pick_repurpose(cfg, state, media_perf):
    """Occasionally repurpose a proven past angle into a fresh derivative."""
    rcfg = cfg.get("repurposing", {})
    if not rcfg.get("enabled", True) or not _audience_ready(cfg, media_perf):
        return None
    if random.random() > float(rcfg.get("budget", 0.12)):
        return None
    cands = top_performers(cfg, media_perf, state)
    if not cands:
        return None
    c = cands[0]
    state.setdefault("repurposed", []).append(c["media_id"])
    state["repurposed"] = state["repurposed"][-200:]
    os.makedirs(LOG, exist_ok=True)
    date = datetime.date.today().isoformat()
    with open(os.path.join(LOG, f"repurpose_{date}.json"), "a") as f:
        f.write(json.dumps({"from_media": c["media_id"], "angle": c.get("angle"),
                            "category": c.get("category")}) + "\n")
    return {"angle": c.get("angle"), "category": c.get("category"), "format": c.get("format")}

def repurpose_prompt(rep):
    if not rep or not rep.get("angle"):
        return ""
    return (f"\n\nREPURPOSE — this angle already performed well: \"{rep['angle']}\". "
            f"Create a FRESH derivative of it today in a NEW format (not {rep.get('format')}), "
            f"with a new hook and different execution. Same core idea, new packaging.")

def category_scores(cfg, media_perf):
    """Average objective-weighted engagement per category, over posts we can match
    to a category, only where we have >= min_samples (else omitted, honest)."""
    opt = cfg.get("optimization", {})
    if not opt.get("enabled", True) or not media_perf:
        return {}
    led = {p["media_id"]: p for p in _load(PUB, [])}
    weights = cfg.get("objective_metric_weights", {"like": 1.0, "comments": 3.0})
    window = int(opt.get("window", 40)); min_s = int(opt.get("min_samples", 5))
    agg = {}
    for m in media_perf[:window]:
        p = led.get(str(m.get("id")))
        if p and p.get("category"):
            agg.setdefault(p["category"], []).append(_obj_engagement(m, weights))
    return {c: sum(v) / len(v) for c, v in agg.items() if len(v) >= min_s}

def optimized_targets(cfg, base_targets, scores):
    """Blend base ratios with performance share, clamped to per-category min/max.
    Returns (effective_targets, adjustment_note or None)."""
    opt = cfg.get("optimization", {})
    if not opt.get("enabled", True) or not scores:
        return base_targets, None
    w = float(opt.get("weight", 0.3))
    tot = sum(scores.values()) or 1.0
    cats = cfg.get("categories", {})
    eff = {}
    for c, bt in base_targets.items():
        val = (1 - w) * bt + w * (scores[c] / tot) if c in scores else bt
        mn = cats.get(c, {}).get("min_ratio", 0.0)
        mx = cats.get(c, {}).get("max_ratio", 1.0)
        eff[c] = min(mx, max(mn, val))
    s = sum(eff.values()) or 1.0
    eff = {c: v / s for c, v in eff.items()}
    note = {c: round(eff[c] - base_targets[c], 3)
            for c in eff if abs(eff[c] - base_targets[c]) >= 0.01}
    return eff, (note or None)

def _load_exp():
    return _load(EXP, {"active": None, "completed": []})

def _audience_ready(cfg, media_perf):
    """Experiments are meaningless without an audience. Auto-gate: only run once
    enough posts have accumulated AND we're seeing real engagement. Flips itself
    on automatically as the account grows — no manual step."""
    ecfg = cfg.get("experiments", {})
    min_hist = int(ecfg.get("min_history", 12))
    min_eng = int(ecfg.get("min_total_engagement", 30))
    published = len(_load(PUB, []))
    total_eng = sum((m.get("like", 0) + m.get("comments", 0)) for m in (media_perf or []))
    return published >= min_hist and total_eng >= min_eng

def pick_experiment(cfg, state, media_perf=None):
    """Return the variant to apply this run (starts one if none active), or None.
    Returns None during cold start (not enough audience data yet)."""
    ecfg = cfg.get("experiments", {})
    if not ecfg.get("enabled", True):
        return None
    if not _audience_ready(cfg, media_perf):
        return None
    data = _load_exp()
    active = data.get("active")
    if not active:
        backlog = ecfg.get("variables", [])
        if not backlog:
            return None
        tested = {c.get("variable") for c in data.get("completed", [])[-len(backlog):]}
        choices = [v for v in backlog if v["name"] not in tested] or backlog
        v = random.choice(choices)
        active = {"id": datetime.datetime.utcnow().strftime("exp_%Y%m%d%H%M%S"),
                  "variable": v["name"], "hypothesis": v.get("hypothesis", ""),
                  "options": v["options"], "instructions": v.get("instructions", {}),
                  "started": datetime.date.today().isoformat(), "assigned": 0}
        data["active"] = active
        with open(EXP, "w") as f:
            json.dump(data, f, indent=2)
    opts = active["options"]
    variant = opts[active.get("assigned", 0) % len(opts)]
    return {"experiment_id": active["id"], "variable": active["variable"],
            "variant": variant, "instruction": active.get("instructions", {}).get(variant, "")}

def experiment_prompt(exp):
    if not exp or not exp.get("instruction"):
        return ""
    return (f"\n\nACTIVE EXPERIMENT — for this post only, test the "
            f"'{exp['variable']}' variable with the '{exp['variant']}' approach: "
            f"{exp['instruction']}")

def note_experiment_assignment(exp):
    if not exp:
        return
    data = _load_exp(); active = data.get("active")
    if active and active["id"] == exp["experiment_id"]:
        active["assigned"] = active.get("assigned", 0) + 1
        with open(EXP, "w") as f:
            json.dump(data, f, indent=2)

def score_experiments(cfg, media_perf):
    """Tally each variant's performance; conclude when min_samples reached (honest,
    flagged low-confidence). Logs the lean to the daily report."""
    data = _load_exp(); active = data.get("active")
    if not active or not media_perf:
        return
    weights = cfg.get("objective_metric_weights", {"like": 1.0, "comments": 3.0})
    perf = {str(m.get("id")): _obj_engagement(m, weights) for m in media_perf}
    tallies = {o: {"n": 0, "sum": 0.0} for o in active["options"]}
    for p in _load(PUB, []):
        e = p.get("experiment")
        if e and e.get("experiment_id") == active["id"] and p["media_id"] in perf:
            t = tallies.setdefault(e["variant"], {"n": 0, "sum": 0.0})
            t["n"] += 1; t["sum"] += perf[p["media_id"]]
    min_s = int(cfg.get("experiments", {}).get("min_samples", 6))
    if tallies and all(t["n"] >= min_s for t in tallies.values()):
        avgs = {o: (t["sum"] / t["n"] if t["n"] else 0) for o, t in tallies.items()}
        winner = max(avgs, key=avgs.get)
        data["completed"].append({
            "id": active["id"], "variable": active["variable"], "winner": winner,
            "averages": {k: round(v, 1) for k, v in avgs.items()},
            "samples": {o: t["n"] for o, t in tallies.items()},
            "confidence": "low-sample", "concluded": datetime.date.today().isoformat()})
        data["active"] = None
        with open(EXP, "w") as f:
            json.dump(data, f, indent=2)
        os.makedirs(LOG, exist_ok=True)
        with open(os.path.join(LOG, f"report_{datetime.date.today().isoformat()}.md"), "a") as f:
            f.write(f"  - experiment concluded ({active['variable']}): '{winner}' led "
                    f"(low sample size — treat as a lean, not proof).\n")

def log_evidence(specs):
    """Phase B: record each post's evidence class + claims, note any auto-rewrites."""
    if not specs:
        return
    os.makedirs(LOG, exist_ok=True)
    date = datetime.date.today().isoformat()
    recs, rewrites = [], 0
    for s in specs:
        ev = s.get("evidence") or {}
        claims = ev.get("claims") or []
        rewrites += sum(1 for c in claims if c.get("status") == "rewritten")
        recs.append({"format": s.get("format"), "class": ev.get("class"),
                     "disclosure": ev.get("disclosure", ""), "claims": claims})
    ep = os.path.join(LOG, f"evidence_{date}.json")
    day = _load(ep, [])
    day.extend(recs)
    with open(ep, "w") as f:
        json.dump(day, f, indent=2)
    if rewrites:
        with open(os.path.join(LOG, f"report_{date}.md"), "a") as f:
            f.write(f"  - claim validation: {rewrites} unsupported claim(s) "
                    f"auto-rewritten into a supportable form.\n")

def log_topics(specs):
    """Phase D: record the chosen angle, its score, and rejected alternatives."""
    if not specs:
        return
    recs = []
    for s in specs:
        t = s.get("topic")
        if t:
            recs.append({"chosen": t.get("chosen"), "score": t.get("score"),
                         "rejected": t.get("rejected", []), "category": s.get("_category")})
    if not recs:
        return
    os.makedirs(LOG, exist_ok=True)
    date = datetime.date.today().isoformat()
    tp = os.path.join(LOG, f"topics_{date}.json")
    day = _load(tp, [])
    day.extend(recs)
    with open(tp, "w") as f:
        json.dump(day, f, indent=2)
