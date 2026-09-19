from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import LedgerBlock
from app.schemas import LedgerBlockOut, LedgerVerifyOut
from app.blockchain.ledger import verify_chain

router = APIRouter(prefix="/ledger", tags=["ledger"])


@router.get("", response_model=list[LedgerBlockOut])
def list_blocks(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    offset = (page - 1) * page_size
    blocks = (
        db.query(LedgerBlock)
        .order_by(LedgerBlock.index.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return [
        LedgerBlockOut(
            index=b.index,
            timestamp=b.timestamp_iso,
            data_hash=b.data_hash,
            event_type=b.event_type,
            previous_hash=b.previous_hash,
            hash=b.hash,
        )
        for b in blocks
    ]


@router.get("/verify", response_model=LedgerVerifyOut)
def verify(db: Session = Depends(get_db), _user=Depends(get_current_user)):
    result = verify_chain(db)
    return LedgerVerifyOut(**result)
