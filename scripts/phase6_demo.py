"""Phase 6 demo: smoke-test the FastAPI endpoints."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient


def main() -> None:
    db = Path("data/revwatch.duckdb")
    if not db.exists():
        print("ERROR: data/revwatch.duckdb not found. Run: make phase5-demo")
        raise SystemExit(1)

    os.environ["REVWATCH_DB"] = str(db)
    os.environ.pop("REVWATCH_API_KEY", None)

    from api.main import app

    print("=== Phase 6 Demo: RevWatch API ===\n")

    with TestClient(app) as client:
        health = client.get("/health").json()
        print(f"Health: {health['status']} | businesses={health['businesses']:,} | model={health['promoted_model']}")

        biz = client.get("/businesses", params={"limit": 3, "confidence_min": 40}).json()
        print(f"\nGET /businesses → {biz['meta']['total']:,} total, showing {len(biz['data'])}")
        for item in biz["data"]:
            est = item["latest_estimate"]
            if est:
                print(
                    f"  {item['name'][:30]:30s} | ${est['point_estimate']:>10,.0f} "
                    f"[${est['ci_low']:,.0f}–${est['ci_high']:,.0f}] conf={est['confidence_score']:.0f}"
                )
            else:
                print(f"  {item['name'][:30]:30s} | (no estimate)")

        if biz["data"]:
            bid = biz["data"][0]["id"]
            detail = client.get(f"/businesses/{bid}/estimate").json()
            print(f"\nGET /businesses/{{id}}/estimate → {len(detail['history'])} months history")
            if detail["current"]:
                top_contrib = sorted(
                    detail["current"]["signal_contributions"].items(),
                    key=lambda x: -x[1],
                )[:3]
                print(f"  Top contributions: {top_contrib}")

        market = client.get("/markets/US/summary").json()
        print(f"\nGET /markets/US/summary → period={market['period']} HHI={market['hhi']:.0f}")
        print(f"  Total estimated revenue: ${market['total_estimated_revenue']:,.0f}")
        print("  Top categories:")
        for c in market["revenue_by_category"][:5]:
            print(f"    {c['category']:30s} ${c['total_revenue']:>12,.0f} ({c['share']*100:.1f}%)")

        ranks = client.get("/rankings", params={"limit": 3}).json()
        print(f"\nGET /rankings → growth leaders (MoM %):")
        for g in ranks["growth_leaders"][:3]:
            print(f"    {g['label'][:30]:30s} {g['value']:+.1f}%")

        val = client.get("/validation/latest").json()
        print(f"\nGET /validation/latest → MAPE={val['mape']:.1f}% coverage={val['interval_coverage']:.1f}%")

        print("\nOpenAPI docs: http://127.0.0.1:8000/docs")
        print("Serve with:   make api")
        print("\nPhase 6 complete ✓")


if __name__ == "__main__":
    main()
