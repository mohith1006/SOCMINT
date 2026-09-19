"""
Sentiment + emotion-bucket classification (Section 7-B, Section 8), built to
cover the platform's five supported languages: English, Hindi, Telugu,
Tamil, Bengali.

Honest architecture note on language coverage:
- GoEmotions-based fine-grained emotion models (~27 categories) are trained
  on English text only. There is no equivalent well-validated fine-grained
  emotion model across hi/te/ta/bn as of this writing.
- So: English text runs through the full GoEmotions-based pipeline. Text in
  hi/te/ta/bn runs through a multilingual sentiment model instead (3-way
  positive/neutral/negative), which is then mapped to the same 5 display
  buckets at coarser granularity.
- TODO: as validated fine-grained emotion models for Indic languages become
  available (or once budget allows fine-tuning one on labeled Indic data),
  swap the `else` branch below for real per-language emotion classifiers
  instead of the sentiment-only fallback. Benchmark actual accuracy on
  hi/te/ta/bn before trusting the multilingual sentiment model's output at
  the same confidence level as the English path — cross-lingual transfer
  quality varies a lot by language and was not verified here.

Emotion buckets (Section 8) — deliberately NOT "depressed": a textual-
expression indicator, not a clinical diagnosis, never a per-individual
mental-health assessment.
"""
from functools import lru_cache

from transformers import pipeline

EMOTION_BUCKETS = ["happy", "joyful", "sad", "angry", "low_mood_distress_signal"]

# English fine-grained model -> 5-bucket mapping. GoEmotions' 27 labels
# collapsed into the display buckets; extend/adjust based on judging feedback.
GOEMOTIONS_TO_BUCKET = {
    "joy": "joyful", "amusement": "joyful", "excitement": "joyful", "love": "joyful",
    "admiration": "happy", "approval": "happy", "gratitude": "happy", "optimism": "happy",
    "relief": "happy", "pride": "happy", "caring": "happy",
    "sadness": "sad", "grief": "sad", "remorse": "sad", "disappointment": "sad",
    "anger": "angry", "annoyance": "angry", "disgust": "angry", "disapproval": "angry",
    "fear": "low_mood_distress_signal", "nervousness": "low_mood_distress_signal",
    "embarrassment": "low_mood_distress_signal", "confusion": "low_mood_distress_signal",
    "neutral": "happy",  # neutral text defaults to the mildest positive bucket, not sad
}

# Multilingual sentiment fallback (hi/te/ta/bn) -> 5-bucket mapping. Coarser
# by necessity — see module docstring.
SENTIMENT_TO_BUCKET = {
    "positive": "happy",
    "neutral": "happy",
    "negative": "sad",
}

SUPPORTED_LANGUAGES = {"en", "hi", "te", "ta", "bn"}


@lru_cache
def _english_emotion_pipeline():
    # ~27-category GoEmotions-based classifier, English only.
    return pipeline(
        "text-classification",
        model="SamLowe/roberta-base-go_emotions",
        top_k=1,
    )


@lru_cache
def _multilingual_sentiment_pipeline():
    # XLM-R-based multilingual sentiment. Covers many languages via
    # cross-lingual transfer, but per-language accuracy on hi/te/ta/bn
    # specifically has not been benchmarked here — see docstring TODO.
    return pipeline(
        "text-classification",
        model="cardiffnlp/twitter-xlm-roberta-base-sentiment",
        top_k=1,
    )


def classify_emotion(text: str, lang: str | None) -> dict:
    """Returns {"emotion_bucket": str, "sentiment": str, "confidence": float}."""
    if lang == "en":
        result = _english_emotion_pipeline()(text)[0][0]
        label = result["label"].lower()
        bucket = GOEMOTIONS_TO_BUCKET.get(label, "happy")
        sentiment = "negative" if bucket in ("sad", "angry", "low_mood_distress_signal") else "positive"
        return {"emotion_bucket": bucket, "sentiment": sentiment, "confidence": round(result["score"], 4)}

    # hi / te / ta / bn (and anything else) fall back to sentiment-only.
    result = _multilingual_sentiment_pipeline()(text)[0][0]
    sentiment = result["label"].lower()
    bucket = SENTIMENT_TO_BUCKET.get(sentiment, "happy")
    return {"emotion_bucket": bucket, "sentiment": sentiment, "confidence": round(result["score"], 4)}
