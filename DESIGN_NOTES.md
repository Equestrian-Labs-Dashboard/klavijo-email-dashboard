# Design plan — Klaviyo Email Marketing Dashboard

**Subject matter**: email marketing performance for an equestrian/lifestyle retail
brand (Corro Cavali), pulling from Klaviyo. Audience: internal marketing/finance
team reviewing monthly performance. Job: fast read of health (sales, list growth)
plus a deeper campaign vs. flow comparison.

## Color
- `#12241F` — ink green (base background, references saddle leather / stable dark)
- `#F6F2E9` — parchment (card surfaces, warm off-white, not the AI-cliché cream on its own — paired with green instead of terracotta)
- `#C9A227` — brass/buckle gold (primary accent, sparingly — one hero number, key highlights)
- `#7C9A82` — sage (secondary accent, muted, for flows vs. campaigns distinction)
- `#E4572E` — clay red (used only for negative deltas)
- `#2E4034` — deep moss (borders, muted text on parchment)

## Type
- Display/headline: "Fraunces" (serif, has an equestrian/editorial warmth, distinct from default AI serif choices) — used for the hero number and section titles.
- Body/data: "Inter" — clean tabular figures for the metric grids.

## Layout
- Not a SaaS card grid. Structural device: a horizontal ledger/register look —
  thin rule lines between rows, left-aligned labels, right-aligned numbers,
  echoing a monthly ledger book (fits the brand: Corro Cavali, equestrian retail).
- Hero: big Gross Sales number + small monthly line, left-aligned, no gradient.
- Two ledger tables side by side on desktop (Campaigns / Flows), stacked on mobile.
- One line chart for Gross Sales + Active Profiles evolution (dual axis).
- No numbered markers (data isn't a sequence). No all-caps labels except the
  single "AC / BU" tag pulled directly from the source sheet's own convention.

## Principles
- One bold moment: the hero Gross Sales figure in Fraunces + gold.
- Everything else quiet: ledger rows, thin rules, restrained color.
- Every screen must load real seed data (data/data.json) with no placeholder
  lorem ipsum.
