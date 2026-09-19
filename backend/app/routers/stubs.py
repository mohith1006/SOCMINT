"""
Stub endpoints for the pages not yet fully implemented — just live
monitoring (Section 10, page 4) at this point. Returns a clearly-flagged
synthetic/placeholder response so the frontend has something real to
render against while step 5's live WebSocket streaming is built out.

Graph/centrality/community detection (step 6) moved to
app/routers/network.py + app/analytics/network.py. NLP processing +
sentiment timeline (step 7) moved to app/routers/nlp.py +
app/ml/{emotion,stance,sarcasm,pipeline}.py. Trend detection, causal
impact scoring, and propagation replay (step 8) moved to
app/routers/{trends,network}.py + app/analytics/{trends,causal_impact,
propagation}.py. Demographic aggregation (step 9) moved to
app/routers/demographics.py + app/analytics/demographics.py. All real
implementations now, not stubs.
"""
from fastapi import APIRouter, Depends

from app.config import get_settings
from app.deps import get_current_user

router = APIRouter(tags=["stubs"])
settings = get_settings()


@router.get("/meta/languages")
def supported_languages():
    """Single source of truth the frontend could fetch instead of
    hardcoding SUPPORTED_LANGUAGES in src/i18n/index.ts, if preferred."""
    return {"languages": settings.supported_ui_languages}


@router.get("/live/status")
def live_status(_user=Depends(get_current_user)):
    # TODO(build-order step 5/10): real Socket.IO push of ingestion events;
    # this stub just tells the frontend which mode to render.
    return {"mode": "static_sample", "posts_per_minute": 0, "trending": [], "india_mood": {}}
