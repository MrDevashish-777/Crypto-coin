"""
FastAPI Application Server
Main entry point for the Crypto Trading Signal Server
"""

import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
import os
import httpx
from datetime import datetime
from config.settings import settings
from src.monitoring.logger import setup_logging
import asyncio
from src.api.routes.signals import router as signals_router, get_planitt_processor, shutdown_planitt_processor
from src.api.routes.advisor import router as advisor_router, get_advisor_processor, shutdown_advisor_processor
from src.api.routes.news import router as news_router
from src.database.db import init_db

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Shutdown event flag
shutdown_event = asyncio.Event()


def create_app() -> FastAPI:
    """Create and configure FastAPI application"""

    app = FastAPI(
        title=settings.APP_NAME,
        description="Professional-grade cryptocurrency trading signal server with AI analysis",
        version=settings.APP_VERSION,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    cors_origins = [o.strip() for o in settings.FASTAPI_CORS_ORIGINS_RAW.split(",") if o.strip()]
    trusted_hosts = [h.strip() for h in settings.FASTAPI_TRUSTED_HOSTS_RAW.split(",") if h.strip()]

    # Add CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add Trusted Host Middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=trusted_hosts or ["*"]
    )

    # Include routers
    app.include_router(signals_router)
    app.include_router(advisor_router)
    app.include_router(news_router)

    # Instrumentation (Prometheus Metrics)
    if settings.ENABLE_PROMETHEUS:
        Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    # Static files mounting
    if os.path.exists("static"):
        app.mount("/static", StaticFiles(directory="static"), name="static")

    # Serve dashboard at root
    @app.get("/", tags=["UI"])
    async def serve_dashboard():
        """Serve the research analyst dashboard"""
        dashboard_path = os.path.join("static", "index.html")
        if os.path.exists(dashboard_path):
            return FileResponse(dashboard_path)
        return {"message": "Dashboard not found. Run with static files correctly mounted."}

    # Add error handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.detail,
                "status_code": exc.status_code,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request, exc):
        logger.error(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "status_code": 500,
            },
        )

    # Health check endpoint
    @app.get("/health", tags=["Health"])
    async def health_check():
        """Health check endpoint"""
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    # API Root
    @app.get("/api", tags=["Root"])
    async def api_root():
        """API root endpoint"""
        return {
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "endpoints": {
                "signals": "/api/v1/signals",
                "advisor": "/api/v1/advisor",
                "news": "/api/v1/news",
                "health": "/health",
                "docs": "/api/docs",
            }
        }

    async def pull_ollama_model():
        """Pull the required Ollama model if not available"""
        if settings.LLM_PROVIDER != "ollama":
            return
        
        try:
            model = getattr(settings, f"{settings.LLM_PROVIDER.upper()}_MODEL", "mistral")
            base_url = settings.OLLAMA_BASE_URL
            
            logger.info(f"Checking Ollama availability at {base_url}...")
            
            # Check if model is available with timeout
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get(f"{base_url}/api/tags", timeout=10.0)
                    if response.status_code == 200:
                        models = response.json().get("models", [])
                        model_names = [m["name"] for m in models]
                        if model in model_names or f"{model}:latest" in model_names:
                            logger.info(f"✓ Ollama model '{model}' already available")
                            return
                    
                    # Pull the model
                    logger.info(f"Pulling Ollama model '{model}' (this may take a few minutes)...")
                    response = await client.post(
                        f"{base_url}/api/pull",
                        json={"name": model},
                        timeout=300.0  # 5 minutes timeout
                    )
                    if response.status_code == 200:
                        logger.info(f"✓ Successfully pulled Ollama model '{model}'")
                    else:
                        logger.warning(f"Failed to pull Ollama model: {response.text}")
            except httpx.ConnectError:
                logger.error(f"✗ Cannot connect to Ollama at {base_url}. Make sure Ollama is running.")
                logger.info("  Continue without Ollama. Run: ollama serve")
            except httpx.TimeoutException:
                logger.error(f"✗ Ollama connection timeout at {base_url}")
                logger.info("  Ollama may be slow to respond. Check its status.")
        except Exception as e:
            logger.error(f"Error checking Ollama: {str(e)}")

    @app.on_event("startup")
    async def startup_event():
        """Run tasks on startup"""
        logger.info("=" * 60)
        logger.info("Starting Crypto Trading Signal Server")
        logger.info("=" * 60)
        
        # Validate critical environment variables
        logger.info("Validating configuration...")
        logger.info("CoinDCX margin currencies: %s", settings.coindcx_margin_currencies_list)
        from src.data.data_fetcher import DataFetcher
        _fetcher = DataFetcher()
        if await _fetcher.test_connection():
            logger.info("✓ CoinDCX public API reachable")
        else:
            logger.warning("⚠ CoinDCX API health check failed")
        await _fetcher.close()
        if settings.JWT_SECRET_KEY == "your-secret-key-change-in-production":
            logger.error("✗ JWT_SECRET_KEY is still default - MUST be changed in production!")
        
        logger.info("Testing MongoDB connection...")
        from src.database.db import test_connection
        db_ok = await test_connection()
        if not db_ok:
            logger.error("✗ Cannot connect to MongoDB - check MONGODB_URI configuration")
            raise RuntimeError("MongoDB is required for Crypto Bot startup")

        logger.info("Initializing MongoDB indexes...")
        try:
            await init_db()
            logger.info("✓ MongoDB initialized")
        except Exception as e:
            logger.error(f"✗ Database initialization failed: {str(e)}")
            raise
        
        # Pull Ollama model if using Ollama
        if settings.LLM_PROVIDER == "ollama":
            await pull_ollama_model()
        else:
            logger.info(f"Using LLM provider: {settings.LLM_PROVIDER}")
        
        if settings.ENABLE_ADVISOR_SCANNER and settings.ENABLE_BACKGROUND_SCANNER:
            logger.info("Starting CoinDCX advisor background scanner...")
            asyncio.create_task(advisor_market_scanner())
        elif settings.ENABLE_BACKGROUND_SCANNER:
            logger.info("Starting legacy Planitt background scanner...")
            asyncio.create_task(market_scanner())
        else:
            logger.info("Background scanner disabled by ENABLE_BACKGROUND_SCANNER=false")
        logger.info("✓ Application startup complete")

    @app.on_event("shutdown")
    async def shutdown_handler():
        """Clean up on shutdown"""
        logger.info("Shutting down application...")
        shutdown_event.set()
        await shutdown_planitt_processor()
        await shutdown_advisor_processor()
        logger.info("Application shutdown complete.")

    async def advisor_market_scanner():
        """Periodic CoinDCX advisor scan (SOP weekly cap enforced in processor)."""
        processor = await get_advisor_processor()
        scan_interval = max(settings.SCAN_INTERVAL, 900)
        while not shutdown_event.is_set():
            try:
                logger.info("Advisor scanner: starting universe scan...")
                results = await processor.scan_universe()
                published = sum(1 for r in results if r.get("ok"))
                logger.info("Advisor scanner: published %d signals", published)
            except Exception as exc:
                logger.exception("Advisor scanner error: %s", exc)
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=scan_interval)
            except asyncio.TimeoutError:
                pass

    async def market_scanner():
        """Periodically scan market for signals and AI opportunities"""
        processor = await get_planitt_processor()
        # If PLANITT_SCAN_TIMEFRAMES is set, scan all provided timeframes each cycle.
        configured_tfs = [
            tf.strip() for tf in settings.PLANITT_SCAN_TIMEFRAMES_RAW.split(",") if tf.strip()
        ]
        scan_timeframes = configured_tfs if configured_tfs else [settings.DEFAULT_TIMEFRAME]
        while not shutdown_event.is_set():
            try:
                logger.info(f"Background scanner: Initiating market-wide scan for TFs={scan_timeframes} ...")
                
                # Parallel scan across symbols
                for symbol in settings.SUPPORTED_CRYPTOS:
                    if shutdown_event.is_set():
                        break

                    for timeframe in scan_timeframes:
                        correlation_id = f"planitt-scan-{int(datetime.utcnow().timestamp() * 1000)}-{symbol}-{timeframe}"
                        try:
                            await processor.generate_and_forward(
                                symbol=symbol,
                                timeframe=timeframe,
                                correlation_id=correlation_id,
                            )
                        except Exception as inner_e:
                            logger.exception(
                                "Background scanner symbol/timeframe failed: symbol=%s timeframe=%s error=%s",
                                symbol,
                                timeframe,
                                str(inner_e),
                            )
                
                logger.info(f"Background scanner: Completed scan. Waiting {settings.SCAN_INTERVAL}s...")
            except Exception as e:
                logger.error(f"Background scanner error: {str(e)}")
            
            # Wait for interval or shutdown
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=settings.SCAN_INTERVAL)
            except asyncio.TimeoutError:
                pass

    logger.info(f"FastAPI application '{settings.APP_NAME}' created successfully")
    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    logger.info(f"Starting server on {settings.SERVER_HOST}:{settings.SERVER_PORT}")
    uvicorn.run(
        app,
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        workers=settings.WORKERS,
        log_level=settings.LOG_LEVEL.lower(),
    )
