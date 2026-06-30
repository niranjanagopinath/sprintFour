"""
Conseal Batch Review — FastAPI Backend

Entry point. Registers all routes, initializes database on startup,
and configures CORS for frontend dev server.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_schema, close_db, reset_category_stats
from routes import documents, spans, batch, audit, upload, entity_queue


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database schema and reset session-scoped state on startup."""
    import asyncio
    from services.detection_service import prewarm_models
    await init_schema()
    await reset_category_stats()
    # Pre-warm detection models in the background so the server accepts
    # requests immediately while models load; first batch won't be cold.
    asyncio.create_task(prewarm_models())
    yield
    await close_db()


app = FastAPI(
    title="Conseal Batch Review API",
    description="PII redaction review tool backend",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                "http://localhost:5174", "http://127.0.0.1:5174",
                "http://localhost:5175", "http://127.0.0.1:5175"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(documents.router)
app.include_router(upload.router)
app.include_router(spans.router)
app.include_router(batch.router)
app.include_router(audit.router)
app.include_router(entity_queue.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
