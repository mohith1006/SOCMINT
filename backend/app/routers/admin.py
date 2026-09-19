from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models import User, UserStatus
from app.schemas import AdminDecisionRequest, PendingUserOut
from app.security.aes import decrypt_field
from app.blockchain.ledger import append_block

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/pending-users", response_model=list[PendingUserOut])
def list_pending_users(db: Session = Depends(get_db), _admin=Depends(require_admin)):
    pending = db.query(User).filter(User.status == UserStatus.PENDING_VERIFICATION).all()
    return [
        PendingUserOut(id=u.id, email=u.email, created_at=u.created_at.isoformat())
        for u in pending
    ]


@router.get("/pending-users/{user_id}")
def get_pending_user_detail(user_id: str, db: Session = Depends(get_db), _admin=Depends(require_admin)):
    """Decrypted detail view — Admin-only, per-request authorized, and every
    view of PII should itself be considered for ledger logging in a fuller
    build (kept out here to avoid an on-chain event per read)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return {
        "id": user.id,
        "email": user.email,
        "full_name": decrypt_field(user.full_name_enc),
        "organisation": decrypt_field(user.organisation_enc),
        "phone_number": decrypt_field(user.phone_enc),
        "created_at": user.created_at.isoformat(),
    }


@router.post("/pending-users/{user_id}/approve")
def approve_user(user_id: str, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.status != UserStatus.PENDING_VERIFICATION:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending user with this id")

    user.status = UserStatus.ACTIVE
    db.commit()
    append_block(db, "USER_APPROVED", {"user_id": user.id, "approved_by": admin.id})
    return {"id": user.id, "status": user.status.value}


@router.post("/pending-users/{user_id}/reject")
def reject_user(
    user_id: str,
    body: AdminDecisionRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.status != UserStatus.PENDING_VERIFICATION:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No pending user with this id")

    user.status = UserStatus.REJECTED
    user.rejection_reason = body.reason
    db.commit()
    append_block(db, "USER_REJECTED", {"user_id": user.id, "rejected_by": admin.id, "reason": body.reason})
    return {"id": user.id, "status": user.status.value}
