"""
Stance detection (Section 7-B): pair a post with its top-matched topic and
classify supportive / against / neutral.

Topic matching here is lightweight TF-IDF cosine similarity against
existing `topics.label` values — a real topic-modeling pass (TF-IDF/n-gram
extraction across the whole corpus, velocity scoring) is build-order step
8. This only matches an already-scored post against topics that already
exist.

Language coverage is tiered, same honesty pattern as app/ml/emotion.py and
app/ml/sarcasm.py:
- en, hi: real zero-shot NLI-based stance classification, via a
  multilingual NLI model (MoritzLaurer/mDeBERTa-v3-base-mnli-xnli) whose
  fine-tuning/eval languages are exactly the 15 XNLI languages — en and hi
  are both in that set, so this is validated, not hopeful transfer.
- te, ta, bn: NOT in XNLI's 15 languages, so this model's benchmarked
  quality doesn't cover them. Rather than assume decent zero-shot transfer
  from the pretrained-but-unvalidated 100-language base, these three fall
  back to a much weaker sentiment-as-proxy heuristic (positive sentiment ->
  "supportive", negative -> "against"). This is a coarse placeholder, not
  real stance detection, and is flagged with a low fixed confidence rather
  than a model score. TODO: replace with a validated approach for te/ta/bn
  — e.g. a fine-tuned Indic-language NLI model — before trusting this at
  demo time.
"""
from functools import lru_cache

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from transformers import pipeline

NLI_STANCE_LANGS = {"en", "hi"}
TOPIC_MATCH_MIN_SIMILARITY = 0.12  # below this, treat the post as topic-less
HEURISTIC_STANCE_CONFIDENCE = 0.3  # deliberately low & fixed — not a model score


@lru_cache
def _stance_nli_pipeline():
    return pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")


def find_best_topic(text: str, topics: list[tuple[str, str]]) -> tuple[str | None, float]:
    """`topics`: list of (topic_id, label). Returns (topic_id or None, similarity).
    None means no topic cleared the minimum-similarity bar."""
    if not topics:
        return None, 0.0

    labels = [label for _, label in topics]
    vectorizer = TfidfVectorizer().fit(labels + [text])
    text_vec = vectorizer.transform([text])
    label_vecs = vectorizer.transform(labels)
    sims = cosine_similarity(text_vec, label_vecs)[0]

    best_idx = int(sims.argmax())
    if sims[best_idx] < TOPIC_MATCH_MIN_SIMILARITY:
        return None, float(sims[best_idx])
    return topics[best_idx][0], float(sims[best_idx])


def classify_stance(text: str, topic_label: str, lang: str | None, sentiment: str) -> tuple[str, float]:
    """Returns (stance, confidence) where stance is one of
    "supportive" | "against" | "neutral"."""
    if lang in NLI_STANCE_LANGS:
        candidate_labels = [
            f"supportive of {topic_label}",
            f"against {topic_label}",
            f"neutral about {topic_label}",
        ]
        result = _stance_nli_pipeline()(text, candidate_labels)
        top_label = result["labels"][0]
        confidence = round(result["scores"][0], 4)
        if top_label.startswith("supportive"):
            return "supportive", confidence
        if top_label.startswith("against"):
            return "against", confidence
        return "neutral", confidence

    # Heuristic fallback for te/ta/bn (and anything else) — see docstring.
    if sentiment == "positive":
        return "supportive", HEURISTIC_STANCE_CONFIDENCE
    if sentiment == "negative":
        return "against", HEURISTIC_STANCE_CONFIDENCE
    return "neutral", HEURISTIC_STANCE_CONFIDENCE
