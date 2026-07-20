"""Signal ingest endpoint for future real adapters."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from core.models import SignalObservation
from db.repository import RevWatchRepository

from api.auth import require_api_key
from api.deps import get_repo
from api.schemas import SignalIngestRequest, SignalIngestResponse

router = APIRouter(tags=["signals"])


@router.post("/signals/ingest", response_model=SignalIngestResponse)
def ingest_signals(
    body: SignalIngestRequest,
    repo: RevWatchRepository = Depends(get_repo),
    _key: str | None = Depends(require_api_key),
) -> SignalIngestResponse:
    """Ingest signal observations from future real adapters."""
    missing: list[str] = []
    for item in body.observations:
        if repo.get_business(item.business_id) is None:
            missing.append(str(item.business_id))
    if missing:
        unique = sorted(set(missing))[:10]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown business_id(s): {unique}",
        )

    observations = [
        SignalObservation(
            business_id=item.business_id,
            signal_type=item.signal_type,
            value=item.value,
            timestamp=item.timestamp,
            source=item.source,
            reliability=item.reliability,
        )
        for item in body.observations
    ]
    n = repo.insert_signal_observations(observations)
    return SignalIngestResponse(
        inserted=n,
        message=f"Ingested {n} signal observation(s)",
    )
