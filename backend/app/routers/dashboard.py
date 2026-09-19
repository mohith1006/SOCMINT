"""
Section 10: "Dashboard — summary counters (users, posts, active trends,
ledger status)". Was previously an undocumented gap -- the frontend page
existed as a placeholder but nothing backed it.

active_trends is defined as topics with velocity_score > 0 -- the same
"growing, not just present" definition already used by
app/analytics/trends.py's ranking (velocity_score is a rate-of-change
measure per that module: positive means today's mention frequency
exceeds the rolling baseline, negative/zero means flat or declining).
Reusing that definition here rather than inventing a separate threshold
keeps "active trend" meaning the same thing on the Dashboard as it does
on the Trends page.

Deliberately gives every authenticated role a coarse view (this is
aggregate counts, not the underlying data), then a bit more detail for
Admins (pending-approval count) since that's a number only they can act on.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.deps import get_current_user
from app.models import User, Post, Topic, UserStatus, UserRole
from app.blockchain.ledger import verify_chain
from app.models import LedgerBlock

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post_count = db.query(func.count(Post.id)).scalar()
    active_trends_count = db.query(func.count(Topic.id)).filter(Topic.velocity_score > 0).scalar()
    ledger_status = verify_chain(db)
    ledger_block_count = db.query(func.count(LedgerBlock.index)).scalar()

    # is_synthetic isn't a stored column (see Post model) -- inferred the
    # same way the rest of the app treats synthetic vs. live data, via
    # raw_metadata, matching scripts/generate_synthetic_data.py's own tagging.
    # Using Postgres's ->> operator (extract as text) rather than a typed
    # JSON comparator method -- more predictable across SQLAlchemy/Postgres
    # version combinations than relying on a JSON-boolean cast helper.
    synthetic_post_count = (
        db.query(func.count(Post.id))
        .filter(Post.raw_metadata.op("->>")("synthetic") == "true")
        .scalar()
    )

    summary = {
        "post_count": post_count,
        "synthetic_post_count": synthetic_post_count,
        "live_post_count": post_count - synthetic_post_count,
        "active_trends_count": active_trends_count,
        "ledger": {
            "valid": ledger_status["valid"],
            "brokenAtIndex": ledger_status["brokenAtIndex"],
            "block_count": ledger_block_count,
        },
    }

    if current_user.role == UserRole.ADMIN:
        summary["user_count"] = db.query(func.count(User.id)).scalar()
        summary["pending_approval_count"] = (
            db.query(func.count(User.id)).filter(User.status == UserStatus.PENDING_VERIFICATION).scalar()
        )

    return summary
