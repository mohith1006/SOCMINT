from sqlalchemy import cast, Date, func
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_role
from app.models import User, UserRole, Post, SentimentScore, PostTopic, UserCommunityMembership
from app.ml.pipeline import process_unscored_posts

router = APIRouter(tags=["nlp"])

require_analyst_or_above = require_role(UserRole.ADMIN, UserRole.ANALYST, UserRole.INVESTIGATOR)


@router.post("/nlp/process")
def run_nlp_processing(
    limit: int = Query(200, ge=1, le=2000),
    db: Session = Depends(get_db),
    _user: User = Depends(require_analyst_or_above),
):
    """Batch-classifies posts with no sentiment_scores row yet (emotion +
    stance + sarcasm, see app/ml/pipeline.py) and persists results. Gated
    to Analyst/Investigator/Admin since this is compute-heavy."""
    return process_unscored_posts(db, limit=limit)


@router.get("/sentiment/timeline")
def sentiment_timeline(
    topic_id: str | None = Query(None),
    region_tag: str | None = Query(None),
    community_id: str | None = Query(None),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Section 7-B: sentiment/emotion exposed as a time series, filterable
    by community, topic, and India-association (region) tag."""
    query = (
        db.query(
            cast(Post.posted_at, Date).label("date"),
            SentimentScore.emotion_bucket,
            func.count(Post.id).label("count"),
        )
        .join(SentimentScore, SentimentScore.post_id == Post.id)
    )

    if topic_id:
        query = query.join(PostTopic, PostTopic.post_id == Post.id).filter(PostTopic.topic_id == topic_id)
    if region_tag:
        query = query.filter(Post.region_tag == region_tag)
    if community_id:
        query = query.join(
            UserCommunityMembership, UserCommunityMembership.user_handle == Post.author_handle
        ).filter(UserCommunityMembership.community_id == community_id)

    rows = (
        query.filter(Post.posted_at.isnot(None))
        .group_by(cast(Post.posted_at, Date), SentimentScore.emotion_bucket)
        .order_by(cast(Post.posted_at, Date))
        .all()
    )

    mode = "computed" if rows else "static_sample"
    series = [
        {"date": row.date.isoformat(), "emotion_bucket": row.emotion_bucket, "count": row.count}
        for row in rows
    ]
    return {"mode": mode, "series": series}
