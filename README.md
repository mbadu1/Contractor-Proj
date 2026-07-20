# RevWatch

**RevWatch** is a system that tries to figure out how much money businesses are making without asking them directly.

Instead of waiting for companies to report their revenue (which most small businesses never do), we look at *clues* left behind in the real world: payment activity, online reviews, job postings, website traffic, supplier shipments, and things like that. We combine those clues with statistics and machine learning to produce a revenue estimate  and we're honest about how confident we are in each number.

This is the MVP. Right now it runs on **fake but realistic data** for **US businesses only**. The architecture is built so we can swap in real data sources later without rebuilding the core system.

---

## Progress Memo (Phases 1–4)

*Last updated: July 2026*

### Scope note

**Everything is US-focused for now.** All synthetic businesses are in American cities (New York, Chicago, Austin, Miami, etc.). International expansion can come later — the code is structured to support it, but we're not building for other markets yet.

### The short version

We've built the foundation. The system can now:

1. Keep track of US businesses (who they are, where they are, what they do)
2. Pull in "signal" data from multiple sources (stand-ins for real-world clues)
3. Generate a fake universe of ~5,000 US businesses with known hidden revenue, so we can test whether our guesses are any good
4. **Actually estimate revenue** from those clues — with a confidence score and range, not just a single number

We have **not** built the API, dashboard, or autonomous scheduler yet. That's Phases 5–7.

---

### Phase 1 — The basics (done)

Think of this as setting up the filing cabinet.

We defined what a **business** looks like in our system: name, location, category (grocery store, restaurant, etc.), size, and whether they sell online, in person, or both.

We also built a way to **deduplicate businesses**. The same shop might show up in Google Maps and OpenStreetMap under slightly different names. We normalize the names, compare them with fuzzy matching, and merge records that are clearly the same place based on name + location.

Everything gets stored in a lightweight database (DuckDB — basically a single file, no servers to manage).

**In plain terms:** We can ingest messy business records, clean them up, and store them in one place.

---

### Phase 2 — The clue collectors (done)

Real revenue data doesn't exist yet. So we built **signal adapters** — plug-in modules that each represent a different type of clue:

| Adapter | What it stands in for |
|---------|----------------------|
| Digital payments | Card/mobile money transaction volume |
| Reviews | How fast reviews are coming in, ratings |
| Web footprint | Website traffic, product listings, prices |
| Hiring | Job postings (proxy for growth) |
| Supplier flow | Shipment/procurement volume |
| Utility proxy | Opening hours, energy usage intensity |

Each adapter has a simple contract: give it a region and a date range, it returns observations. The estimation engine only ever sees those observations — it doesn't care whether they came from fake data or a real Visa feed.

The fake data is designed to feel real:
- E-commerce businesses show ~95% of revenue in payment signals; cash-heavy informal shops show ~20%
- Some signals are randomly missing (like real-world data gaps)
- Each observation carries a reliability score

**In plain terms:** We built six different "sensor" types that produce believable fake clues about how a business is doing. They're swappable — when real data shows up, we just plug in a new adapter.

---

### Phase 3 — The fake world (done)

To know if our revenue guesses are any good, we need businesses where we *actually know* the answer. Phase 3 generates that.

We created a synthetic universe of **~5,000 US businesses** spread across 20 major metros (NYC, LA, Chicago, Houston, Austin, Miami, Denver, etc.).

For each business, the system generates **24 months of hidden "true" revenue** using realistic statistical distributions (log-normal, parameterized by category and size). The numbers have trend, seasonality, and occasional shocks — like a real business would.

Then we run all six signal adapters against that hidden revenue to produce the clue data the estimation engine will eventually consume.

The true revenue is stored in a separate table (`true_revenue`) that the estimator is **never allowed to read**. It's only for validation — like an answer key kept in a locked drawer.

Quick-run results (500 US businesses):
- 12,000 hidden revenue records
- ~100,000+ signal observations generated
- Payment signals correlate strongly with true revenue — the clues actually relate to the hidden answer
- Cash-heavy informal retailers have sparser payment signals than e-commerce businesses, as intended

**In plain terms:** We built a practice test with known answers, so when we build the revenue estimator we can check its homework.

---

### What's next

| Phase | What it does | Status |
|-------|-------------|--------|
| 4 | Estimation engine — actually guess revenue from signals | Not started |
| 5 | Validation + autonomous scheduled runs | Not started |
| 6 | API (FastAPI) | Not started |
| 7 | Dashboard (Next.js) | Not started |

The end goal is `make demo` — one command that generates data, trains the model, and serves the API + dashboard.

---

## Running what exists today

```bash
# Install dependencies
make install

# Run all tests
make test

# Phase demos
make phase1-demo    # Business dedup + database storage
make phase2-demo    # Signal adapters on sample US businesses
make phase3-quick   # Generate 500-business US universe (~70s)
make phase3-demo    # Full 5,000-business US universe (~10 min)
```

Generated data lands in `data/revwatch.duckdb`.

---

## Project structure (so far)

```
core/           Domain models + entity resolution (dedup)
adapters/       Pluggable signal sources (6 synthetic adapters)
simulation/     Fake US business universe + hidden revenue generator
db/             DuckDB schema + repository layer
scripts/        Phase demo scripts
tests/          Unit tests
```

---

## Tech stack (planned)

- **Python 3.11** — FastAPI, Pydantic, DuckDB, LightGBM, scikit-learn
- **Next.js 14** — Dashboard (not built yet)
- **Docker Compose** — One-command deployment (not built yet)
