"""API integration tests against the local DuckDB (if present)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

DB = Path("data/revwatch.duckdb")


@pytest.fixture(scope="module")
def client():
    if not DB.exists():
        pytest.skip("data/revwatch.duckdb missing — run phase5-demo first")
    os.environ["REVWATCH_DB"] = str(DB)
    # Clear API key for open mode
    os.environ.pop("REVWATCH_API_KEY", None)

    from api.main import app

    with TestClient(app) as c:
        yield c


class TestHealthAndDocs:
    def test_health(self, client: TestClient) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["businesses"] > 0

    def test_openapi(self, client: TestClient) -> None:
        r = client.get("/openapi.json")
        assert r.status_code == 200
        assert "RevWatch" in r.json()["info"]["title"]


class TestBusinesses:
    def test_list_paginated(self, client: TestClient) -> None:
        r = client.get("/businesses", params={"limit": 5, "offset": 0})
        assert r.status_code == 200
        body = r.json()
        assert "data" in body and "meta" in body
        assert body["meta"]["limit"] == 5
        assert len(body["data"]) <= 5
        if body["data"]:
            est = body["data"][0].get("latest_estimate")
            if est:
                assert "ci_low" in est and "confidence_score" in est

    def test_filter_confidence(self, client: TestClient) -> None:
        r = client.get("/businesses", params={"confidence_min": 50, "limit": 10})
        assert r.status_code == 200
        for item in r.json()["data"]:
            if item["latest_estimate"]:
                assert item["latest_estimate"]["confidence_score"] >= 50

    def test_estimate_detail(self, client: TestClient) -> None:
        listing = client.get("/businesses", params={"limit": 1}).json()
        assert listing["data"]
        biz_id = listing["data"][0]["id"]
        r = client.get(f"/businesses/{biz_id}/estimate")
        assert r.status_code == 200
        body = r.json()
        assert body["business"]["id"] == biz_id
        assert "history" in body
        if body["current"]:
            assert body["current"]["ci_high"] >= body["current"]["ci_low"]


class TestMarketsRankingsValidation:
    def test_market_summary_us(self, client: TestClient) -> None:
        r = client.get("/markets/US/summary")
        assert r.status_code == 200
        body = r.json()
        assert body["country"] == "US"
        assert body["hhi"] >= 0
        assert body["revenue_by_category"]
        assert body["commercial_density_by_city"]

    def test_rankings(self, client: TestClient) -> None:
        r = client.get("/rankings", params={"limit": 5})
        assert r.status_code == 200
        body = r.json()
        assert "top_categories_by_revenue" in body
        assert "growth_leaders" in body

    def test_validation_latest(self, client: TestClient) -> None:
        r = client.get("/validation/latest")
        assert r.status_code == 200
        body = r.json()
        assert "mape" in body
        assert "calibration" in body


class TestSignalIngest:
    def test_ingest_known_business(self, client: TestClient) -> None:
        listing = client.get("/businesses", params={"limit": 1}).json()
        biz_id = listing["data"][0]["id"]
        r = client.post(
            "/signals/ingest",
            json={
                "observations": [
                    {
                        "business_id": biz_id,
                        "signal_type": "payment_volume",
                        "value": 12345.0,
                        "timestamp": "2025-12-01T00:00:00Z",
                        "source": "api_test",
                        "reliability": 0.8,
                    }
                ]
            },
        )
        assert r.status_code == 200
        assert r.json()["inserted"] == 1

    def test_ingest_unknown_business_fails(self, client: TestClient) -> None:
        r = client.post(
            "/signals/ingest",
            json={
                "observations": [
                    {
                        "business_id": "00000000-0000-0000-0000-000000000001",
                        "signal_type": "payment_volume",
                        "value": 1.0,
                        "timestamp": "2025-12-01T00:00:00Z",
                        "source": "api_test",
                        "reliability": 0.5,
                    }
                ]
            },
        )
        assert r.status_code == 400
