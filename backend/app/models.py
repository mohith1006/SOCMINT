"""
ORM models for SOCMINT.

Fields suffixed `_enc` hold AES-256-GCM ciphertext (see app/security/aes.py).
They are encrypted/decrypted at the application layer, never in the DB.
Passcodes are bcrypt-hashed, not encrypted — hashing is the correct,
irreversible approach for credentials. Do not "fix" this into encryption.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    String, DateTime, ForeignKey, Enum, Float, Integer, JSON, Boolean, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class UserStatus(str, enum.Enum):
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    REJECTED = "rejected"


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    INVESTIGATOR = "investigator"
    VIEWER = "viewer"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    passcode_hash: Mapped[str] = mapped_column(String, nullable=False)

    # AES-256-GCM encrypted PII fields
    full_name_enc: Mapped[str] = mapped_column(Text, nullable=False)
    organisation_enc: Mapped[str] = mapped_column(Text, nullable=False)
    phone_enc: Mapped[str] = mapped_column(Text, nullable=False)

    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER)
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.PENDING_VERIFICATION)

    mfa_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    mfa_enrolled: Mapped[bool] = mapped_column(Boolean, default=False)
    backup_codes_enc: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON list, encrypted

    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Password reset (forgot-passcode flow). Only the SHA-256 hash of the
    # reset token is stored, same principle as passcodes — the raw token
    # only ever exists in the emailed link, never at rest.
    reset_token_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    reset_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        # Nullable + unique: NULLs don't conflict with each other in Postgres
        # (each is treated as distinct), so pre-existing rows without a
        # platform_post_id (synthetic data, or anything ingested before this
        # column existed) are unaffected. New live-ingested rows that DO set
        # it get real dedup protection — re-running a connector over an
        # overlapping time window updates/skips instead of duplicating every
        # post, the same idempotency bug already caught and fixed once in
        # this project's interaction-ingestion path; this closes the same
        # gap for posts.
        UniqueConstraint("platform", "platform_post_id", name="uq_posts_platform_post_id"),
    )

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    platform: Mapped[str] = mapped_column(String, nullable=False)  # telegram | reddit | x
    platform_post_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    author_handle: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    lang: Mapped[str | None] = mapped_column(String, nullable=True)

    # Probabilistic tag — never an assertion about a real individual's location.
    region_tag: Mapped[str | None] = mapped_column(String, nullable=True)
    region_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    posted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # event time
    ingested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)  # pipeline time
    raw_metadata: Mapped[dict] = mapped_column(JSON, default=dict)


class Interaction(Base):
    __tablename__ = "interactions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    source_user: Mapped[str] = mapped_column(String, nullable=False)
    target_user: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[str] = mapped_column(String, nullable=False)  # mention|reply|share|follow
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Community(Base):
    __tablename__ = "communities"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    label: Mapped[str] = mapped_column(String, nullable=False)
    algorithm_run_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserCommunityMembership(Base):
    __tablename__ = "user_community_membership"

    user_handle: Mapped[str] = mapped_column(String, primary_key=True)
    community_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("communities.id"), primary_key=True)


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    label: Mapped[str] = mapped_column(String, nullable=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    velocity_score: Mapped[float] = mapped_column(Float, default=0.0)


class PostTopic(Base):
    __tablename__ = "post_topics"

    post_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("posts.id"), primary_key=True)
    topic_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("topics.id"), primary_key=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)


class SentimentScore(Base):
    __tablename__ = "sentiment_scores"

    post_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("posts.id"), primary_key=True)
    sentiment: Mapped[str] = mapped_column(String, nullable=False)  # positive|negative|neutral
    # Display bucket — see app/ml/emotion.py. Deliberately "low_mood_distress_signal",
    # never "depressed": a textual-expression indicator, not a clinical diagnosis.
    emotion_bucket: Mapped[str] = mapped_column(String, nullable=False)
    stance_topic_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False), ForeignKey("topics.id"), nullable=True)
    stance: Mapped[str | None] = mapped_column(String, nullable=True)  # supportive|against|neutral
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    # Extends the original Section 9 outline: Section 7-B separately calls
    # for a "best-effort, explicitly experimental / low confidence" sarcasm
    # signal (see app/ml/sarcasm.py). NULL means "not evaluated for this
    # language" — never coerce that to False in the UI.
    sarcasm_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    sarcasm_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)


class DemographicAggregate(Base):
    """Aggregate-only. The API layer must structurally prevent returning
    any demographic label tied to a single user ID — see app/routers stubs."""
    __tablename__ = "demographic_aggregates"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    community_id: Mapped[str] = mapped_column(UUID(as_uuid=False), ForeignKey("communities.id"))
    dimension: Mapped[str] = mapped_column(String, nullable=False)  # age_bracket|language|region
    value: Mapped[str] = mapped_column(String, nullable=False)
    pct: Mapped[float] = mapped_column(Float, nullable=False)  # noise-adjusted
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NodeInfluenceScore(Base):
    """Extends the original Section 9 outline: Section 7-E separately calls
    for a per-node "causal_impact_score" from Independent Cascade
    node-removal simulation (see app/analytics/causal_impact.py), which
    doesn't fit any existing table. One row per (node, analysis run) so
    history isn't overwritten, same pattern as `communities`."""
    __tablename__ = "node_influence_scores"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=gen_uuid)
    node_handle: Mapped[str] = mapped_column(String, nullable=False, index=True)
    algorithm_run_id: Mapped[str] = mapped_column(String, nullable=False)
    causal_impact_score: Mapped[float] = mapped_column(Float, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LedgerBlock(Base):
    __tablename__ = "ledger_blocks"

    index: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Exact ISO-8601 string used at hash-computation time. Stored verbatim
    # (rather than re-deriving from `timestamp`) so /ledger/verify recomputes
    # hashes deterministically regardless of DB datetime round-tripping.
    timestamp_iso: Mapped[str] = mapped_column(String, nullable=False)
    data_hash: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    previous_hash: Mapped[str] = mapped_column(String, nullable=False)
    hash: Mapped[str] = mapped_column(String, nullable=False)
