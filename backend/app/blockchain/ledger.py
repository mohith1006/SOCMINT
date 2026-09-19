"""
Custom hash-chained ledger. No external blockchain framework — this is a
deliberately simple, auditable append-only log where each block commits to
the previous block's hash.

IMPORTANT: never write raw content, PII, or decrypted data on-chain — only
SHA-256 hashes of event payloads plus event-type metadata. The chain proves
"this event happened, in this order, unaltered" — it is not a data store.
"""
import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import LedgerBlock

GENESIS_EVENT_TYPE = "GENESIS"


def _hash_payload(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _compute_block_hash(index: int, timestamp: str, data_hash: str, event_type: str, previous_hash: str) -> str:
    combined = f"{index}{timestamp}{data_hash}{event_type}{previous_hash}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def ensure_genesis(db: Session) -> LedgerBlock:
    """Create the genesis block on first app boot if the chain is empty."""
    existing = db.query(LedgerBlock).filter(LedgerBlock.index == 0).first()
    if existing:
        return existing

    ts = datetime.now(timezone.utc).isoformat()
    data_hash = _hash_payload({"msg": "SOCMINT ledger genesis"})
    previous_hash = "0" * 64
    block_hash = _compute_block_hash(0, ts, data_hash, GENESIS_EVENT_TYPE, previous_hash)

    block = LedgerBlock(
        index=0,
        timestamp=datetime.now(timezone.utc),
        timestamp_iso=ts,
        data_hash=data_hash,
        event_type=GENESIS_EVENT_TYPE,
        previous_hash=previous_hash,
        hash=block_hash,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


def append_block(db: Session, event_type: str, payload: dict) -> LedgerBlock:
    """Append a new event to the chain. `payload` should contain only
    hashable metadata — never raw PII or decrypted content."""
    last = db.query(LedgerBlock).order_by(LedgerBlock.index.desc()).first()
    if last is None:
        last = ensure_genesis(db)

    ts = datetime.now(timezone.utc).isoformat()
    data_hash = _hash_payload(payload)
    new_index = last.index + 1
    block_hash = _compute_block_hash(new_index, ts, data_hash, event_type, last.hash)

    block = LedgerBlock(
        index=new_index,
        timestamp=datetime.now(timezone.utc),
        timestamp_iso=ts,
        data_hash=data_hash,
        event_type=event_type,
        previous_hash=last.hash,
        hash=block_hash,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


def verify_chain(db: Session) -> dict:
    """Recompute every hash in the chain. Returns {valid, brokenAtIndex}."""
    blocks = db.query(LedgerBlock).order_by(LedgerBlock.index.asc()).all()
    if not blocks:
        return {"valid": True, "brokenAtIndex": None}

    expected_previous = "0" * 64
    for block in blocks:
        recomputed = _compute_block_hash(
            block.index, block.timestamp_iso, block.data_hash, block.event_type, block.previous_hash
        )
        if block.previous_hash != expected_previous or recomputed != block.hash:
            return {"valid": False, "brokenAtIndex": block.index}
        expected_previous = block.hash

    return {"valid": True, "brokenAtIndex": None}
