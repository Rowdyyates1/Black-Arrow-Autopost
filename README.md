# Black Arrow — Research-Driven Daily Instagram Auto-Poster

Every day: researches what's converting on Instagram right now → writes 3 fresh,
on-brand posts in the highest-performing formats (reels + carousels) → renders
them in the blackarrow.ltd style → publishes all 3 automatically. Never repeats.

**→ Start with [SETUP_GUIDE.md](SETUP_GUIDE.md).**

## Pipeline
`generate.py` (the brain: Claude API + web search → 3 post specs)
→ `run_daily.py generate` (renders each spec via the renderers below, writes a manifest, logs history)
→ workflow commits media (gives it a public URL)
→ `run_daily.py publish` → `publish_instagram.py` (Meta Graph API: image / carousel / reel)

## Files
- `generate.py` — researches trends and writes 3 post specs as JSON (edit BRAND/SCHEMA to tune voice)
- `brand.py` — fixed visual system: single-image templates + carousel slides
- `render_reel.py` — animated text reel (720x1280 MP4) from a spec
- `run_daily.py` — orchestrates generate → render → publish for all 3
- `publish_instagram.py` — Meta Graph API publisher
- `.github/workflows/daily.yml` — the daily cron
- `history.json` — auto-updated log of used angles (never-repeat memory)
- `sample_specs.json` — example specs for a free local dry run

## Dry run (no API spend)
```
pip install pillow            # + ffmpeg for reels
python run_daily.py generate --specs sample_specs.json
```
Renders into `published/<date>/` so you can inspect before going live.

## Secrets (GitHub → Settings → Secrets and variables → Actions)
`IG_USER_ID`, `IG_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`  ·  optional var `MODEL`.
