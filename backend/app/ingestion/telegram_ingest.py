"""
Telegram ingestion via telethon.

Telegram has no native geo filter, so channel selection + language detection
is the mechanism for India-scoping (per Section 5). The seed channel list is
config-driven (TELEGRAM_SEED_CHANNELS in .env) — never hardcode channels here,
since relevant communities shift over time.

Run standalone for a one-off pull:
    python -m app.ingestion.telegram_ingest

In production this is scheduled via APScheduler (see app/scheduler.py, TODO)
so it runs as a recurring background job rather than manually.
"""
import asyncio

from langdetect import detect, LangDetectException
from telethon import TelegramClient
from telethon.errors import FloodWaitError

from app.config import get_settings
from app.database import SessionLocal
from app.models import Post
from app.blockchain.ledger import append_block

settings = get_settings()

# Region-association is a probabilistic tag, never an assertion of a real
# individual's location. This first pass tags purely on channel origin +
# detected language; posting-time timezone-pattern scoring is a TODO
# (build-order step 5/9) that refines `region_confidence` further.
INDIAN_LANGS = {"hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "pa", "ur", "en"}


def _detect_lang(text: str) -> str | None:
    try:
        return detect(text) if text.strip() else None
    except LangDetectException:
        return None


async def ingest_once(limit_per_channel: int = 100) -> int:
    if not settings.telegram_api_id or not settings.telegram_api_hash:
        raise RuntimeError("TELEGRAM_API_ID / TELEGRAM_API_HASH not set in .env")

    channels = settings.telegram_channel_list
    if not channels:
        raise RuntimeError(
            "TELEGRAM_SEED_CHANNELS is empty — add comma-separated public "
            "channel usernames to .env, e.g. TELEGRAM_SEED_CHANNELS=channel1,channel2"
        )

    client = TelegramClient(
        settings.telegram_session_name, int(settings.telegram_api_id), settings.telegram_api_hash
    )
    ingested = 0
    db = SessionLocal()
    try:
        await client.start()
        for channel in channels:
            try:
                async for message in client.iter_messages(channel, limit=limit_per_channel):
                    if not message.text:
                        continue

                    platform_post_id = str(message.id)
                    existing = db.query(Post).filter(
                        Post.platform == "telegram", Post.platform_post_id == platform_post_id
                    ).first()
                    if existing is not None:
                        continue  # already ingested -- re-running over an overlapping
                                   # window must not duplicate rows (see models.py)

                    lang = _detect_lang(message.text)
                    is_india_signal = lang in INDIAN_LANGS if lang else False
                    post = Post(
                        platform="telegram",
                        platform_post_id=platform_post_id,
                        author_handle=str(message.sender_id) if message.sender_id else "unknown",
                        text=message.text,
                        lang=lang,
                        region_tag="india" if is_india_signal else "unclassified",
                        region_confidence=0.5 if is_india_signal else 0.1,
                        posted_at=message.date,
                        raw_metadata={"channel": channel, "message_id": message.id},
                    )
                    db.add(post)
                    ingested += 1
            except FloodWaitError as e:
                # Zero Trust / good citizenship: respect Telegram's own rate
                # limiting rather than hammering the API.
                await asyncio.sleep(e.seconds)

        db.commit()
        append_block(
            db,
            "INGESTION_CHECKPOINT",
            {"platform": "telegram", "channels": channels, "count": ingested},
        )
    finally:
        await client.disconnect()
        db.close()

    return ingested


if __name__ == "__main__":
    count = asyncio.run(ingest_once())
    print(f"Ingested {count} Telegram posts.")
