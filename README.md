# RevWatch

**RevWatch** is a system that tries to figure out how much money businesses are making without asking them directly.

Instead of waiting for companies to report their revenue (which most small businesses never do), we look at *clues* left behind in the real world: payment activity, online reviews, job postings, website traffic, supplier shipments, and things like that. We combine those clues with statistics and machine learning to produce a revenue estimate, and we're honest about how confident we are in each number.

This is the MVP. Right now it runs on **fake but realistic data** for **US businesses only**. The architecture is built so we can swap in real data sources later without rebuilding the core system.

---

## Progress Memo (Phases 1–6)

*Last updated: July 2026*

### Scope note

**Everything is US-focused for now.** All synthetic businesses are in American cities (New York, Chicago, Austin, Miami, etc.). International expansion can come later — the code is structured to support it, but we're not building for other markets yet.

### The short version

We've built the foundation. The system can now:

1. Keep track of US businesses (who they are, where they are, what they do)
2. Pull in "signal" data from multiple sources (stand-ins for real-world clues)
3. Generate a fake universe of ~5,000 US businesses with known hidden revenue, so we can test whether our guesses are any good
4. **Actually estimate revenue** from those clues — with a confidence score and range, not just a single number
5. **Check its own homework** and **run on a schedule** without someone babysitting it
6. **Serve it over an API** so other apps (and eventually the dashboard) can query estimates

We have **not** built the dashboard yet. That's Phase 7.

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

**In plain terms:** We built a practice test with known answers, so we can check the estimator's homework.

---

### Phase 4 — The revenue guesser (done)

This is the brain. It takes all those clues and produces a revenue estimate for every business, every month.

How it works, in plain English:

1. **Feature builder** — Crunches signals into a spreadsheet-style row per business per month: payment volume, review velocity, how many clue types are missing, growth vs last month, how this business compares to others in the same category, etc.

2. **Training on a lucky few** — In the real world, almost nobody publishes their revenue. We simulate the ~8% of businesses whose revenue is "known" (like public filings). Those are biased toward big companies — we correct for that with reweighting so the model doesn't only learn to predict Walmart-sized businesses.

3. **Machine learning ensemble** — Three LightGBM models predict the 10th, 50th, and 90th percentile of revenue. That gives us a point estimate (the middle) and a range (the low and high bounds).

4. **Shrinkage for sparse clues** — If a business has very few signals, we don't trust the model blindly. We pull the estimate toward a sensible default for that category and size tier.

5. **Confidence score** — Every estimate gets a 0–100 score based on how much data we had, how well the clues agreed with each other, and how wide the uncertainty range is.

6. **Explainability** — Each estimate includes which clue types contributed most (payments, reviews, etc.).

The estimator itself **never peeks at the answer key**. Only the training pipeline touches hidden true revenue, and only for those ~8% labeled businesses.

Quick-run results (500 US businesses):
- 40 businesses used for training (8%, biased toward enterprise)
- 12,000 revenue estimates produced
- Holdout MAPE ~28% on businesses the model wasn't trained on
- Average confidence score ~69/100

**In plain terms:** We can now guess revenue from clues, say how sure we are, and show our work.

---

### Phase 5 — The report card + autopilot (done)

Two big pieces landed here.

**Validation (the report card)**
After we produce estimates, we compare them to the hidden answer key (`true_revenue`) — but only for this check, never during guessing. We measure:

- **MAPE** — how far off our guesses are on average (as a %)
- **Interval coverage** — how often the true revenue falls inside our low–high range
- **Calibration** — whether high-confidence estimates are actually more accurate
- **Segments** — the same metrics broken down by category, size tier, and city

Every model version gets a saved validation report so we can see if a new model is better or worse.

**Autonomous loop (the autopilot)**
A scheduler runs three jobs without anyone clicking buttons:

| Cadence | Job | What it does |
|---------|-----|--------------|
| Daily | Signal ingestion | Pull fresh clues from all adapters |
| Weekly | Re-estimation | Re-run revenue estimates with the current promoted model |
| Monthly | Retrain + gate | Train a new candidate model, validate it, **only promote if MAPE doesn't get worse by more than 5%** |

If the new model is worse than the ceiling, it gets rejected and the old one stays live. All runs are logged.

Quick-run results (500 US businesses):
- Holdout MAPE ~27.6%, median error ~16.7%
- Medium businesses easiest (~12% MAPE); micro hardest (~37%)
- Higher confidence bins → lower MAPE (calibration works in the right direction)
- Candidate `v0.2.demo` promoted: MAPE stayed within the 5% gate

**In plain terms:** The system grades itself, and it only ships a new model if the grade doesn't get meaningfully worse.

---

### Phase 6 — The front door (done)

Other systems (and people) can now ask RevWatch questions over HTTP.

**Endpoints**

| Method | Path | What you get |
|--------|------|--------------|
| GET | `/businesses` | Searchable list — filter by city, category, revenue band, min confidence |
| GET | `/businesses/{id}/estimate` | Current estimate + up to 24 months of history + which clues mattered |
| GET | `/markets/{country}/summary` | Revenue by category, concentration (HHI), commercial density by city |
| GET | `/rankings` | Top categories/cities, growth leaders and decliners |
| GET | `/validation/latest` | Model health (MAPE, coverage, calibration) |
| POST | `/signals/ingest` | Drop in new clue data (for real adapters later) |
| GET | `/health` | Is the API up, how many businesses, which model is live? |
| GET | `/docs` | Interactive OpenAPI docs (Swagger UI) |

Every estimate always includes a **confidence interval** and a **confidence score** — never a bare number.

There's a stub API-key gate (`X-API-Key` / `REVWATCH_API_KEY`). Leave the env var unset for local demo mode; set it when you want to lock things down.

**In plain terms:** You can now query revenue estimates like a normal web API, and browse the docs in a browser.

---

### What's next

| Phase | What it does | Status |
|-------|-------------|--------|
| 4 | Estimation engine — guess revenue from signals | Done |
| 5 | Validation + autonomous scheduled runs | Done |
| 6 | API (FastAPI) | Done |
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
make phase4-demo    # Train estimator + produce estimates (~3 min)
make phase4-full    # Same on full dataset if already generated
make phase5-demo    # Validate + run one autonomous cycle (~3 min)
make phase6-demo    # Smoke-test API endpoints
make api            # Serve API at http://127.0.0.1:8000 (docs at /docs)
make scheduler      # Start long-running APScheduler loop
```

Generated data lands in `data/revwatch.duckdb`.

---

## Project structure (so far)

```
core/             Domain models + entity resolution (dedup)
adapters/         Pluggable signal sources (6 synthetic adapters)
simulation/       Fake US business universe + hidden revenue generator
engine/           Features, confidence, LightGBM estimator, validation
orchestration/    APScheduler jobs (ingest / re-estimate / retrain gate)
api/              FastAPI app (businesses, markets, rankings, validation)
db/               DuckDB schema + repository layer
scripts/          Phase demo scripts
tests/            Unit tests
```

---

## Tech stack (planned)

- **Python 3.11** — FastAPI, Pydantic, DuckDB, LightGBM, scikit-learn
- **Next.js 14** — Dashboard (not built yet)
- **Docker Compose** — One-command deployment (not built yet)
