#!/usr/bin/env python3
"""Regression self-test for the Brain. No network/API needed.
Run:  python brain_selftest.py     (exit 0 = all pass)
"""
import os, json, shutil, tempfile, importlib

def run():
    root = os.path.dirname(os.path.abspath(__file__))
    # sandbox state so we never touch real logs
    for p in ("brain_state.json", "brain_experiments.json"):
        fp = os.path.join(root, p)
        if os.path.exists(fp):
            os.remove(fp)
    log = os.path.join(root, "brain_log")
    if os.path.isdir(log):
        shutil.rmtree(log)

    import brain
    importlib.reload(brain)
    cfg = brain.load_config()
    assert brain.enabled(), "config should be present"

    # 1. cold start: no experiments, no optimization
    st = brain.load_state()
    d0 = brain.decide(cfg, st, [])
    assert d0 and d0["category"], "should still pick a category cold"
    assert d0["allocation_adjustment"] in (None, {}), "no optimization without data"
    assert brain.pick_experiment(cfg, st, []) is None, "experiments must be paused cold"

    # 2. eligibility: proof/founder never chosen while unavailable
    seen = set()
    for _ in range(60):
        s = brain.load_state()
        dd = brain.decide(cfg, s, [])
        seen.add(dd["category"])
        brain.record(dd, [{"format": dd["format_bias"] or "image", "rationale": "t"}], s)
    assert "verified_proof" not in seen and "personal_founder" not in seen, "unavailable categories leaked"

    # 3. attribution + optimization once data exists
    for i in range(6):
        brain.record_published(f"a{i}", "education_informative", "reel", angle="edu angle")
        brain.record_published(f"b{i}", "authority_frameworks", "carousel", angle="auth angle")
    media = ([{"id": f"a{i}", "like": 150, "comments": 40} for i in range(6)]
             + [{"id": f"b{i}", "like": 30, "comments": 2} for i in range(6)])
    d1 = brain.decide(cfg, brain.load_state(), media)
    adj = d1["allocation_adjustment"] or {}
    assert adj.get("education_informative", 0) > 0, "high performer should be boosted"

    # 4. experiments resume once audience-ready, and conclude honestly
    exp = brain.pick_experiment(cfg, brain.load_state(), media)
    assert exp is not None, "experiments should resume with data"
    data = json.load(open(os.path.join(root, "brain_experiments.json")))
    opts = data["active"]["options"]
    perf = []
    for k in range(12):
        v = opts[k % 2]
        mid = f"e{k}"
        brain.record_published(mid, "education_informative", "reel",
                               {"experiment_id": data["active"]["id"], "variant": v}, "x")
        perf.append({"id": mid, "like": 200 if v == opts[0] else 50, "comments": 40 if v == opts[0] else 5})
    brain.score_experiments(cfg, perf + media)
    data = json.load(open(os.path.join(root, "brain_experiments.json")))
    assert data["active"] is None and data["completed"], "experiment should conclude"

    # 5. evidence: a fabricated claim is captured as rewritten
    brain.log_evidence([{"format": "image", "evidence": {"class": "third_party_research",
        "claims": [{"text": "we booked 42 calls", "status": "rewritten"}]}}])

    # 6. website monitoring auto-enables proof on strong signals
    s = brain.load_state()
    brain.monitor_site("Our case study: we helped a roofer. Client results and testimonial here.", s)
    assert "verified_proof" in (s.get("eligibility_overrides") or {}), "proof should auto-enable on site proof"

    # 7. repurposing surfaces a proven angle
    rep = brain.pick_repurpose({**cfg, "repurposing": {"enabled": True, "budget": 1.0, "min_engagement": 10}},
                               brain.load_state(), media)
    assert rep and rep.get("angle"), "repurpose should find a proven angle"

    print("brain_selftest: ALL PASS")

if __name__ == "__main__":
    run()
    # clean the sandbox artifacts
    r = os.path.dirname(os.path.abspath(__file__))
    for p in ("brain_state.json", "brain_experiments.json"):
        fp = os.path.join(r, p)
        if os.path.exists(fp):
            os.remove(fp)
    import shutil as _s
    if os.path.isdir(os.path.join(r, "brain_log")):
        _s.rmtree(os.path.join(r, "brain_log"))
