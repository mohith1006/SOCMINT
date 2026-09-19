"""
Orchestrates the three classifiers in app/ml/ (emotion, stance, sarcasm)
over posts that don't have a `sentiment_scores` row yet, and persists
results — the actual wiring that build-order step 7 needs beyond having
the classifiers exist in isolation.
"""
from sqlalchemy.orm import Session

from app.models import Post, SentimentScore, Topic, PostTopic
from app.ml.emotion import classify_emotion
from app.ml.stance import find_best_topic, classify_stance
from app.ml.sarcasm import detect_sarcasm
from app.blockchain.ledger import append_block


def process_unscored_posts(db: Session, limit: int = 200) -> dict:
    """Finds posts with no sentiment_scores row, classifies each, and
    writes sentiment_scores (+ post_topics when a topic match clears the
    similarity bar). Returns a summary; also writes an NLP_PROCESSING_RUN
    ledger checkpoint, since Section 4 calls for hashing "generated
    reports/exports" — a processing run's output counts as one."""
    already_scored = {row.post_id for row in db.query(SentimentScore.post_id).all()}

    posts_query = db.query(Post)
    if already_scored:
        posts_query = posts_query.filter(Post.id.notin_(already_scored))
    posts = posts_query.limit(limit).all()

    topics = [(t.id, t.label) for t in db.query(Topic.id, Topic.label).all()]

    processed = 0
    topic_matches = 0
    sarcasm_evaluated = 0

    for post in posts:
        emotion_result = classify_emotion(post.text, post.lang)

        topic_id, similarity = find_best_topic(post.text, topics)
        stance = None
        stance_confidence = 0.0
        if topic_id is not None:
            topic_label = next(label for tid, label in topics if tid == topic_id)
            stance, stance_confidence = classify_stance(
                post.text, topic_label, post.lang, emotion_result["sentiment"]
            )
            topic_matches += 1
            db.add(PostTopic(post_id=post.id, topic_id=topic_id, score=round(similarity, 4)))

        is_sarcastic, sarcasm_confidence = detect_sarcasm(post.text, post.lang)
        if is_sarcastic is not None:
            sarcasm_evaluated += 1

        db.add(SentimentScore(
            post_id=post.id,
            sentiment=emotion_result["sentiment"],
            emotion_bucket=emotion_result["emotion_bucket"],
            stance_topic_id=topic_id,
            stance=stance,
            confidence=emotion_result["confidence"],
            sarcasm_flag=is_sarcastic,
            sarcasm_confidence=sarcasm_confidence,
        ))
        processed += 1

    db.commit()

    total_matching_filter = posts_query.count()
    summary = {
        "processed": processed,
        "topic_matches": topic_matches,
        "sarcasm_evaluated": sarcasm_evaluated,
        "remaining_unscored": total_matching_filter - processed,
    }

    if processed > 0:
        append_block(db, "NLP_PROCESSING_RUN", summary)

    return summary
