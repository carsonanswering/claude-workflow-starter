# Polsia teardown — 2026-07-19

Falsifiable goal: what Polsia actually ships vs marketing vapor, and the gaps a legibility-first "AI employees" product can exploit.

## What it is

Polsia (polsia.com) is an autonomous "AI runs your company while you sleep" platform: nine specialized agents on staggered schedules (Orchestrator/"CEO", business planning, competitor research, social media, email outreach, customer support, ads management, code generation, finance) that operate a business end-to-end with minimal human input ([preuve.ai review](https://preuve.ai/blog/polsia-review), [cto.new review](https://cto.new/guides/polsia-review)). Positioned as an autonomous AI co-founder / incubator hybrid. Founder: Ben Cera (early CloudKitchens operator; appears as "Ben Broca" on Product Hunt). Funding: $30M Series A at $250M valuation, May 2026, Sound Ventures + True Ventures ([preuve.ai](https://preuve.ai/blog/polsia-review), [cto.new](https://cto.new/guides/polsia-review)). Launched on Product Hunt ~Jan 2026, 144 upvotes, #13 day rank ([Product Hunt](https://www.producthunt.com/products/polsia)).

## Verified features (real, shipped)

- **Nine scheduled agents built on Claude Code CLI.** The public repo ([github.com/PolsiaAI/Polsia](https://github.com/PolsiaAI/Polsia), 83 stars / 38 forks, Python) shows the architecture: each agent executes Claude Code CLI as a subprocess authenticated via `~/.claude` OAuth credentials; FastAPI + WebSocket backend, Next.js 14 frontend, PostgreSQL (15 tables) + ChromaDB + Redis, Celery Beat scheduling (agents run every 2–6h or on-demand), Docker Compose, nginx. A "sandbox mode" flag gates real actions (posts, emails, ad spend, financial transactions). Minimal commit activity; no visible license.
- **Infrastructure bundling.** Provisions servers, Stripe, email addresses, GitHub repos per company ([preuve.ai](https://preuve.ai/blog/polsia-review)).
- **Fast execution when inputs are good.** Andreas Klinger's "surprise me" test: research, mission statement, email setup, Twitter post within minutes ([search summary via cto.new/preuve](https://cto.new/guides/polsia-review)). SyntaxGTM case study: landing pages and ad creatives generated quickly ([cto.new](https://cto.new/guides/polsia-review)).
- **Live operations feed** at polsia.com/live — a transparency-flavored marketing surface ([Product Hunt](https://www.producthunt.com/products/polsia)).
- **Founder-admitted 90/10 split**: AI handles "90% of responses"; the remaining 10% needs human oversight ([founder comment, Product Hunt](https://www.producthunt.com/products/polsia)).

## Claims unverified / vapor

- **"500+ companies with $450k+ ARR"** (Product Hunt) vs **"800+ companies, $700K+ ARR"** (GitHub org) vs **"1,000+ companies ran autonomously"** (same GitHub org tagline) — self-reported, mutually inconsistent, and their own dashboard reportedly shows ARR slipping ([Product Hunt](https://www.producthunt.com/products/polsia), [GitHub org](https://github.com/PolsiaAI), [cto.new](https://cto.new/guides/polsia-review)).
- **Portfolio companies appear hollow.** Independent spot-check of three Polsia-launched companies (FleetNova, DeckFlow, Panelwright) found each was "a nice-looking landing page with marketing copy" and nothing behind it ([panphora on X](https://x.com/panphora/status/2039792403788292156)).
- **Task completion is unreliable.** One audit found **~21% real success rate**; tasks routinely marked "complete" that never deploy ([cto.new](https://cto.new/guides/polsia-review), Trustpilot themes).
- **"Negotiates with VCs" / manages founder inboxes** — marketing copy, no independent verification ([Product Hunt](https://www.producthunt.com/products/polsia)).
- **Documented failure case:** Rest of World profiled a user paying $199/month for months with 7 signups, zero conversions ([via preuve.ai](https://preuve.ai/blog/polsia-review)).

## Pricing

- **$49/month base** — daily autonomous cycles + $5/month API credit; 5 free monthly tasks (10 first month) ([Product Hunt](https://www.producthunt.com/products/polsia)).
- **20% take-rate on ALL economic activity** the platform touches — revenue AND managed ad spend combined. Example: $5k revenue + $3k ad spend = $1,600/month on top of subscription ([cto.new](https://cto.new/guides/polsia-review), [preuve.ai](https://preuve.ai/blog/polsia-review)).
- **~$1 per on-demand task** (credit system); one nightly task free ([cto.new](https://cto.new/guides/polsia-review)).
- Users report pricing was not visible up front at signup ([Product Hunt review](https://www.producthunt.com/products/polsia)).

## Trust / reliability record

Trustpilot **1.8/5, 35 reviews, ~80% one-star** (June 2026) ([Trustpilot](https://www.trustpilot.com/review/polsia.com)). Recurring, specific complaints:

- Tasks marked complete that never deployed; credits burned on failed actions with limited refunds (one user: 44 credits owed, five escalations Apr 14–22 2026, zero responses; another got $59 back of $251 spent).
- Automated outreach sent with wrong names and wrong prices; cold emails to journalists the user never approved ([cto.new](https://cto.new/guides/polsia-review)).
- **Asset lock-in / "domain hostage"**: custom domains stayed attached to Polsia's Render account after claimed release; user needed Render support to force-remove. Code and infra live on Polsia servers and become inaccessible after cancellation ([Trustpilot via search](https://www.trustpilot.com/review/polsia.com), [preuve.ai](https://preuve.ai/blog/polsia-review)).
- Support response measured in weeks; accounts stuck paused after payment.

## Gaps we exploit (legibility/auditability angle)

1. **No approval gates anywhere.** Polsia's core design is full autonomy; reviews trace most damage (unauthorized cold emails, wrong-price outreach, ad spend on failed tasks) directly to the absence of human approval before irreversible actions. Our per-role approval gates attack the exact failure mode their 1-star reviews document. cto.new explicitly recommends "directed alternatives with human approval gates" — the market is asking for our product.
2. **Completion is unauditable.** "Complete" ≠ deployed (~21% real success in one audit). A readable work journal with verifiable artifacts per step (diff, sent-email log, deploy URL) turns their biggest trust failure into our headline feature. Their polsia.com/live feed shows they know transparency sells — but it's a spectator stream, not an audit trail.
3. **Billing opacity compounds black-box execution.** Credits burn on invisible failed work with no refund path. Legible per-task journals make "what did I pay for" answerable; metered billing tied to *verified* outcomes is a direct counter-position.
4. **Asset lock-in.** Domains, code, and infra held on Polsia accounts, hostage-style exits. "Your repo, your domain, your Stripe — we operate inside accounts you own" is a cheap, sharp wedge.
5. **Anonymous swarm vs named roles.** Nine agents with function labels but no accountable identity; the 20% take-rate makes it an incubator wearing a SaaS mask, misaligned with users who already have revenue. Named AI employees with bounded mandates + flat pricing reads as trustworthy where "AI CEO takes 20% of everything it touches" reads as predatory (their own preuve verdict: unsuitable for first-time founders — i.e., for their marketing's target audience).
6. **Technically shallow moat.** The open repo shows the product is Claude Code CLI subprocesses + Celery cron + Postgres. Nothing there prevents a competitor from matching capability while adding the legibility layer they lack.

## Sources

- https://polsia.com/ (tagline only; thin marketing page)
- https://www.producthunt.com/products/polsia
- https://preuve.ai/blog/polsia-review
- https://cto.new/guides/polsia-review
- https://github.com/PolsiaAI and https://github.com/PolsiaAI/Polsia
- https://www.trustpilot.com/review/polsia.com (1.8/5; page itself 403s to bots — details via search excerpts)
- https://x.com/panphora/status/2039792403788292156 (hollow portfolio companies)
- https://crevio.co/blog/is-polsia-legit (corroborating, not fetched directly)
