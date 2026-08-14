# Pricing & positioning — 2026-07-19

Falsifiable goal: anchor our pricing against Polsia's take-rate and adjacent
"AI employee" products, then propose flat per-seat tiers.

## Polsia (verified, from findings/polsia-teardown.md)

$49/month base (daily cycles + $5 API credit, 5 free tasks/mo) **plus 20%
take-rate on all economic activity touched** — revenue AND managed ad spend
combined (e.g. $5k revenue + $3k ad spend = $1,600/mo on top of the
subscription) ([cto.new](https://cto.new/guides/polsia-review),
[preuve.ai](https://preuve.ai/blog/polsia-review)). ~$1/on-demand task beyond
the free allotment. Pricing reportedly not shown up front at signup
(Product Hunt reviews) — confirms opacity as part of the pattern, not a one-off.

## Adjacent "AI employee" pricing (one line each)

- **Artisan (Ava, AI SDR)** — publicly listed from $280/mo (Intern) to
  $660/mo (Employee), but real mid-market deals run $2,000–$5,000+/mo
  driven by outreach volume + seat count, annual contracts, pricing not
  fixed/public ([landbase.com](https://www.landbase.com/blog/artisan-ai-pricing), [11x.ai guide](https://www.11x.ai/guides/artisan-pricing)).
- **11x (Alice, AI SDR)** — starts ~$2,000/mo ($36k/yr Growth plan) per
  official framing, but third-party reporting puts real single-worker cost
  at $5,000–$15,000/mo once volume/channels scale; not published, sales-gated
  ([11x.ai/pricing](https://www.11x.ai/products/alice/pricing), [marketbetter.ai](https://marketbetter.ai/blog/11x-ai-pricing-2026/)).
- **Lindy (general AI agent/assistant)** — flat published tiers: $49.99/mo
  Plus, $99.99/mo Pro, $199.99/mo Max, no permanent free tier, voice add-ons
  billed separately ([lindy.ai/pricing](https://www.lindy.ai/pricing)).
- **Relevance AI (agent platform)** — Free / $19/mo Pro / $234/mo Team
  (billed annually), usage-metered on "Actions" + "Vendor Credits," not
  per-seat, unlimited agents included ([relevanceai.com/pricing](https://relevanceai.com/pricing)).

Pattern: the two products actually named "AI employees that act" (Artisan,
11x) hide pricing behind sales calls and land at $2k–$15k/mo once real usage
kicks in. The two general-purpose agent platforms (Lindy, Relevance) publish
flat/usage tiers under $250/mo but don't do bounded, accountable "employee"
work with approval gates — they're tool builders, not staffed roles.

## Proposed pricing: flat per-employee-seat, published

No take-rate, no revenue share, no sales call required to see a number —
the seat price is the entire bill outside of infra the owner already owns
(gap 4: we operate inside their accounts, so we have no ad-spend or Stripe
flow to tax in the first place).

| Tier | Price | Seats included | Rationale |
|---|---|---|---|
| **Starter** | $99/employee/mo | 1–2 employees | Undercuts Lindy Max ($199.99) per seat while being a *named, gated* worker, not a general chat agent — anchors us as cheaper than the nearest "real employee" product bracket (Artisan Intern $280) and priced like a SaaS seat, not a sales-call quote. |
| **Team** | $79/employee/mo | 3–10 employees, volume discount | Undercuts Artisan's public Employee plan ($660) by 8x per seat, still comfortably above Relevance's usage-metered floor — priced for a company running Engineer + Marketer + one more role, matching docs/mvp.md's two-role MVP plus headroom. |
| **Scale** | Custom, still per-seat (~$59–69/employee/mo at volume) | 10+ employees | Only lever that moves is seat count and support SLA — never a % of revenue or spend, unlike Polsia and unlike Artisan/11x's volume-based creep. Published floor price stated even at this tier so "custom" never means "hidden." |

## Positioning one-liner

**Polsia takes 20% of everything it touches and won't tell you the number
until you're in; we charge a flat per-employee seat you can quote from the
website — legible pricing for a legible product.**
