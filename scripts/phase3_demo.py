"""Phase 3 demo: synthetic ground truth universe generation."""

from __future__ import annotations

import argparse
import time
from collections import Counter, defaultdict
from pathlib import Path

from core.models import SignalType
from db.repository import RevenueLensRepository
from simulation import GeneratorConfig, SyntheticUniverseGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description="RevenueLens Phase 3 generator demo")
    parser.add_argument("--businesses", type=int, default=5000, help="Number of businesses")
    parser.add_argument("--quick", action="store_true", help="Quick run with 500 businesses")
    parser.add_argument(
        "--db", type=str, default="data/revenuelens.duckdb", help="DuckDB output path"
    )
    args = parser.parse_args()

    n = 500 if args.quick else args.businesses
    db_path = Path(args.db)

    print("=== Phase 3 Demo: Synthetic Ground Truth Generator (US) ===\n")
    print(f"Generating {n:,} businesses × 24 months …")

    config = GeneratorConfig(n_businesses=n, db_path=db_path, seed=42)
    gen = SyntheticUniverseGenerator(config)

    t0 = time.perf_counter()
    result = gen.run()
    elapsed = time.perf_counter() - t0

    repo = RevenueLensRepository(db_path)

    # Business distribution
    by_city = repo.conn.execute(
        "SELECT city, COUNT(*) FROM businesses GROUP BY city ORDER BY 2 DESC LIMIT 8"
    ).fetchall()
    by_category = repo.conn.execute(
        "SELECT category, COUNT(*) FROM businesses GROUP BY category ORDER BY 2 DESC LIMIT 8"
    ).fetchall()

    print(f"\nCompleted in {elapsed:.1f}s")
    print(f"Database:                  {db_path}")
    print(f"Businesses:                  {len(result.businesses):,}")
    print(f"True revenue records:      {repo.count_true_revenue():,}")
    print(f"Signal observations:       {result.signal_count:,}")

    print("\n--- US Businesses (all markets) ---")
    print(f"  US: {len(result.businesses):,} (100%)")

    print("\n--- Top US Cities ---")
    for city, cnt in by_city:
        pct = 100 * cnt / len(result.businesses)
        print(f"  {city}: {cnt:,} ({pct:.1f}%)")

    print("\n--- Top Categories ---")
    for cat, cnt in by_category:
        print(f"  {cat}: {cnt:,}")

    # True revenue stats
    rev_stats = repo.conn.execute(
        """
        SELECT
            MIN(revenue), AVG(revenue), MAX(revenue),
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY revenue)
        FROM true_revenue
        """
    ).fetchone()
    print("\n--- True Revenue Distribution (monthly, hidden) ---")
    print(f"  Min:    ${rev_stats[0]:,.0f}")
    print(f"  Median: ${rev_stats[3]:,.0f}")
    print(f"  Mean:   ${rev_stats[1]:,.0f}")
    print(f"  Max:    ${rev_stats[2]:,.0f}")

    print("\n--- Median True Revenue by City (top metros) ---")
    for row in repo.conn.execute(
        """
        SELECT b.city, PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY tr.revenue)
        FROM true_revenue tr
        JOIN businesses b ON b.id = tr.business_id
        GROUP BY b.city
        ORDER BY 2 DESC
        LIMIT 6
        """
    ).fetchall():
        print(f"  {row[0]}: ${row[1]:,.0f}/mo")

    print("\n--- Signal Coverage (US overall) ---")
    row = repo.conn.execute(
        """
        SELECT COUNT(DISTINCT s.business_id), COUNT(*), AVG(s.reliability)
        FROM signal_observations s
        """
    ).fetchone()
    cov = 100 * row[0] / len(result.businesses)
    print(f"  {row[0]:,}/{len(result.businesses):,} businesses ({cov:.0f}%) | {row[1]:,} obs | rel={row[2]:.3f}")

    print("\n--- Payment Signal Sparsity (informal vs ecommerce) ---")
    for category in ("informal_retail", "ecommerce_pure_play"):
        row = repo.conn.execute(
            """
            SELECT
                COUNT(DISTINCT CASE WHEN s.signal_type = 'payment_volume' THEN s.business_id END),
                COUNT(DISTINCT b.id)
            FROM businesses b
            LEFT JOIN signal_observations s ON s.business_id = b.id
            WHERE b.category = ?
            """,
            [category],
        ).fetchone()
        pct = 100 * row[0] / row[1] if row[1] else 0
        print(f"  {category}: {row[0]:,}/{row[1]:,} with payment_volume ({pct:.0f}%)")

    # Revenue-signal correlation sample
    print("\n--- Revenue ↔ Payment Volume Correlation (sample) ---")
    corr_row = repo.conn.execute(
        """
        WITH joined AS (
            SELECT tr.revenue, s.value AS payment_vol
            FROM true_revenue tr
            JOIN signal_observations s
              ON s.business_id = tr.business_id
             AND strftime(s.timestamp, '%Y-%m') = tr.period
            WHERE s.signal_type = 'payment_volume'
              AND tr.period = '2025-12'
        )
        SELECT CORR(revenue, payment_vol) FROM joined
        """
    ).fetchone()
    corr = corr_row[0] if corr_row and corr_row[0] is not None else 0.0
    print(f"  Pearson r (Dec 2025): {corr:.3f}")

    # Shocks
    shocks = repo.conn.execute(
        "SELECT COUNT(*) FROM true_revenue WHERE shock_factor != 1.0"
    ).fetchone()[0]
    print(f"\n--- Revenue Shocks ---")
    print(f"  Business-months with shocks: {shocks:,} ({100*shocks/repo.count_true_revenue():.1f}%)")

    print("\n  ⚠ true_revenue table is validation-only — estimator never reads it")
    print("\nPhase 3 complete ✓")
    repo.close()


if __name__ == "__main__":
    main()
