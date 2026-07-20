"""Phase 4 demo: train estimator and produce revenue estimates."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from db.repository import RevWatchRepository
from engine import EstimatorConfig, run_estimation_pipeline
from simulation import GeneratorConfig, SyntheticUniverseGenerator


def _ensure_data(db_path: Path, quick: bool) -> None:
    if db_path.exists():
        repo = RevWatchRepository(db_path)
        n = repo.count_businesses()
        repo.close()
        if n > 0:
            return
    n = 500 if quick else 2000
    print(f"No data found — generating {n} US businesses (Phase 3) …")
    SyntheticUniverseGenerator(
        GeneratorConfig(n_businesses=n, db_path=db_path, seed=42)
    ).run()


def main() -> None:
    parser = argparse.ArgumentParser(description="RevWatch Phase 4 estimation demo")
    parser.add_argument("--db", default="data/revwatch.duckdb")
    parser.add_argument("--quick", action="store_true", help="Use smaller dataset")
    args = parser.parse_args()

    db_path = Path(args.db)
    print("=== Phase 4 Demo: Estimation Engine ===\n")

    _ensure_data(db_path, args.quick)
    repo = RevWatchRepository(db_path)

    t0 = time.perf_counter()
    result = run_estimation_pipeline(
        repo,
        EstimatorConfig(model_version="v0.1.0", labeled_fraction=0.08, seed=42),
    )
    elapsed = time.perf_counter() - t0

    n_biz = repo.count_businesses()
    n_labeled = len(result.labeling.labeled_business_ids)

    print(f"Completed in {elapsed:.1f}s")
    print(f"Businesses in universe:    {n_biz:,}")
    print(f"Labeled for training:      {n_labeled:,} ({100*n_labeled/n_biz:.1f}%)")
    print(f"  (simulates public filings — biased toward large firms)")
    print(f"Training rows:             {result.n_train_rows:,}")
    print(f"Estimates produced:        {result.n_predict_rows:,}")

    # Size tier breakdown of labeled vs population
    print("\n--- Labeling Bias (size tier) ---")
    labeled_str = {str(bid) for bid in result.labeling.labeled_business_ids}
    tiers: dict[str, list[int]] = {}
    for row in repo.conn.execute(
        "SELECT id, size_tier FROM businesses"
    ).fetchall():
        tier = row[1]
        tiers.setdefault(tier, [0, 0])
        tiers[tier][1] += 1
        if row[0] in labeled_str:
            tiers[tier][0] += 1
    for tier in sorted(tiers):
        labeled, total = tiers[tier]
        pct = 100 * labeled / total if total else 0
        print(f"  {tier:12s}: {labeled:3d}/{total:4d} labeled ({pct:.0f}%)")

    # Sample estimates
    print("\n--- Sample Estimates (latest period) ---")
    for row in repo.conn.execute(
        """
        SELECT b.name, b.city, b.category, e.period,
               e.point_estimate, e.ci_low, e.ci_high, e.confidence_score
        FROM revenue_estimates e
        JOIN businesses b ON b.id = e.business_id
        WHERE e.model_version = 'v0.1.0'
        ORDER BY e.point_estimate DESC
        LIMIT 5
        """
    ).fetchall():
        print(
            f"  {row[0][:28]:28s} | ${row[4]:>10,.0f} "
            f"[${row[5]:,.0f}–${row[6]:,.0f}] | conf={row[7]:.0f}"
        )

    # Holdout MAPE (businesses NOT used for training labels)
    labeled_ids = [str(bid) for bid in result.labeling.labeled_business_ids]
    if labeled_ids:
        ph = ",".join("?" * len(labeled_ids))
        holdout_mape = repo.conn.execute(
            f"""
            SELECT AVG(ABS(e.point_estimate - tr.revenue) / NULLIF(tr.revenue, 0)) * 100
            FROM revenue_estimates e
            JOIN true_revenue tr
              ON tr.business_id = e.business_id AND tr.period = e.period
            WHERE e.model_version = 'v0.1.0'
              AND e.business_id NOT IN ({ph})
            """,
            labeled_ids,
        ).fetchone()[0]
        labeled_mape = repo.conn.execute(
            f"""
            SELECT AVG(ABS(e.point_estimate - tr.revenue) / NULLIF(tr.revenue, 0)) * 100
            FROM revenue_estimates e
            JOIN true_revenue tr
              ON tr.business_id = e.business_id AND tr.period = e.period
            WHERE e.model_version = 'v0.1.0'
              AND e.business_id IN ({ph})
            """,
            labeled_ids,
        ).fetchone()[0]
    else:
        holdout_mape = labeled_mape = 0.0

    print("\n--- Accuracy vs Hidden Truth (validation preview) ---")
    print(f"  Holdout MAPE (unlabeled businesses): {holdout_mape:.1f}%")
    print(f"  Training MAPE (labeled businesses):    {labeled_mape:.1f}%")
    print("  ⚠ true_revenue used here for demo validation only")

    # Confidence distribution
    conf = repo.conn.execute(
        """
        SELECT MIN(confidence_score), AVG(confidence_score), MAX(confidence_score)
        FROM revenue_estimates WHERE model_version = 'v0.1.0'
        """
    ).fetchone()
    print(f"\n--- Confidence Distribution ---")
    print(f"  Min: {conf[0]:.0f} | Avg: {conf[1]:.1f} | Max: {conf[2]:.0f}")

    print("\nPhase 4 complete ✓")
    repo.close()


if __name__ == "__main__":
    main()
