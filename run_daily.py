#!/usr/bin/env python3
"""Daily orchestrator.

  python run_daily.py generate    # research + write 3 specs + render all media
  python run_daily.py publish     # publish the 3 rendered posts to Instagram

'generate' runs the AI brain (generate.py), renders each spec into
published/<date>/postN/, writes a manifest, and logs the hooks to history.json
so future days never repeat. The GitHub workflow commits the media between the
two steps so Instagram can fetch it by public URL.

A --specs <file> flag lets you feed pre-made specs (e.g. for a local dry run
without spending API tokens).
"""
import os, sys, json, datetime, subprocess
import brand

ROOT = os.path.dirname(os.path.abspath(__file__))
def rel(*p): return os.path.join(ROOT, *p)

def _slug(spec, i):
    return f"post{i+1}_{spec.get('format','image')}"

def render_spec(spec, outdir, date):
    """Render one spec into outdir. Returns post.json dict."""
    os.makedirs(outdir, exist_ok=True)
    fmt = spec.get("format", "image")
    base = os.path.basename(outdir)
    images, video, cover = [], None, None

    # media lives under published/<date>/<base>/ ; the public URL is repo-root
    # based, so the recorded path must include the published/ prefix.
    if fmt == "reel":
        import render_reel
        vpath = os.path.join(outdir, "reel.mp4")
        render_reel.render_reel(spec["spec"], vpath)
        video = f"published/{date}/{base}/reel.mp4"
        brand.reel_cover(spec["spec"]).save(os.path.join(outdir, "cover.png"), "PNG")
        cover = f"published/{date}/{base}/cover.png"
    elif fmt == "carousel":
        imgs = brand.render_carousel(spec["slides"])
        for j, im in enumerate(imgs):
            im.save(os.path.join(outdir, f"image_{j}.png"), "PNG")
            images.append(f"published/{date}/{base}/image_{j}.png")
    else:  # image
        im = brand.render({"template": spec["template"], "params": spec["params"]})
        im.save(os.path.join(outdir, "image_0.png"), "PNG")
        images.append(f"published/{date}/{base}/image_0.png")

    post = {"caption": spec["caption"], "format": fmt,
            "rationale": spec.get("rationale", "")}
    if video:
        post["video"] = video
        if cover: post["cover"] = cover
    else:
        post["images"] = images
    with open(os.path.join(outdir, "post.json"), "w") as f:
        json.dump(post, f, indent=2)
    return post

def cmd_generate():
    date = datetime.date.today().isoformat()
    day_dir = rel("published", date)

    # 1) get specs (from brain, or from --specs file for dry runs)
    if "--specs" in sys.argv:
        specs = json.load(open(sys.argv[sys.argv.index("--specs") + 1]))
    else:
        out = subprocess.run([sys.executable, rel("generate.py")],
                             capture_output=True, text=True)
        if out.returncode != 0:
            sys.exit("brain failed:\n" + out.stderr[-3000:])
        # generate.py prints the JSON array (may include trailing logs)
        txt = out.stdout
        start, depth, buf = txt.find("["), 0, None
        specs = json.loads(txt[txt.find("["): txt.rfind("]") + 1])

    # 2) render each
    n = int(os.environ.get("POSTS_PER_RUN", "1"))
    manifest = {"date": date, "posts": []}
    hooks = []
    for i, spec in enumerate(specs[:n]):
        outdir = os.path.join(day_dir, _slug(spec, i))
        post = render_spec(spec, outdir, date)
        manifest["posts"].append(f"published/{date}/{_slug(spec, i)}/post.json")
        hooks.append(spec.get("rationale") or spec.get("caption", "")[:80])

    with open(rel("published", date, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    # 3) log history so we never repeat
    hp = rel("history.json")
    hist = json.load(open(hp)) if os.path.exists(hp) else {"recent": []}
    hist["recent"] = (hist.get("recent", []) + hooks)[-200:]
    with open(hp, "w") as f:
        json.dump(hist, f, indent=2)

    print(f"generated {len(manifest['posts'])} posts for {date}")
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as f:
            f.write(f"manifest=published/{date}/manifest.json\n")
            f.write(f"date={date}\n")

def cmd_publish():
    import publish_instagram as pub
    date = os.environ.get("POST_DATE") or datetime.date.today().isoformat()
    manifest = json.load(open(rel("published", date, "manifest.json")))
    public_base = os.environ["PUBLIC_BASE"].rstrip("/")
    failures = 0
    for pj in manifest["posts"]:
        post = json.load(open(rel(pj)))
        try:
            res = pub.publish_post(post, public_base)
            print(f"published {pj} -> {res.get('id')}")
        except Exception as e:
            failures += 1
            print(f"FAILED {pj}: {e}")
    if failures:
        sys.exit(f"{failures} post(s) failed to publish")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "generate"
    if mode == "generate": cmd_generate()
    elif mode == "publish": cmd_publish()
    else: sys.exit("usage: run_daily.py [generate|publish]")
