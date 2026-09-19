from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models import User, UserRole, DemographicAggregate, Community
from app.analytics.demographics import (
    run_demographic_aggregation, DIMENSIONS, DEFAULT_EPSILON, MIN_CELL_COUNT,
)

router = APIRouter(prefix="/demographics", tags=["demographics"])

require_analyst_or_above = require_role(UserRole.ADMIN, UserRole.ANALYST, UserRole.INVESTIGATOR)


@router.post("/compute")
def compute_demographics(
    epsilon: float = Query(DEFAULT_EPSILON, gt=0.0, le=10.0),
    min_cell_count: int = Query(MIN_CELL_COUNT, ge=1, le=1000),
    db: Session = Depends(get_db),
    _user: User = Depends(require_analyst_or_above),
):
    """Runs all three dimensions (language/region/age_bracket), applying
    k-anonymity suppression then Laplace-mechanism noise before persisting
    — see app/analytics/demographics.py for the full privacy design.
    `min_cell_count` below the default of 5 weakens the suppression floor
    — only lower it if you understand that trade-off."""
    return run_demographic_aggregation(db, epsilon, min_cell_count)


@router.get("")
def list_demographics(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Latest persisted aggregate-only results per dimension. Every row is
    a (community, value) percentage — never anything tied to one user."""
    aggregates: dict[str, list[dict]] = {}
    any_data = False

    for dimension in DIMENSIONS:
        latest_ts = (
            db.query(func.max(DemographicAggregate.computed_at))
            .filter(DemographicAggregate.dimension == dimension)
            .scalar()
        )
        if not latest_ts:
            aggregates[dimension] = []
            continue

        rows = (
            db.query(DemographicAggregate, Community)
            .join(Community, DemographicAggregate.community_id == Community.id)
            .filter(DemographicAggregate.dimension == dimension, DemographicAggregate.computed_at == latest_ts)
            .all()
        )
        aggregates[dimension] = [
            {"community_label": community.label, "value": agg.value, "pct": agg.pct}
            for agg, community in rows
        ]
        any_data = any_data or bool(rows)

    return {"mode": "computed" if any_data else "static_sample", "aggregates": aggregates}
