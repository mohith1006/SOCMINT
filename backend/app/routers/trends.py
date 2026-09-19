from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models import User, UserRole, Topic
from app.analytics.trends import compute_trends, persist_trends

router = APIRouter(prefix="/trends", tags=["trends"])

require_analyst_or_above = require_role(UserRole.ADMIN, UserRole.ANALYST, UserRole.INVESTIGATOR)


@router.post("/detect")
def detect_trends(
    db: Session = Depends(get_db),
    _user: User = Depends(require_analyst_or_above),
):
    """Runs n-gram extraction + rolling-baseline velocity scoring (Section
    7-D) and upserts results into `topics`. Gated like the other compute-
    heavy analysis triggers."""
    trends = compute_trends(db)
    updated = persist_trends(db, trends)
    return {"topics_updated": updated, "trends": trends}


@router.get("")
def list_trends(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Ranked current + predicted-rising topics, by velocity_score — not
    absolute volume, per Section 7-D."""
    topics = db.query(Topic).order_by(Topic.velocity_score.desc()).limit(50).all()
    mode = "computed" if topics else "static_sample"
    return {
        "mode": mode,
        "topics": [
            {
                "id": t.id,
                "label": t.label,
                "velocity_score": t.velocity_score,
                "first_seen": t.first_seen.isoformat(),
            }
            for t in topics
        ],
    }
