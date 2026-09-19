"""
Automated Demographic Profiling (Section 7-C).

Structural privacy guarantee: this module NEVER computes or returns a
demographic value tied to a single user or post — every function here
operates on and returns COMMUNITY-LEVEL aggregate counts/percentages only.
There is no function in this file that accepts a user handle and returns
that user's inferred demographics; that's not an oversight to fix later,
it's the point, matching Section 7-C's own requirement: "the API must
structurally prevent returning any demographic label tied to a single
user ID."

Three dimensions, per the Section 9 schema (`dimension` enum:
age_bracket|language|region):

- language: Post.lang, from langdetect at ingestion time — a real,
  already-collected signal.
- region: Post.region_tag, the same probabilistic India-association tag
  used elsewhere in the platform — already a coarse, low-confidence
  signal by design (see app/ingestion/*.py), not re-derived here.
- age_bracket: the weakest signal by far, and worth being blunt about.
  Section 7-C's own description ("infer from post language, bio-text
  keywords, and posting-time-derived rough timezone") describes input
  signals for the platform generally, not a validated age-inference
  method. There's no separate bio-text/profile field in this schema
  (posts, not profiles, are what's stored), so this substitutes a small
  set of self-disclosure keyword patterns scanned in post text — "17
  years old", "in college", "retired", etc. Expect the overwhelming
  majority of posts to land in "unknown"; treat any non-"unknown"
  bucket's aggregate percentage as a weak signal, not a measured
  demographic breakdown.

Privacy mechanism, applied in this order:
1. k-anonymity-style suppression: any (community, dimension, value) cell
   with fewer than `min_cell_count` real posts is dropped entirely BEFORE
   noise is added. Small cells are where re-identification risk
   concentrates; noise alone doesn't fix that.
2. Laplace-mechanism differential privacy on surviving cells: each count
   gets Laplace(0, 1/epsilon) noise added (sensitivity=1 for a count
   query — one more/fewer post changes the count by at most 1), clipped
   at 0. Percentages are computed from the NOISED counts, never the raw
   ones.

Default epsilon=1.0 and min_cell_count=5 are reasonable starting points,
not a calibrated privacy budget for any specific legal/regulatory
requirement — tune per deployment. On sparse data (e.g. the synthetic
generator's default 300 posts spread across communities), most cells will
fall below the suppression floor and aggregates will come back mostly
empty — that's the privacy control working as designed, not a bug.
"""
import math
import random
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Post, DemographicAggregate, UserCommunityMembership, Community
from app.blockchain.ledger import append_block

DIMENSIONS = ("language", "region", "age_bracket")
MIN_CELL_COUNT = 5  # k-anonymity-style suppression floor
DEFAULT_EPSILON = 1.0  # Laplace mechanism privacy budget — see docstring

AGE_BRACKET_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("under_18", re.compile(r"\b1[0-7]\s*(years old|yo|y/o)\b", re.IGNORECASE)),
    ("under_18", re.compile(r"\b(in|at)\s+(high school|middle school)\b", re.IGNORECASE)),
    ("18_24", re.compile(r"\b(college|university|undergrad)\b", re.IGNORECASE)),
    ("50_plus", re.compile(r"\b(retired|retirement|my grandchildren|my grandkids)\b", re.IGNORECASE)),
]


def infer_age_bracket(text: str) -> str:
    """Best-effort, low-confidence keyword match. Returns "unknown" for
    the overwhelming majority of text — see module docstring."""
    for bucket, pattern in AGE_BRACKET_PATTERNS:
        if pattern.search(text):
            return bucket
    return "unknown"


def _laplace_noise(scale: float, rng: random.Random) -> float:
    """Sample from Laplace(0, scale) via inverse-CDF from a uniform variate."""
    u = rng.uniform(-0.5, 0.5)
    sign = 1.0 if u >= 0 else -1.0
    magnitude = min(abs(u), 0.5 - 1e-12)  # guards math.log(0) at the u=±0.5 boundary
    return -scale * sign * math.log(1 - 2 * magnitude)


def compute_demographic_aggregates(
    db: Session,
    dimension: str,
    epsilon: float = DEFAULT_EPSILON,
    min_cell_count: int = MIN_CELL_COUNT,
    rng_seed: int | None = None,
) -> list[dict]:
    """Returns [{community_id, community_label, dimension, value, pct}]
    for one dimension. Never returns anything keyed by user or post."""
    if dimension not in DIMENSIONS:
        raise ValueError(f"Unknown dimension: {dimension}")

    latest_community = db.query(Community).order_by(Community.created_at.desc()).first()
    if not latest_community:
        return []

    memberships = (
        db.query(UserCommunityMembership, Community)
        .join(Community, UserCommunityMembership.community_id == Community.id)
        .filter(Community.algorithm_run_id == latest_community.algorithm_run_id)
        .all()
    )
    community_by_user = {m.user_handle: c.id for m, c in memberships}
    community_label_by_id = {c.id: c.label for _, c in memberships}
    if not community_by_user:
        return []

    posts = db.query(Post).filter(Post.author_handle.in_(community_by_user.keys())).all()

    raw_counts: dict[tuple[str, str], int] = {}
    for post in posts:
        community_id = community_by_user.get(post.author_handle)
        if not community_id:
            continue
        if dimension == "language":
            value = post.lang or "unknown"
        elif dimension == "region":
            value = post.region_tag or "unclassified"
        else:  # age_bracket
            value = infer_age_bracket(post.text)
        key = (community_id, value)
        raw_counts[key] = raw_counts.get(key, 0) + 1

    # 1. k-anonymity-style suppression, BEFORE noise.
    suppressed = {k: v for k, v in raw_counts.items() if v >= min_cell_count}

    # 2. Laplace noise on surviving cells.
    rng = random.Random(rng_seed)
    scale = 1.0 / epsilon
    noised_counts: dict[tuple[str, str], int] = {
        key: max(0, round(count + _laplace_noise(scale, rng)))
        for key, count in suppressed.items()
    }

    # Percentages from NOISED counts only, per community.
    community_totals: dict[str, int] = {}
    for (community_id, _value), count in noised_counts.items():
        community_totals[community_id] = community_totals.get(community_id, 0) + count

    results = []
    for (community_id, value), count in noised_counts.items():
        total = community_totals.get(community_id, 0)
        if total == 0:
            continue
        results.append({
            "community_id": community_id,
            "community_label": community_label_by_id.get(community_id, "unknown"),
            "dimension": dimension,
            "value": value,
            "pct": round(100.0 * count / total, 2),
        })
    return results


def run_demographic_aggregation(
    db: Session,
    epsilon: float = DEFAULT_EPSILON,
    min_cell_count: int = MIN_CELL_COUNT,
) -> dict:
    """Computes + persists all three dimensions in one run, sharing a
    single computed_at timestamp (so GET /demographics can group "the
    latest run" per dimension without a dedicated run-id column) and one
    ledger checkpoint covering all three."""
    now = datetime.utcnow()
    summary = {}

    for dimension in DIMENSIONS:
        results = compute_demographic_aggregates(db, dimension, epsilon, min_cell_count)
        for row in results:
            db.add(DemographicAggregate(
                community_id=row["community_id"],
                dimension=row["dimension"],
                value=row["value"],
                pct=row["pct"],
                computed_at=now,
            ))
        summary[dimension] = len(results)

    db.commit()
    append_block(db, "DEMOGRAPHIC_AGGREGATION_RUN", {
        "epsilon": epsilon,
        "min_cell_count": min_cell_count,
        "cell_counts": summary,
    })
    return summary
