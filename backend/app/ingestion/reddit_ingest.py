"""
Reddit ingestion via praw. Structurally identical to the Telegram connector —
config-driven seed subreddit list (REDDIT_SEED_SUBREDDITS in .env), tag
rather than discard content, one ledger checkpoint per ingestion run.

TODO: wire in real REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET once available.
Until then, use scripts/generate_synthetic_data.py so the full demo works
end-to-end without live keys.
"""
import datetime as dt

from langdetect import detect, LangDetectException
import praw

from app.config import get_settings
from app.database import SessionLocal
from app.models import Post
from app.blockchain.ledger import append_block
from app.ingestion.telegram_ingest import INDIAN_LANGS  # shared language set

settings = get_settings()


def _detect_lang(text: str) -> str | None:
    try:
        return detect(text) if text.strip() else None
    except LangDetectException:
        return None


def ingest_once(limit_per_subreddit: int = 100) -> int:
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        raise RuntimeError(
            "REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not set — this connector "
            "is stubbed until real credentials are added to .env"
        )

    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
    )

    db = SessionLocal()
    ingested = 0
    try:
        for sub_name in settings.reddit_subreddit_list:
            subreddit = reddit.subreddit(sub_name)
            for submission in subreddit.new(limit=limit_per_subreddit):
                existing = db.query(Post).filter(
                    Post.platform == "reddit", Post.platform_post_id == submission.id
                ).first()
                if existing is not None:
                    continue  # already ingested -- see models.py's UniqueConstraint docstring

                text = f"{submission.title}\n{submission.selftext or ''}".strip()
                lang = _detect_lang(text)
                is_india_signal = lang in INDIAN_LANGS if lang else False
                post = Post(
                    platform="reddit",
                    platform_post_id=submission.id,
                    author_handle=str(submission.author) if submission.author else "unknown",
                    text=text,
                    lang=lang,
                    region_tag="india" if is_india_signal else "unclassified",
                    # Subreddit origin is a stronger India signal than language alone.
                    region_confidence=0.8 if is_india_signal else 0.3,
                    # submission.created_utc is a Unix timestamp (float) -- was
                    # previously left as a TODO and hardcoded to None, which
                    # silently excluded every Reddit post from trend detection,
                    # propagation replay, and the sentiment timeline (all three
                    # filter on Post.posted_at.isnot(None)). Fixed.
                    posted_at=dt.datetime.fromtimestamp(submission.created_utc, tz=dt.timezone.utc),
                    raw_metadata={"subreddit": sub_name, "submission_id": submission.id},
                )
                db.add(post)
                ingested += 1

        db.commit()
        append_block(
            db,
            "INGESTION_CHECKPOINT",
            {"platform": "reddit", "subreddits": settings.reddit_subreddit_list, "count": ingested},
        )
    finally:
        db.close()

    return ingested


if __name__ == "__main__":
    count = ingest_once()
    print(f"Ingested {count} Reddit posts.")
