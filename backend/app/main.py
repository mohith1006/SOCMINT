import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine, SessionLocal
from app.blockchain.ledger import ensure_genesis
from app.bootstrap import ensure_default_admin
from app.routers import auth, admin, ledger, network, nlp, trends, demographics, stubs, dashboard

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev convenience only — production uses Alembic migrations
    # (see alembic/ and the README "Migrations" section).
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        ensure_genesis(db)
        ensure_default_admin(db)
    finally:
        db.close()
    yield


app = FastAPI(title="SOCMINT API", version="0.1.0", lifespan=lifespan)

# CORS is permissive here for local dev only; lock allow_origins down to
# the deployed frontend origin in production. allow_credentials=False is
# deliberate: the frontend sends Bearer tokens (Authorization header via
# axios), never cookies, so there's no browser credentials mode to allow —
# and allow_origins=["*"] combined with allow_credentials=True is invalid
# per the CORS spec anyway (browsers reject that combination for
# credentialed requests).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(ledger.router)
app.include_router(network.router)
app.include_router(nlp.router)
app.include_router(trends.router)
app.include_router(demographics.router)
app.include_router(stubs.router)
app.include_router(dashboard.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "socmint-api"}
