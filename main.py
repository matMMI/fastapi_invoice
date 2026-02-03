from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from core.config import settings
from core.rate_limit import limiter
from routers import clients, quotes, pdf, dashboard, share
from routers import settings as settings_router

app = FastAPI(
    title="Devis Generator API",
    version="1.0.0",
    description="API for the Invoice/Devis Generator application",
    docs_url="/api/docs" if settings.environment != "production" else None,
    openapi_url="/api/openapi.json" if settings.environment != "production" else None,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.cors_origins],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
        expose_headers=["Content-Disposition"],
    )
app.include_router(clients.router, prefix="/api", tags=["clients"])
app.include_router(quotes.router, prefix="/api", tags=["quotes"])
app.include_router(pdf.router, prefix="/api", tags=["pdf"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(share.router, prefix="/api", tags=["share"])
@app.get("/")
async def root():
    return {"message": "Devis Generator API", "status": "ok"}
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
