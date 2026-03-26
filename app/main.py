# ===========================================
# FastAPI Application Entry Point
# ===========================================
"""
Emotion Management and Smart Cushion Intervention System - Main Application

Main features:
- FastAPI application configuration
- CORS middleware
- Route registration
- Exception handling
- Startup/shutdown events
"""

import sys
from contextlib import asynccontextmanager
from typing import Any, Dict

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.router import api_router
from app.config import settings
from app.database import close_db, init_db, test_connection
from app.schemas import BaseResponse


# ===========================================
# Logging Configuration
# ===========================================

def setup_logging():
    """Configure Loguru logging"""
    # Remove default handler
    logger.remove()
    
    # Add console handler
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="DEBUG" if settings.DEBUG else "INFO",
        colorize=True,
    )
    
    # Add file handler (production)
    if not settings.DEBUG:
        logger.add(
            "logs/app_{time:YYYY-MM-DD}.log",
            rotation="00:00",
            retention="30 days",
            level="INFO",
            encoding="utf-8",
        )


# ===========================================
# Application Lifecycle
# ===========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle management
    
    Startup:
    - Configure logging
    - Test database connection
    - Initialize Redis connection
    - Start background tasks
    
    Shutdown:
    - Close database connection
    - Close Redis connection
    """
    # Startup
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    
    # Test database connection
    if await test_connection():
        logger.info("Database connection successful")
    else:
        logger.warning("Database connection failed, please check configuration")
    
    # Initialize Redis connection
    from app.services.redis_client import redis_client
    try:
        await redis_client.connect()
        logger.info("Redis connection successful")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
    
    # Start data persistence background task
    from app.services.data_persistence_service import get_persistence_service
    try:
        persistence_service = await get_persistence_service(redis_client)
        await persistence_service.start_background_task()
        logger.info("Data persistence task started")
    except Exception as e:
        logger.warning(f"Failed to start persistence task: {e}")
    
    # Initialize database tables in development mode
    if settings.DEBUG:
        try:
            await init_db()
        except Exception as e:
            logger.warning(f"Database table initialization warning: {e}")
    
    # Print registered routes
    logger.info("Registered routes:")
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            methods = ", ".join(route.methods)
            logger.info(f"  {methods:10} {route.path}")
    
    yield
    
    # Shutdown
    # Stop persistence task
    from app.services.data_persistence_service import data_persistence_service
    if data_persistence_service:
        await data_persistence_service.stop_background_task()
    
    # Close Redis connection
    await redis_client.disconnect()
    
    # Close database connection
    await close_db()
    logger.info("Application shutdown complete")


# ===========================================
# Create FastAPI Application
# ===========================================

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## Emotion Management and Smart Cushion Intervention System API

Smart cushion hardware collects user heart rate, breathing and other physiological data,
processed and analyzed through this system.

### Main Features
- Multi-tenant SaaS architecture
- Smart cushion data collection and processing
- HRV, stress index and other advanced metrics calculation
- AI large model health report generation

### Merchant Types
- Traditional Chinese Medicine Clinic (chinese_medicine)
- Hotel (hotel)
- Wellness Center (wellness_center)

### Webhook Endpoints
- POST /api/v1/webhook/realtime-data - Receive real-time device data
- POST /api/v1/webhook/report - Receive sleep reports

### Real-time Data Endpoints
- GET /api/v1/realtime/{device_code}/latest - Get latest data
- GET /api/v1/realtime/{device_code}/stream - SSE real-time stream
- POST /api/v1/realtime/{device_code}/start - Start measurement
- POST /api/v1/realtime/{device_code}/stop - End measurement
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ===========================================
# CORS Middleware
# ===========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================
# Exception Handlers
# ===========================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Global exception handler
    
    Catches all unhandled exceptions and returns standardized error response
    """
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder({
            "code": 500,
            "msg": "Internal server error" if not settings.DEBUG else str(exc),
            "data": None
        })
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """
    ValueError exception handler
    
    Handles data validation errors
    """
    logger.warning(f"Data validation error: {exc}")
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder({
            "code": 400,
            "msg": str(exc),
            "data": None
        })
    )


# ===========================================
# Health Check Endpoint
# ===========================================

@app.get("/health", tags=["Health Check"], summary="Health check")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint
    
    Used for monitoring, load balancing, etc.
    
    Returns:
        Health status information
    """
    # Check Redis connection
    from app.services.redis_client import redis_client
    redis_status = "connected" if redis_client._client else "disconnected"
    
    return {
        "code": 200,
        "msg": "healthy",
        "data": {
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "status": "running",
            "redis": redis_status
        }
    }


@app.get("/", tags=["Root"], summary="API information")
async def root() -> Dict[str, Any]:
    """
    Root path
    
    Returns basic API information and documentation links
    
    Returns:
        API information
    """
    return {
        "code": 200,
        "msg": "success",
        "data": {
            "app_name": settings.APP_NAME,
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json"
        }
    }


# ===========================================
# Register Routes
# ===========================================

app.include_router(api_router, prefix="/api/v1")


# ===========================================
# Development Server Entry
# ===========================================

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="debug" if settings.DEBUG else "info",
    )
