"""
FastAPI Application Server
CoinDCX futures advisor — confluence, SOP gates, PDF reports, optional LLM narrative.
"""

import asyncio
import logging

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from prometheus_fastapi_instrumentator import Instrumentator

from config.settings import settings
from src.api.routes.advisor import router as advisor_router, get_advisor_processor, shutdown_advisor_processor
from src.api.routes.news import router as news_router
from src.database.db import init_db
from src.monitoring.logger import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

shutdown_event = asyncio.Event()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        description="CoinDCX futures signal research — SOP-gated advisor PDFs with optional LLM narrative",
        version=settings.APP_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    cors_origins = [o.strip() for o in settings.FASTAPI_CORS_ORIGINS_RAW.split(",") if o.strip()]
    trusted_hosts = [h.strip() for h in settings.FASTAPI_TRUSTED_HOSTS_RAW.split(",") if h.strip()]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=trusted_hosts or ["*"],
    )

    app.include_router(advisor_router)
    app.include_router(news_router)

    if settings.ENABLE_PROMETHEUS:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": exc.detail, "status_code": exc.status_code},
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        logger.error("Unhandled exception: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": "Internal server error", "status_code": 500},
        )

    @app.get("/health", tags=["Health"])
    async def health_check():
        return {"status": "healthy", "app": settings.APP_NAME, "version": settings.APP_VERSION}

    def _service_links() -> dict:
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "message": "API-only server — no web dashboard. Use Swagger UI or curl.",
            "endpoints": {
                "docs": "/api/docs",
                "health": "/health",
                "advisor_generate": "POST /api/v1/advisor/generate (header x-api-key)",
                "advisor_health": "GET /api/v1/advisor/health (header x-api-key)",
                "news": "GET /api/v1/news",
                "metrics": "/metrics",
            },
            "pdf_output_dir": settings.ADVISOR_OUTPUT_DIR,
        }

    @app.get("/", tags=["Root"], include_in_schema=False)
    async def root(request: Request):
        """Browser-friendly entry: redirect to Swagger; JSON for API clients."""
        if "text/html" in (request.headers.get("accept") or ""):
            return RedirectResponse(url="/api/docs")
        return _service_links()

    @app.get("/api", tags=["Root"])
    async def api_root():
        return _service_links()

    async def pull_ollama_model() -> None:
        if settings.LLM_PROVIDER != "ollama":
            return
        model = settings.OLLAMA_MODEL
        base_url = settings.OLLAMA_BASE_URL
        logger.info("Checking Ollama availability at %s...", base_url)
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{base_url}/api/tags")
                if response.status_code == 200:
                    model_names = [m["name"] for m in response.json().get("models", [])]
                    candidates = {model, f"{model}:latest", model.split(":")[0] + ":latest"}
                    if candidates & set(model_names):
                        logger.info("Ollama model '%s' already available", model)
                        return
                logger.info("Pulling Ollama model '%s' (may take several minutes)...", model)
                pull = await client.post(
                    f"{base_url}/api/pull",
                    json={"name": model},
                    timeout=600.0,
                )
                if pull.status_code == 200:
                    logger.info("Successfully pulled Ollama model '%s'", model)
                else:
                    logger.warning("Failed to pull Ollama model: %s", pull.text)
        except httpx.ConnectError:
            logger.error("Cannot connect to Ollama at %s — narratives will use template fallback", base_url)
        except httpx.TimeoutException:
            logger.error("Ollama connection timeout at %s", base_url)
        except Exception as exc:
            logger.error("Error checking Ollama: %s", exc)

    @app.on_event("startup")
    async def startup_event():
        import config.settings as settings_mod
        from config.settings import get_settings

        get_settings.cache_clear()
        settings_mod.settings = get_settings()
        active = settings_mod.settings
        logger.info(
            "Advisor scan: timeframes=%s directions=%s sell_tfs=%s allowlist=%s",
            active.advisor_scan_timeframes,
            sorted(active.advisor_allowed_directions),
            sorted(active.advisor_sell_allowed_timeframes) or "none",
            len(active.advisor_symbol_allowlist or ()),
        )
        logger.info("=" * 60)
        logger.info("Starting %s", settings.APP_NAME)
        logger.info("=" * 60)

        from src.data.data_fetcher import DataFetcher

        fetcher = DataFetcher()
        if await fetcher.test_connection():
            logger.info("CoinDCX public API reachable")
        else:
            logger.warning("CoinDCX API health check failed")
        await fetcher.close()

        from src.database.db import test_connection

        if not await test_connection():
            raise RuntimeError("MongoDB is required — check MONGODB_URI")
        await init_db()
        logger.info("MongoDB initialized")

        if settings.ENABLE_LLM_ANALYSIS and settings.LLM_PROVIDER == "ollama":
            await pull_ollama_model()
        elif settings.ENABLE_LLM_ANALYSIS:
            logger.info("LLM provider: %s", settings.LLM_PROVIDER)

        if settings.ENABLE_BACKGROUND_SCANNER:
            logger.info("Background scanner is enabled in config, but runs via scripts/run_workers.py")
        else:
            logger.info("Background scanner disabled (ENABLE_BACKGROUND_SCANNER=false)")



        logger.info("Application startup complete")

    @app.on_event("shutdown")
    async def shutdown_handler():
        logger.info("Shutting down application...")
        shutdown_event.set()
        await shutdown_advisor_processor()



    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        workers=settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
