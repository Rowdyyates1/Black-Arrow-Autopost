# Black Arrow — Autonomous Content Strategy Engine

Every day, three times, on GitHub Actions: the **Brain** researches, decides what
to post and why, generates it, renders it on-brand, publishes to feed + Story, then
learns from performance and adjusts. Runs itself; state lives in committed JSON
(git is the database — every decision is an auditable commit).

**Setup:** see [SETUP_GUIDE.md](SETUP_GUIDE.md). Secrets: `IG_USER_ID`,
`IG_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`.

## The daily loop
`generate.py` runs the Brain (`brain.py`) → picks an eligible category, an
experiment variant (once there's an audience), and maybe a repurpose → writes the
post with an editor + claim-validation pass → `run_daily.py` renders
(`brand.py` / `render_reel.py` / `music_gen.py`) and publishes
(`publish_instagram.py`) → records performance for the next cycle.

## The Brain (fully self-adapting, no manual updates)
- **Category selection** — balances toward target ratios among *eligible* categories, with an exploration budget. (`brain_config.json`)
- **Evidence governance + claim validation** — every claim maps to an evidence class; unsupported claims are auto-rewritten into a labeled demonstration, a qualified citation, or an honest general pattern. Proof/Founder stay **unavailable** until real evidence exists — never fabricated.
- **Content-mix optimization** — attributes performance to categories (objective-weighted) and shifts the mix toward what works, within bounds. Auto-pauses cold, auto-resumes with data.
- **Experiments** — one at a time (hook style, CTA style, opening frame); assigns variants, tallies, concludes honestly (small samples = a lean, not proof). Auto-gated on audience.
- **News + topic scoring** — scores candidate angles and interprets recent developments; prioritizes configured sources/keywords.
- **Website monitoring** — hashes blackarrow.ltd; when it genuinely publishes a case study or founder story, auto-enables those categories at a low ratio, grounded strictly in the site's own text.
- **Repurposing flywheel + strategic memory** — rebuilds proven angles into fresh derivatives; feeds "what's worked" back into generation.

## Files
| File | Role |
|------|------|
| `generate.py` | The brain's decision cycle + content writing (Anthropic API + web search) |
| `brain.py` | Strategy: eligibility, optimization, experiments, evidence logs, memory, site monitor |
| `brain_config.json` | **All strategy settings — edit freely, no code** |
| `brand.py` | Fixed visual system (overflow-safe layout engine) |
| `render_reel.py` | Animated reels + slideshows (paced, on-brand generated music) |
| `music_gen.py` | Original dark instrumental loop generator |
| `publish_instagram.py` | Meta Graph API publisher (feed, carousel, reel, story) with retries |
| `run_daily.py` | Orchestrator |
| `report.py` | `python report.py` → `brain_log/rollup.md` summary |
| `brain_selftest.py` | `python brain_selftest.py` → regression check (no API needed) |

## Where the Brain writes (all committed, auditable)
`brain_state.json` (strategy state + memory + eligibility overrides) ·
`brain_experiments.json` (experiment ledger) ·
`brain_log/` (daily `report_*.md`, `decisions_*.json`, `evidence_*.json`,
`topics_*.json`, `published.json`, `company_changes_*.json`, `rollup.md`).

## Tuning
Everything strategic is in `brain_config.json`: objective + metric weights,
category ratios and eligibility, exploration/optimization/experiment settings,
repurposing, funnel stages, research sources. Change the file, commit, done.
Disable the Brain entirely by removing `brain_config.json` (the system reverts to
plain research-and-post). Music: drop licensed tracks named by mood into `music/`.
