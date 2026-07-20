# RevWatch — User Manual

A practical guide to what RevWatch does, how to run it, and how to read the numbers.

---

## 1. What is this?

**RevWatch** estimates how much money a business is making **without asking the business**.

Most small companies never publish revenue. Instead of waiting for reports, RevWatch looks at **clues** (signals) left in the open world — payment activity, reviews, website footprint, hiring, supplier flow, utilities — then combines them with a statistical model to produce:

- a **point estimate** (best guess)
- a **confidence interval** (low–high range)
- a **confidence score** (0–100: how much we trust this guess)
- **signal contributions** (which clues mattered most)

Right now the MVP runs on **realistic fake US data**. The pipes are built so real data sources can be plugged in later without rewriting the brain.

---

## 2. How it works (the short pipeline)

```
Businesses in the US
        ↓
Signal adapters collect clues (payments, reviews, web, hiring, etc.)
        ↓
Feature builder turns clues into a monthly “profile” per business
        ↓
Model trains on ~8% of businesses with “known” revenue (public-filings analog)
        ↓
Model estimates revenue for everyone else
        ↓
Validation checks guesses against a hidden answer key
        ↓
API + dashboard show results (always with uncertainty)
```

### Important honesty rules

| Rule | Meaning |
|------|---------|
| Never a bare number | Every estimate shows a range **and** a confidence score |
| Answer key is locked | Hidden true revenue is only for grading the model, not for guessing |
| Bias is explicit | Training labels favor larger firms (like real filings); the model reweights to correct for that |
| New models need a hall pass | A new model only goes live if MAPE doesn’t get worse by more than ~5% |

---

## 3. Start the platform

### One command (recommended)

From the project root:

```bash
make demo
```

That will:

1. Use existing data in `data/revwatch.duckdb` (or generate a demo universe if missing)
2. Start the **API** at http://127.0.0.1:8000  
3. Start the **dashboard** at http://127.0.0.1:3000  

Open the dashboard in your browser: **http://127.0.0.1:3000**

API docs (interactive): **http://127.0.0.1:8000/docs**

### Run pieces separately

```bash
make install      # Python + dashboard npm packages
make api          # API only → :8000
make dashboard    # UI only → :3000  (needs API running)
make scheduler    # Optional autonomous loop (ingest / re-estimate / retrain)
```

### First-time data (if the DB is empty)

```bash
make phase3-quick   # fake US businesses + signals
make phase4-demo    # train + produce estimates
make phase5-demo    # validate + promote a model
make demo           # then open the UI
```

---

## 4. Dashboard walkthrough

### Market Overview (`/`)

**Use when:** You want the big picture for the US market.

You’ll see:

- **Business count** and **total estimated revenue** for the latest period
- **HHI** — concentration (lower ≈ more competitive across categories)
- **Map** — cities; bigger circles = more businesses
- **Revenue by category** — which sectors dominate estimated dollars
- **Growth leaders** — biggest month-over-month % jumps

### Business Explorer (`/businesses`)

**Use when:** You’re hunting a specific shop or filtering a slice.

1. Filter by search text, city, category, and/or minimum confidence  
2. Open a row to see the **detail page**

On the detail page:

- **Current estimate** with interval + confidence badge  
- **Time series** — 24 months of guesses with a shaded uncertainty band  
- **Signal contributions** — bar chart of which clue types drove the estimate  

### Comparisons (`/comparisons`)

**Use when:** You want “A vs B” growth, not raw dollar levels.

1. Choose **business** or **category** mode  
2. Pick **2–4** items  
3. Curves are **indexed to 100** at the first month — so you’re comparing *shape of growth*, not size  

### Model Health (`/model-health`)

**Use when:** You need to know if the guesses are trustworthy.

This page is the report card:

- **MAPE** — average % error vs hidden truth (lower is better)  
- **Interval coverage** — how often truth falls inside the low–high range  
- **Calibration** — high-confidence estimates should be more accurate  
- **Segments** — error by size tier and category  

If Model Health looks bad, don’t trust Market Overview blindly.

---

## 5. How to read an estimate (explainability)

Example:

```
$10,762  [$8,305 – $10,762]   conf 71%
```

| Piece | Plain English |
|-------|----------------|
| **$10,762** | Best guess for that month |
| **[$8,305 – $10,762]** | Likely range (model’s low/high quantiles after shrinkage) |
| **conf 71%** | How much evidence we had + how much the clues agreed + how tight the range is |

### Confidence score (0–100)

Rough guide:

| Score | How to treat it |
|------|------------------|
| **70+** | Stronger — more signals, better agreement |
| **50–70** | Usable with caution |
| **Below 50** | Thin evidence — treat as directional only |

Confidence is **not** “probability the number is exact.” It’s a quality score for the estimate.

### Signal contributions

On a business detail page, bars like:

- `payment_volume` 35%  
- `review_velocity` 20%  
- `business_profile` 25%  
- …

mean: “Of the factors the model used, these shares explain the prediction.”  
It’s attribution, not a receipt of real cash.

### Why two similar shops can differ

- Different **signal coverage** (one has payments + reviews; the other is sparse)  
- Different **size / category priors** (shrinkage pulls sparse shops toward category norms)  
- Different **month** (seasonality and shocks)

---

## 6. Using the API (optional)

Interactive docs: http://127.0.0.1:8000/docs  

Common calls:

| Call | Purpose |
|------|---------|
| `GET /health` | Is the API up? Which model is live? |
| `GET /businesses?city=Austin&confidence_min=60` | Filtered list |
| `GET /businesses/{id}/estimate` | History + contributions |
| `GET /markets/US/summary` | Market rollup + HHI + city density |
| `GET /rankings` | Leaders / decliners |
| `GET /validation/latest` | Model health JSON |
| `POST /signals/ingest` | Push new clue rows (for real adapters later) |

**Auth stub:** leave open for local demo. To lock it:

```bash
export REVWATCH_API_KEY=your-secret
# then send header: X-API-Key: your-secret
```

---

## 7. The autopilot (scheduler)

If you run `make scheduler`, RevWatch loops on its own:

| Cadence | Job |
|---------|-----|
| Daily | Pull fresh signals |
| Weekly | Re-estimate with the promoted model |
| Monthly | Retrain a candidate; **promote only if MAPE doesn’t regress >5%** |

You don’t need the scheduler just to browse the dashboard.

---

## 8. What’s real vs demo

| Piece | Status in MVP |
|-------|----------------|
| Businesses, signals, revenue | **Synthetic** (fake but realistic US sample) |
| Estimation engine | **Real logic** (LightGBM quantiles + shrinkage + confidence) |
| Validation | **Real checks** against hidden synthetic truth |
| Dashboard / API | **Real product surface** |
| Live Visa / logistics feeds | **Not connected yet** — adapters are the swap point |

---

## 9. Quick troubleshooting

| Symptom | Try this |
|---------|----------|
| Dashboard: “Could not load data” | Run `make api` and confirm http://127.0.0.1:8000/health |
| Empty / no estimates | `make phase4-demo` then `make phase5-demo` |
| Port already in use | Stop the old process, or change ports in the Makefile / demo script |
| DuckDB lock errors | Only one writer/API process should hold `data/revwatch.duckdb` |

---

## 10. Mental model in one sentence

**RevWatch turns messy public clues into revenue estimates with a range and a trust score — then shows you both the guesses and the report card that proves they were checked.**
