"""
Sarcasm detection (Section 7-B): "best-effort classifier, explicitly labeled
'experimental / low confidence' in the UI" — the spec's own words, worth
taking literally. Sarcasm detection is a genuinely hard NLP problem even in
English; cross-lingual sarcasm detection is a research problem, not a
solved one. So: real classifier for English, and an honest `None` (not a
guessed signal) for every other language rather than fabricating one.

Model: helinivan/english-sarcasm-detector (BERT fine-tuned on Kaggle news
headlines, labels 0=Not Sarcastic / 1=Sarcastic, ~92% reported accuracy on
its own headline-style test set — headlines are a narrower domain than
social media posts, so treat that number as optimistic for this use case).
Called via AutoModelForSequenceClassification directly (matching the model
card's documented usage) rather than the generic `pipeline()` wrapper, to
avoid relying on default LABEL_0/LABEL_1 naming that isn't guaranteed to
mean what you'd assume.
"""
from functools import lru_cache
import string

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

SARCASM_SUPPORTED_LANGS = {"en"}
MODEL_PATH = "helinivan/english-sarcasm-detector"


def _preprocess(text: str) -> str:
    return text.lower().translate(str.maketrans("", "", string.punctuation)).strip()


@lru_cache
def _tokenizer():
    return AutoTokenizer.from_pretrained(MODEL_PATH)


@lru_cache
def _model():
    return AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)


def detect_sarcasm(text: str, lang: str | None) -> tuple[bool | None, float | None]:
    """Returns (is_sarcastic, confidence). Both None = not evaluated for
    this language, not "not sarcastic" — the frontend must distinguish
    those two states and label this feature experimental either way."""
    if lang not in SARCASM_SUPPORTED_LANGS:
        return None, None

    tokenized = _tokenizer()(
        [_preprocess(text)], padding=True, truncation=True, max_length=256, return_tensors="pt"
    )
    with torch.no_grad():
        output = _model()(**tokenized)
    probs = output.logits.softmax(dim=-1).tolist()[0]
    confidence = max(probs)
    prediction = probs.index(confidence)
    return bool(prediction == 1), round(confidence, 4)
