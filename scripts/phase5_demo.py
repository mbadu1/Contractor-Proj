"""Phase 5 demo: validation + one autonomous cycle."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

from db.repository import RevWatchRepository
from engine import EstimatorConfig, run_estimation_pipeline, run_validation
from engine.validation import ValidationConfig, should_promote
from orchestration import create_scheduler, run_autonomous_cycle_once
from simulation import GeneratorConfig, SyntheticUniverseGenerator


def _ensure_data(db_path: Path, quick: bool) -> None:
    if db_path.exists():
        repo = RevWatchRepository(db_path)
        n = repo.count_businesses()
        repo.close()
        if n > 0:
            return
    n = 500 if quick else 2000
    print(f"No data found — generating {n} US businesses …")
    SyntheticUniverseGenerator(
        GeneratorConfig(n_businesses=n, db_path=db_path, seed=42)
    ).run()


def _ensure_baseline(repo: RevWatchRepository) -> str:
    """Train + validate + promote baseline model if none exists."""
    version = "v0.1.0"
    promoted = repo.get_promoted_model_version()
    if promoted:
        return promoted

    print(f"No promoted model — training baseline {version} …")
    result = run_estimation_pipeline(
        repo, EstimatorConfig(model_version=version, seed=42)
    )
    labeled = {str(b) for b in result.labeling.labeled_business_ids}
    report = run_validation(
        repo, version, ValidationConfig(exclude_business_ids=labeled)
    )
    ok, reason = should_promote(report, previous_mape=None)
    report.promoted = ok
    report.notes = f"{report.notes}; {reason}"
    repo.insert_validation_report(report)
    repo.register_model(version, status="promoted" if ok else "rejected", mape=report.mape, notes=reason)
    print(f"  Baseline MAPE={report.mape:.1f}% coverage={report.interval_coverage:.1f}% — {reason}")
    return version if ok else version


def main() -> None:
    parser = argparse.ArgumentParser(description="RevWatch Phase 5 demo")
    parser.add_argument("--db", default="data/revwatch.duckdb")
    parser.add_argument("--quick", action="store_true")
    args = parser.parse_args()

    db_path = Path(args.db)
    print("=== Phase 5 Demo: Validation + Autonomous Loop ===\n")

    _ensure_data(db_path, args.quick)
    repo = RevWatchRepository(db_path)

    baseline = _ensure_baseline(repo)
    print(f"Promoted model: {baseline}")

    # Show latest validation for baseline
    report = repo.get_latest_validation_report(baseline)
    if report:
        print("\n--- Baseline Model Health ---")
        print(f"  Version:            {report.model_version}")
        print(f"  Observations:       {report.n_observations:,}")
        print(f"  Holdout MAPE:       {report.mape:.1f}%")
        print(f"  Median APE:         {report.median_ape:.1f}%")
        print(f"  Interval coverage:  {report.interval_coverage:.1f}%")
        print(f"  Mean confidence:    {report.mean_confidence:.1f}")

        print("\n--- MAPE by Size Tier ---")
        for seg in report.segment_metrics:
            if seg.segment_type == "size_tier":
                print(
                    f"  {seg.segment_value:12s}: MAPE={seg.mape:5.1f}% "
                    f"coverage={seg.interval_coverage:5.1f}% n={seg.n_observations:,}"
                )

        print("\n--- Calibration (confidence → accuracy) ---")
        for bin_ in report.calibration:
            print(
                f"  conf [{bin_.confidence_bin_low:3.0f}–{bin_.confidence_bin_high:3.0f}): "
                f"n={bin_.n_observations:5d} | avg_conf={bin_.mean_confidence:5.1f} | "
                f"MAPE={bin_.mape:5.1f}% | cov={bin_.interval_coverage:5.1f}%"
            )

    print("\n--- Running one autonomous cycle (ingest → re-estimate → retrain+gate) ---")
    t0 = time.perf_counter()
    cycle = run_autonomous_cycle_once(repo, candidate_version="v0.2.demo")
    elapsed = time.perf_counter() - t0
    print(f"Cycle finished in {elapsed:.1f}s\n")

    print("  Ingestion:", cycle["ingestion"])
    print("  Re-estimation:", {
        k: cycle["reestimation"][k]
        for k in ("model_version", "n_estimates", "n_train_rows")
    })
    rv = cycle["retrain_validate"]
    print(
        f"  Retrain gate: candidate={rv['candidate_version']} "
        f"MAPE={rv['mape']:.1f}% (prev={rv['previous_mape']}) "
        f"promoted={rv['promoted']}"
    )
    print(f"    Reason: {rv['reason']}")

    print("\n--- Pipeline Run Log ---")
    for run in repo.list_pipeline_runs(limit=6):
        print(
            f"  {run['job_name']:28s} {run['status']:8s} "
            f"@ {run['started_at']}"
        )

    print("\n--- Scheduled Jobs (APScheduler, not started) ---")
    scheduler = create_scheduler(db_path)
    for job in scheduler.get_jobs():
        print(f"  {job.id:28s} next={job.trigger}")

    print("\n  Start long-running loop with: make scheduler")
    print("\nPhase 5 complete ✓")
    repo.close()


if __name__ == "__main__":
    main()
