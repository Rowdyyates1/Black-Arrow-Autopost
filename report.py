#!/usr/bin/env python3
"""Roll the Brain's logs into one readable report (brain_log/rollup.md).
Run any time:  python report.py
"""
import os, json, glob, datetime, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(ROOT, "brain_log")

def _load(p, d):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return d

def main():
    state = _load(os.path.join(ROOT, "brain_state.json"), {"history": []})
    exp = _load(os.path.join(ROOT, "brain_experiments.json"), {"active": None, "completed": []})
    hist = state.get("history", [])[-60:]
    dist = collections.Counter(h.get("category") for h in hist if h.get("category"))

    L = ["# Black Arrow — Brain rollup",
         f"_generated {datetime.date.today().isoformat()}_", "",
         f"## Content mix (last {len(hist)} posts)"]
    for c, n in dist.most_common():
        L.append(f"- {c}: {n} ({n / max(1, len(hist)):.0%})")

    mem = state.get("memory") or {}
    if mem:
        L += ["", "## What's working"]
        if mem.get("top_categories"):
            L.append("- top categories: " + ", ".join(mem["top_categories"]))
        if mem.get("best_format"):
            L.append("- best format: " + mem["best_format"])
        for f in mem.get("experiment_findings", []):
            L.append(f"- experiment lean: {f['variable']} -> {f['winner']}")

    ov = state.get("eligibility_overrides") or {}
    if ov:
        L += ["", "## Auto-enabled from the website", "- " + ", ".join(ov.keys())]

    if exp.get("active"):
        a = exp["active"]
        L += ["", "## Active experiment",
              f"- {a['variable']}: {a['options']} (assigned {a.get('assigned', 0)})"]
    if exp.get("completed"):
        L += ["", "## Concluded experiments (low-sample leans, not proof)"]
        for e in exp["completed"][-10:]:
            L.append(f"- {e['variable']}: winner '{e['winner']}' {e.get('averages', {})}")

    rewrites = 0
    for f in glob.glob(os.path.join(LOG, "evidence_*.json")):
        for r in _load(f, []):
            rewrites += sum(1 for c in r.get("claims", []) if c.get("status") == "rewritten")
    L += ["", "## Truthfulness",
          f"- unsupported claims auto-rewritten (all time): {rewrites}"]

    out = "\n".join(L) + "\n"
    os.makedirs(LOG, exist_ok=True)
    with open(os.path.join(LOG, "rollup.md"), "w") as f:
        f.write(out)
    print(out)

if __name__ == "__main__":
    main()
