"""
Real-Time Trend & Topic Detection (Section 7-D): n-gram extraction per time
window against a rolling baseline, flagging "predicted rising" topics by
rate of change rather than absolute volume.

Honest limitation on multilingual coverage: tokenization is a simple
Unicode-range regex splitter, and stopword removal only covers English
(scikit-learn's built-in list). Hindi/Telugu/Tamil/Bengali posts still get
tokenized (their Unicode blocks aren't dropped), but function words /
grammatical particles in those languages are NOT filtered the way English
stopwords are — non-English trend rankings will be noisier until real
Indic-language stopword lists are wired in. TODO before trusting them at
demo time; this is a genuinely different gap from the emotion/stance/
sarcasm modules' language-tiering, worth calling out separately.
"""
import re
from collections import Counter
from datetime import datetime, timedelta

from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
from sqlalchemy.orm import Session

from app.models import Post, Topic
from app.blockchain.ledger import append_block

WINDOW_DAYS = 1  # "today" bucket
BASELINE_WINDOWS = 7  # compare against the trailing 7-day daily average
MIN_MENTIONS_TO_RANK = 3  # ignore near-zero-sample terms entirely — see docstring
TOP_N_TRENDING = 20

# Word-ish tokens of 3+ chars. Unicode ranges: Latin, Devanagari (Hindi),
# Telugu, Tamil, Bengali — so non-Latin scripts aren't silently dropped by
# an ASCII-only regex, even though downstream stopword filtering is still
# English-only (see module docstring).
TOKEN_RE = re.compile(r"[a-zA-Z\u0900-\u097F\u0C00-\u0C7F\u0B80-\u0BFF\u0980-\u09FF]{3,}")


def _tokenize(text: str) -> list[str]:
    tokens = [t.lower() for t in TOKEN_RE.findall(text)]
    return [t for t in tokens if t not in ENGLISH_STOP_WORDS]


def _ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def _window_term_counts(posts: list[Post]) -> Counter:
    counts: Counter = Counter()
    for post in posts:
        tokens = _tokenize(post.text)
        counts.update(tokens)
        counts.update(_ngrams(tokens, 2))
    return counts


def compute_trends(db: Session, now: datetime | None = None) -> list[dict]:
    """Returns candidate trending terms, ranked by velocity (rate of
    change vs. rolling baseline), not raw mention count."""
    now = now or datetime.utcnow()
    today_start = now - timedelta(days=WINDOW_DAYS)
    baseline_start = today_start - timedelta(days=BASELINE_WINDOWS)

    today_posts = db.query(Post).filter(Post.posted_at >= today_start, Post.posted_at < now).all()
    baseline_posts = db.query(Post).filter(
        Post.posted_at >= baseline_start, Post.posted_at < today_start
    ).all()

    today_counts = _window_term_counts(today_posts)
    baseline_counts = _window_term_counts(baseline_posts)
    baseline_days = max(BASELINE_WINDOWS, 1)

    results = []
    for term, today_freq in today_counts.items():
        if today_freq < MIN_MENTIONS_TO_RANK:
            continue
        baseline_avg = baseline_counts.get(term, 0) / baseline_days
        # +1 in the denominator avoids a divide-by-zero for brand-new terms
        # and dampens their velocity slightly rather than letting a single
        # day-one mention register as "infinite" growth.
        velocity = (today_freq - baseline_avg) / (baseline_avg + 1.0)
        results.append({
            "label": term,
            "mentions_today": today_freq,
            "baseline_avg_per_day": round(baseline_avg, 2),
            "velocity_score": round(velocity, 4),
        })

    results.sort(key=lambda r: r["velocity_score"], reverse=True)
    return results[:TOP_N_TRENDING]


def persist_trends(db: Session, trends: list[dict]) -> int:
    """Upserts into `topics` by label — updates velocity_score if the
    label already exists, else creates a new Topic with first_seen=now.
    This is also what feeds app/ml/stance.py's topic matching."""
    updated = 0
    for trend in trends:
        existing = db.query(Topic).filter(Topic.label == trend["label"]).first()
        if existing:
            existing.velocity_score = trend["velocity_score"]
        else:
            db.add(Topic(label=trend["label"], velocity_score=trend["velocity_score"]))
        updated += 1
    db.commit()

    append_block(db, "TREND_DETECTION_RUN", {"topic_count": updated})
    return updated
