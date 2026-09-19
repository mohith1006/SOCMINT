FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

# torch first, from the CPU-only wheel index — the default PyPI wheel
# bundles CUDA and is 2GB+; this backend never uses a GPU, so that's pure
# build-time/image-size cost for nothing. Installing it first means the
# `pip install -r requirements.txt` below sees torch==<pinned version>
# already satisfied and skips re-downloading the heavy default wheel.
COPY requirements.txt .
RUN grep '^torch==' requirements.txt | xargs -I{} pip install --no-cache-dir {} --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download the HuggingFace models used by app/ml/{emotion,stance,sarcasm}.py
# at BUILD time rather than on first API call. This trades a larger/slower
# image build for a demo that never stalls on a live model download during
# actual judging — see Section 11's "reliability during judging" goal.
# Keep this list in sync with the model names hardcoded in app/ml/*.py.
RUN python -c "\
from transformers import pipeline, AutoModelForSequenceClassification, AutoTokenizer; \
pipeline('text-classification', model='SamLowe/roberta-base-go_emotions', top_k=1); \
pipeline('text-classification', model='cardiffnlp/twitter-xlm-roberta-base-sentiment', top_k=1); \
pipeline('zero-shot-classification', model='MoritzLaurer/mDeBERTa-v3-base-mnli-xnli'); \
AutoTokenizer.from_pretrained('helinivan/english-sarcasm-detector'); \
AutoModelForSequenceClassification.from_pretrained('helinivan/english-sarcasm-detector')"

COPY . .

EXPOSE 8000

# --proxy-headers + --forwarded-allow-ips: WITHOUT these, uvicorn ignores the
# X-Forwarded-For header Caddy sends and reports every request's client IP as
# Caddy's own internal Docker address — identical for every real visitor. That
# silently breaks the whole point of binding sessions to a device/IP fingerprint
# (app/deps.py, app/security/jwt.py): the IP component would be the same for
# every user behind the proxy, not a real per-user signal. Restricting
# forwarded-allow-ips to the docker-compose network's subnet (not "*") means
# only Caddy itself is trusted to supply a forwarded IP — a request that
# reaches this container directly, bypassing Caddy, can't spoof its way past
# the fingerprint check by injecting its own X-Forwarded-For header.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=172.16.0.0/12"]
