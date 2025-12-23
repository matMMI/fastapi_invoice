from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from core.config import settings
from routers import clients, quotes, pdf, dashboard
app = FastAPI(
    title="Devis Generator API",
    version="1.0.0",
    description="API for the Invoice/Devis Generator application",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)
if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.cors_origins],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(clients.router, prefix="/api", tags=["clients"])
app.include_router(quotes.router, prefix="/api", tags=["quotes"])
app.include_router(pdf.router, prefix="/api", tags=["pdf"])
app.include_router(dashboard.router, prefix="/api", tags=["dashboard"])
@app.get("/")
async def root():
    return {"message": "Hello World", "environment": settings.environment}
@app.get("/health")
async def health_check():
    return {"status": "healthy"}
