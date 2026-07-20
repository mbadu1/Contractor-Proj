"""DuckDB repository layer for RevWatch."""

from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID

import duckdb

from core.models import (
    Business,
    BusinessCategory,
    RevenueEstimate,
    SalesChannel,
    SignalObservation,
    SignalType,
    SizeTier,
    TrueRevenue,
    ValidationReport,
)
from db.schema import ALL_DDL


class _MaterializedResult:
    """Snapshot of query rows so fetch happens under the same lock as execute."""

    def __init__(self, rows: list[tuple]) -> None:
        self._rows = rows
        self._idx = 0

    def fetchone(self) -> tuple | None:
        if self._idx >= len(self._rows):
            return None
        row = self._rows[self._idx]
        self._idx += 1
        return row

    def fetchall(self) -> list[tuple]:
        rows = self._rows[self._idx :]
        self._idx = len(self._rows)
        return rows


class _ThreadSafeConnection:
    """
    Serialize DuckDB access.

    DuckDB connections are not safe for concurrent use. FastAPI runs sync
    endpoints in a threadpool, so parallel dashboard requests must lock.
    """

    def __init__(self, conn: duckdb.DuckDBPyConnection, lock: threading.RLock) -> None:
        self._conn = conn
        self._lock = lock

    def execute(self, query: str, params: Any = None) -> _MaterializedResult:
        with self._lock:
            if params is None:
                rel = self._conn.execute(query)
            else:
                rel = self._conn.execute(query, params)
            return _MaterializedResult(rel.fetchall())

    def executemany(self, query: str, params: Any) -> None:
        with self._lock:
            self._conn.executemany(query, params)

    def commit(self) -> None:
        with self._lock:
            self._conn.commit()

    def rollback(self) -> None:
        with self._lock:
            self._conn.rollback()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class RevWatchRepository:
    """Analytical storage backed by a single DuckDB file."""

    def __init__(self, db_path: str | Path = "data/revwatch.duckdb") -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: _ThreadSafeConnection | None = None
        self._lock = threading.RLock()

    @property
    def conn(self) -> _ThreadSafeConnection:
        if self._conn is None:
            raw = duckdb.connect(str(self.db_path))
            self._conn = _ThreadSafeConnection(raw, self._lock)
            self.initialize()
        return self._conn

    def initialize(self) -> None:
        """Create tables and indexes if they do not exist."""
        self.conn.execute(ALL_DDL)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @contextmanager
    def session(self) -> Iterator["RevWatchRepository"]:
        try:
            yield self
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    # ------------------------------------------------------------------
    # Businesses
    # ------------------------------------------------------------------

    def upsert_business(self, business: Business) -> None:
        channels = [c.value for c in business.channels]
        self.conn.execute(
            """
            INSERT INTO businesses (
                id, name, category, country, city,
                latitude, longitude, size_tier, channels
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (id) DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                country = excluded.country,
                city = excluded.city,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                size_tier = excluded.size_tier,
                channels = excluded.channels,
                updated_at = now()
            """,
            [
                str(business.id),
                business.name,
                business.category.value,
                business.country,
                business.city,
                business.latitude,
                business.longitude,
                business.size_tier.value,
                channels,
            ],
        )

    def upsert_businesses(self, businesses: list[Business]) -> int:
        for b in businesses:
            self.upsert_business(b)
        return len(businesses)

    def get_business(self, business_id: UUID) -> Business | None:
        row = self.conn.execute(
            "SELECT * FROM businesses WHERE id = ?", [str(business_id)]
        ).fetchone()
        if row is None:
            return None
        return self._row_to_business(row)

    def list_businesses(
        self,
        *,
        country: str | None = None,
        city: str | None = None,
        category: BusinessCategory | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Business]:
        clauses: list[str] = []
        params: list[object] = []
        if country:
            clauses.append("country = ?")
            params.append(country.upper())
        if city:
            clauses.append("LOWER(city) = LOWER(?)")
            params.append(city)
        if category:
            clauses.append("category = ?")
            params.append(category.value)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.extend([limit, offset])
        rows = self.conn.execute(
            f"""
            SELECT * FROM businesses
            {where}
            ORDER BY name
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
        return [self._row_to_business(r) for r in rows]

    def count_businesses(self, **filters: object) -> int:
        country = filters.get("country")
        row = self.conn.execute(
            "SELECT COUNT(*) FROM businesses"
            + (" WHERE country = ?" if country else ""),
            [country.upper()] if country else [],
        ).fetchone()
        return int(row[0]) if row else 0

    # ------------------------------------------------------------------
    # Source mappings (entity resolution)
    # ------------------------------------------------------------------

    def upsert_source_mapping(
        self, source: str, source_id: str, business_id: UUID
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO source_mappings (source, source_id, business_id)
            VALUES (?, ?, ?)
            ON CONFLICT (source, source_id) DO UPDATE SET
                business_id = excluded.business_id
            """,
            [source, source_id, str(business_id)],
        )

    def upsert_source_mappings(
        self, mapping: dict[tuple[str, str], UUID]
    ) -> int:
        for (source, source_id), bid in mapping.items():
            self.upsert_source_mapping(source, source_id, bid)
        return len(mapping)

    def resolve_business_id(self, source: str, source_id: str) -> UUID | None:
        row = self.conn.execute(
            "SELECT business_id FROM source_mappings WHERE source = ? AND source_id = ?",
            [source, source_id],
        ).fetchone()
        return UUID(row[0]) if row else None

    # ------------------------------------------------------------------
    # Signal observations
    # ------------------------------------------------------------------

    def insert_signal_observation(self, obs: SignalObservation) -> None:
        self.conn.execute(
            """
            INSERT INTO signal_observations (
                business_id, signal_type, value, timestamp, source, reliability
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                str(obs.business_id),
                obs.signal_type.value,
                obs.value,
                obs.timestamp,
                obs.source,
                obs.reliability,
            ],
        )

    def insert_signal_observations(self, observations: list[SignalObservation]) -> int:
        if not observations:
            return 0
        self.conn.executemany(
            """
            INSERT INTO signal_observations (
                business_id, signal_type, value, timestamp, source, reliability
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(o.business_id),
                    o.signal_type.value,
                    o.value,
                    o.timestamp,
                    o.source,
                    o.reliability,
                )
                for o in observations
            ],
        )
        return len(observations)

    def get_signals_for_business(
        self,
        business_id: UUID,
        *,
        since: datetime | None = None,
        signal_type: SignalType | None = None,
    ) -> list[SignalObservation]:
        clauses = ["business_id = ?"]
        params: list[object] = [str(business_id)]
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        if signal_type:
            clauses.append("signal_type = ?")
            params.append(signal_type.value)

        rows = self.conn.execute(
            f"""
            SELECT business_id, signal_type, value, timestamp, source, reliability
            FROM signal_observations
            WHERE {' AND '.join(clauses)}
            ORDER BY timestamp
            """,
            params,
        ).fetchall()
        return [self._row_to_signal(r) for r in rows]

    # ------------------------------------------------------------------
    # Revenue estimates
    # ------------------------------------------------------------------

    def upsert_revenue_estimate(self, estimate: RevenueEstimate) -> None:
        self.conn.execute(
            """
            INSERT INTO revenue_estimates (
                business_id, period, point_estimate, ci_low, ci_high,
                confidence_score, signal_contributions, model_version
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (business_id, period, model_version) DO UPDATE SET
                point_estimate = excluded.point_estimate,
                ci_low = excluded.ci_low,
                ci_high = excluded.ci_high,
                confidence_score = excluded.confidence_score,
                signal_contributions = excluded.signal_contributions,
                created_at = now()
            """,
            [
                str(estimate.business_id),
                estimate.period,
                estimate.point_estimate,
                estimate.ci_low,
                estimate.ci_high,
                estimate.confidence_score,
                json.dumps(estimate.signal_contributions),
                estimate.model_version,
            ],
        )

    def upsert_revenue_estimates(self, estimates: list[RevenueEstimate]) -> int:
        for e in estimates:
            self.upsert_revenue_estimate(e)
        return len(estimates)

    def get_latest_estimate(
        self, business_id: UUID, model_version: str | None = None
    ) -> RevenueEstimate | None:
        if model_version:
            row = self.conn.execute(
                """
                SELECT business_id, period, point_estimate, ci_low, ci_high,
                       confidence_score, signal_contributions, model_version
                FROM revenue_estimates
                WHERE business_id = ? AND model_version = ?
                ORDER BY period DESC
                LIMIT 1
                """,
                [str(business_id), model_version],
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT business_id, period, point_estimate, ci_low, ci_high,
                       confidence_score, signal_contributions, model_version
                FROM revenue_estimates
                WHERE business_id = ?
                ORDER BY period DESC, created_at DESC
                LIMIT 1
                """,
                [str(business_id)],
            ).fetchone()
        return self._row_to_estimate(row) if row else None

    def get_estimate_history(
        self,
        business_id: UUID,
        *,
        model_version: str | None = None,
        limit: int = 24,
    ) -> list[RevenueEstimate]:
        params: list[object] = [str(business_id)]
        version_clause = ""
        if model_version:
            version_clause = "AND model_version = ?"
            params.append(model_version)
        params.append(limit)

        rows = self.conn.execute(
            f"""
            SELECT business_id, period, point_estimate, ci_low, ci_high,
                   confidence_score, signal_contributions, model_version
            FROM revenue_estimates
            WHERE business_id = ? {version_clause}
            ORDER BY period DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [self._row_to_estimate(r) for r in rows]

    # ------------------------------------------------------------------
    # True revenue (validation only — never used by estimation engine)
    # ------------------------------------------------------------------

    def insert_true_revenue(self, record: TrueRevenue) -> None:
        self.conn.execute(
            """
            INSERT INTO true_revenue (
                business_id, period, revenue, trend_factor, seasonal_factor, shock_factor
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (business_id, period) DO UPDATE SET
                revenue = excluded.revenue,
                trend_factor = excluded.trend_factor,
                seasonal_factor = excluded.seasonal_factor,
                shock_factor = excluded.shock_factor
            """,
            [
                str(record.business_id),
                record.period,
                record.revenue,
                record.trend_factor,
                record.seasonal_factor,
                record.shock_factor,
            ],
        )

    def insert_true_revenue_batch(self, records: list[TrueRevenue]) -> int:
        if not records:
            return 0
        self.conn.executemany(
            """
            INSERT INTO true_revenue (
                business_id, period, revenue, trend_factor, seasonal_factor, shock_factor
            ) VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT (business_id, period) DO UPDATE SET
                revenue = excluded.revenue,
                trend_factor = excluded.trend_factor,
                seasonal_factor = excluded.seasonal_factor,
                shock_factor = excluded.shock_factor
            """,
            [
                (
                    str(r.business_id),
                    r.period,
                    r.revenue,
                    r.trend_factor,
                    r.seasonal_factor,
                    r.shock_factor,
                )
                for r in records
            ],
        )
        return len(records)

    def get_true_revenue(
        self,
        business_id: UUID,
        *,
        limit: int = 24,
    ) -> list[TrueRevenue]:
        rows = self.conn.execute(
            """
            SELECT business_id, period, revenue, trend_factor, seasonal_factor, shock_factor
            FROM true_revenue
            WHERE business_id = ?
            ORDER BY period DESC
            LIMIT ?
            """,
            [str(business_id), limit],
        ).fetchall()
        return [self._row_to_true_revenue(r) for r in rows]

    def count_true_revenue(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM true_revenue").fetchone()
        return int(row[0]) if row else 0

    # ------------------------------------------------------------------
    # Validation reports / model registry / pipeline runs
    # ------------------------------------------------------------------

    def insert_validation_report(self, report: ValidationReport) -> None:
        self.conn.execute(
            """
            INSERT INTO validation_reports (
                model_version, n_observations, mape, median_ape,
                interval_coverage, mean_confidence, segment_metrics,
                calibration, promoted, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                report.model_version,
                report.n_observations,
                report.mape,
                report.median_ape,
                report.interval_coverage,
                report.mean_confidence,
                json.dumps([s.model_dump() for s in report.segment_metrics]),
                json.dumps([c.model_dump() for c in report.calibration]),
                report.promoted,
                report.notes,
            ],
        )

    def get_latest_validation_report(
        self, model_version: str | None = None
    ) -> ValidationReport | None:
        if model_version:
            row = self.conn.execute(
                """
                SELECT model_version, n_observations, mape, median_ape,
                       interval_coverage, mean_confidence, segment_metrics,
                       calibration, promoted, notes
                FROM validation_reports
                WHERE model_version = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [model_version],
            ).fetchone()
        else:
            row = self.conn.execute(
                """
                SELECT model_version, n_observations, mape, median_ape,
                       interval_coverage, mean_confidence, segment_metrics,
                       calibration, promoted, notes
                FROM validation_reports
                ORDER BY created_at DESC
                LIMIT 1
                """
            ).fetchone()
        return self._row_to_validation_report(row) if row else None

    def get_promoted_model_mape(self) -> float | None:
        row = self.conn.execute(
            """
            SELECT mape FROM model_registry
            WHERE status = 'promoted'
            ORDER BY promoted_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """
        ).fetchone()
        return float(row[0]) if row and row[0] is not None else None

    def get_promoted_model_version(self) -> str | None:
        row = self.conn.execute(
            """
            SELECT model_version FROM model_registry
            WHERE status = 'promoted'
            ORDER BY promoted_at DESC NULLS LAST, created_at DESC
            LIMIT 1
            """
        ).fetchone()
        return str(row[0]) if row else None

    def register_model(
        self,
        model_version: str,
        *,
        status: str,
        mape: float | None = None,
        notes: str = "",
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO model_registry (model_version, status, mape, notes, promoted_at)
            VALUES (?, ?, ?, ?, CASE WHEN ? = 'promoted' THEN now() ELSE NULL END)
            ON CONFLICT (model_version) DO UPDATE SET
                status = excluded.status,
                mape = excluded.mape,
                notes = excluded.notes,
                promoted_at = CASE
                    WHEN excluded.status = 'promoted' THEN now()
                    ELSE model_registry.promoted_at
                END
            """,
            [model_version, status, mape, notes, status],
        )

    def demote_other_models(self, keep_version: str) -> None:
        self.conn.execute(
            """
            UPDATE model_registry
            SET status = 'retired'
            WHERE model_version != ? AND status = 'promoted'
            """,
            [keep_version],
        )

    def log_pipeline_run(
        self,
        job_name: str,
        status: str,
        started_at: datetime,
        finished_at: datetime | None = None,
        details: dict | None = None,
        error_message: str | None = None,
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO pipeline_runs (
                job_name, status, started_at, finished_at, details, error_message
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                job_name,
                status,
                started_at,
                finished_at,
                json.dumps(details or {}),
                error_message,
            ],
        )

    def list_pipeline_runs(self, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT job_name, status, started_at, finished_at, details, error_message
            FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT ?
            """,
            [limit],
        ).fetchall()
        out = []
        for r in rows:
            details = r[4]
            if isinstance(details, str):
                details = json.loads(details)
            out.append(
                {
                    "job_name": r[0],
                    "status": r[1],
                    "started_at": r[2],
                    "finished_at": r[3],
                    "details": details,
                    "error_message": r[5],
                }
            )
        return out

    # ------------------------------------------------------------------
    # Row mappers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_business(row: tuple) -> Business:
        # Column order from SELECT *: id, name, category, country, city,
        # latitude, longitude, size_tier, channels, created_at, updated_at
        channels_raw = row[8]
        if isinstance(channels_raw, str):
            channels_raw = json.loads(channels_raw)
        return Business(
            id=UUID(row[0]),
            name=row[1],
            category=BusinessCategory(row[2]),
            country=row[3],
            city=row[4],
            latitude=row[5],
            longitude=row[6],
            size_tier=SizeTier(row[7]),
            channels=[SalesChannel(c) for c in channels_raw],
        )

    @staticmethod
    def _row_to_signal(row: tuple) -> SignalObservation:
        return SignalObservation(
            business_id=UUID(row[0]),
            signal_type=SignalType(row[1]),
            value=row[2],
            timestamp=row[3],
            source=row[4],
            reliability=row[5],
        )

    @staticmethod
    def _row_to_validation_report(row: tuple) -> ValidationReport:
        from core.models import CalibrationBin, SegmentMetrics

        segments_raw = row[6]
        calibration_raw = row[7]
        if isinstance(segments_raw, str):
            segments_raw = json.loads(segments_raw)
        if isinstance(calibration_raw, str):
            calibration_raw = json.loads(calibration_raw)
        return ValidationReport(
            model_version=row[0],
            n_observations=int(row[1]),
            mape=float(row[2]),
            median_ape=float(row[3]),
            interval_coverage=float(row[4]),
            mean_confidence=float(row[5]),
            segment_metrics=[SegmentMetrics(**s) for s in segments_raw],
            calibration=[CalibrationBin(**c) for c in calibration_raw],
            promoted=bool(row[8]),
            notes=row[9] or "",
        )

    @staticmethod
    def _row_to_true_revenue(row: tuple) -> TrueRevenue:
        return TrueRevenue(
            business_id=UUID(row[0]),
            period=row[1],
            revenue=row[2],
            trend_factor=row[3],
            seasonal_factor=row[4],
            shock_factor=row[5],
        )

    @staticmethod
    def _row_to_estimate(row: tuple) -> RevenueEstimate:
        contributions = row[6]
        if isinstance(contributions, str):
            contributions = json.loads(contributions)
        return RevenueEstimate(
            business_id=UUID(row[0]),
            period=row[1],
            point_estimate=row[2],
            ci_low=row[3],
            ci_high=row[4],
            confidence_score=row[5],
            signal_contributions=contributions,
            model_version=row[7],
        )


def get_repository(db_path: str | Path = "data/revwatch.duckdb") -> RevWatchRepository:
    """Factory for a initialized repository."""
    repo = RevWatchRepository(db_path)
    repo.initialize()
    return repo
