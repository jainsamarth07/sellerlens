"""FastAPI application entry-point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api import (
    ads,
    analytics,
    auth,
    chat,
    chat_sessions,
    health,
    listing,
    multi_period,
    upload,
)

app = FastAPI(
    title="E-Commerce Profit Analytics",
    description="AI-powered profit analytics for Indian Flipkart / Amazon sellers",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers -----------------------------------------------------------------
app.include_router(health.router, tags=["Health"])
app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(upload.router, prefix="/api/upload", tags=["Upload"])
app.include_router(listing.router, prefix="/api/upload", tags=["Listing"])
app.include_router(ads.router, prefix="/api", tags=["Ads"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["Analytics"])
app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])
app.include_router(chat_sessions.router, prefix="/api/chat", tags=["ChatSessions"])
app.include_router(multi_period.router, prefix="/api/analytics", tags=["MultiPeriod"])
