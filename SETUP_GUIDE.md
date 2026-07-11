# Black Arrow — Daily Auto-Poster Setup (research-driven)

Every day this: **(1)** researches what's converting on Instagram right now, **(2)** writes 3 fresh, on-brand Black Arrow posts in the best-performing formats (a mix of reels and carousels), **(3)** renders them in your blackarrow.ltd style, and **(4)** publishes all 3 automatically — each driving to the Revenue Score at blackarrow.ltd/#assessment via a "Comment SCORE" DM prompt. It never repeats an angle.

It runs on **GitHub Actions**. Rendering and publishing are free; the research-and-writing brain uses the **Claude API** (a paid key — budget ~$15–30/mo at the quality tier you picked).

**One-time setup ≈ 25 minutes.** Do the parts in order. After that it's hands-off.

---

## You'll need three secrets
1. `IG_USER_ID` — your Instagram Business account id
2. `IG_ACCESS_TOKEN` — a Meta token allowed to publish
3. `ANTHROPIC_API_KEY` — powers the daily research + copywriting

---

## Part 1 — Instagram must be a Business account on a Page (5 min)
Instagram's API only publishes from a **Business/Creator** account linked to a Facebook Page.
1. Instagram app → **Settings → Account type and tools → Switch to Professional → Business.**
2. Create a Facebook Page if you don't have one (facebook.com/pages/create).
3. Link them: Facebook Page → **Settings → Linked accounts → Instagram → Connect.**

## Part 2 — Meta token + account id (10 min)
1. **developers.facebook.com → My Apps.** Use your existing app (or Create App → type **Business**).
2. In the app: **Add Product → Instagram → set up.**
3. Open **Graph API Explorer**, select your app, **Generate Access Token**, and grant:
   `instagram_basic`, `instagram_content_publish`, `pages_show_list`, `pages_read_engagement`, `business_management`.
4. **IG_USER_ID:** run `me/accounts` → copy your Page `id`; then run
   `{page-id}?fields=instagram_business_account` → the number returned is your **IG_USER_ID**.
5. **A token that never expires** (recommended): business.facebook.com/settings → **Users → System Users → Add** (Admin) → assign your **app** + **Page** → **Generate token** → pick the 5 permissions above → generate. Copy it — that's **IG_ACCESS_TOKEN**.

## Part 3 — Claude API key (3 min)
1. Go to **console.anthropic.com → API Keys → Create Key.** Copy it — that's **ANTHROPIC_API_KEY**.
2. Add a little credit (Billing). At 3 posts/day with daily research, expect roughly $15–30/month on the quality model. To spend less, set the `MODEL` variable (Part 4) to a lighter model.

## Part 4 — GitHub (7 min)
1. Create a free **github.com** account if needed.
2. New **repository** (name it `blackarrow-autopost`), set it **Public** (this is what gives the rendered media a public link for Instagram to fetch — only the finished posts are exposed, and they're going on public IG anyway).
3. Upload every file from this folder, keeping the structure (especially `.github/workflows/daily.yml`).
4. **Settings → Secrets and variables → Actions → New repository secret** — add all three:
   `IG_USER_ID`, `IG_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`.
5. (Optional) same screen → **Variables** tab → add `MODEL` = `claude-sonnet-5` (default) or `claude-opus-4-8` (max quality, higher cost).
6. **Settings → Actions → General → Workflow permissions → Read and write → Save.**
7. Open the **Actions** tab and enable workflows.

## Part 5 — Test, then forget
1. **Actions → Daily Instagram posts → Run workflow.** Watch it research, generate, commit, and publish. Check your Instagram — 3 new posts.
2. It now runs **daily at 14:00 UTC (~9am Central)**. Change the `cron` line in `.github/workflows/daily.yml` to adjust (it's UTC).

---

## Living with it
- **Never repeats:** `history.json` logs every angle and is fed back to the brain each day as a do-not-repeat list.
- **Formats:** the brain picks the mix based on current research (usually ~2 reels + 1 carousel). Reels are animated text videos rendered on-brand — no filming.
- **Tune the voice:** edit the `BRAND` / `SCHEMA` text at the top of `generate.py`.
- **Change the look:** all visual styling is in `brand.py`; the reel animation is in `render_reel.py`.
- **Dry run without spending API tokens:** `python run_daily.py generate --specs sample_specs.json`.
- **Cost control:** lower `MODEL`, reduce `max_uses` for web search in `generate.py`, or drop to 2 posts/day (edit the `[:3]` slice in `run_daily.py`).
- **Comment-to-DM:** set your CRM to reply to the keyword **SCORE** with blackarrow.ltd/#assessment — that's what turns posts into leads.

## Judgment
It posts unattended. Glance at the feed a couple times a week, and pause the workflow (Actions → ⋯ → Disable) around anything sensitive or a launch you'd rather handle by hand.
