import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

import lidarrmetadata
from lidarrmetadata import config, util, provider, api
from lidarrmetadata.logging_config import configure_structlog, get_logger
from lidarrmetadata.logging_settings import get_logging_settings
from lidarrmetadata.async_tracker import operation_tracker
from lidarrmetadata.circuit_breaker import circuit_breakers
from lidarrmetadata.models import (
    ErrorResponse, HealthResponse, AsyncHealthResponse, 
    CleanupResponse, InfoResponse, HangingOperationDetail, 
    FailedOperationDetail, CircuitBreakerInfo, CircuitBreakerStats, 
    CircuitBreakerConfig
)
import asyncio
from fastapi import HTTPException, Request, status

# Get configuration first
CONFIG = config.get_config()

# Configure structured logging with new settings
logging_settings = get_logging_settings()
configure_structlog(settings=logging_settings)

# Get structured logger
logger = get_logger(__name__)
logger.info("FastAPI app initializing")

# Initialize FastAPI app
fastapi_app = FastAPI(
    title="Lidarr Metadata API",
    description="FastAPI-powered metadata API for Lidarr",
    version=lidarrmetadata.__version__,
    docs_url="/docs" if CONFIG.DEBUG else None,
    redoc_url="/redoc" if CONFIG.DEBUG else None
)

# Configure CORS
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure Sentry for FastAPI
if CONFIG.SENTRY_DSN:
    if CONFIG.SENTRY_REDIS_HOST is not None:
        processor = util.SentryRedisTtlProcessor(
            redis_host=CONFIG.SENTRY_REDIS_HOST,
            redis_port=CONFIG.SENTRY_REDIS_PORT,
            ttl=CONFIG.SENTRY_TTL
        )
    else:
        processor = util.SentryTtlProcessor(ttl=CONFIG.SENTRY_TTL)

    sentry_sdk.init(
        dsn=CONFIG.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        release=f"lidarr-metadata-{lidarrmetadata.__version__}",
        before_send=processor.create_event,
        send_default_pii=True
    )

# Basic health check endpoint
@fastapi_app.get("/health")
async def health_check() -> HealthResponse:
    """Health check endpoint for FastAPI"""
    return HealthResponse(status="healthy", framework="fastapi")

# Async operations health check endpoint
@fastapi_app.get("/health/async")
async def async_health_check() -> AsyncHealthResponse:
    """
    Health check endpoint showing async operation status and hanging operations.
    Useful for monitoring and debugging hanging async calls.
    """
    status = operation_tracker.get_status()
    circuit_stats = circuit_breakers.get_all_stats()
    
    # Convert hanging details to structured models
    hanging_details = [
        HangingOperationDetail(
            name=detail["name"],
            running_time=detail["running_time"],
            timeout=detail["timeout"],
            context=detail["context"]
        )
        for detail in status["hanging_details"]
    ]
    
    # Convert recent failures to structured models  
    recent_failures = [
        FailedOperationDetail(
            name=failure["name"],
            duration=failure.get("duration"),
            success=failure["success"],
            context=failure["context"]
        )
        for failure in status["recent_failures"]
    ]
    
    return AsyncHealthResponse(
        healthy=status["hanging_operations"] == 0,
        active_operations=status["active_operations"],
        hanging_operations=status["hanging_operations"],
        total_recent_operations=len(operation_tracker.completed_operations),
        framework="fastapi",
        hanging_details=hanging_details,
        recent_failures=recent_failures,
        circuit_breakers=circuit_stats
    )

# Manual cleanup endpoint for hanging operations
@fastapi_app.post("/health/async/cleanup")
async def manual_cleanup_hanging_operations() -> CleanupResponse:
    """
    Manually trigger cleanup of hanging operations.
    Useful for debugging and emergency cleanup.
    """
    cleaned_count = await operation_tracker.cleanup_hanging_operations()
    return CleanupResponse(
        cleaned_operations=cleaned_count,
        message=f"Cleaned up {cleaned_count} hanging operations"
    )

# Background task for cleaning up hanging operations
async def cleanup_hanging_operations_task():
    """Background task to cleanup operations that have been hanging too long"""
    while True:
        try:
            await asyncio.sleep(30)  # Check every 30 seconds
            cleaned_count = await operation_tracker.cleanup_hanging_operations()
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} hanging operations")
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")

# Start the cleanup task
@fastapi_app.on_event("startup")
async def startup_event():
    """Start background tasks when FastAPI starts"""
    asyncio.create_task(cleanup_hanging_operations_task())
    logger.info("Started hanging operations cleanup task")

# Exception handlers for proper HTTP status codes
@fastapi_app.exception_handler(api.ArtistNotFoundException)
async def artist_not_found_handler(request: Request, exc: api.ArtistNotFoundException):
    """Handle artist not found exceptions with 404 status"""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ErrorResponse(error="Artist not found", detail=str(exc)).dict()
    )

@fastapi_app.exception_handler(api.ReleaseGroupNotFoundException)
async def album_not_found_handler(request: Request, exc: api.ReleaseGroupNotFoundException):
    """Handle album not found exceptions with 404 status"""
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=ErrorResponse(error="Album not found", detail=str(exc)).dict()
    )

# Root endpoint - migrated from Quart
@fastapi_app.get("/")
async def default_route() -> InfoResponse:
    """
    Default route with API information
    FastAPI version of the root endpoint
    """
    vintage_providers = provider.get_providers_implementing(
        provider.DataVintageMixin)
    
    # Get data vintage from first provider
    data = None
    if vintage_providers:
        try:
            data = await vintage_providers[0].data_vintage()
        except Exception as e:
            logger.warning(f"Failed to get data vintage: {e}")
            data = None

    return InfoResponse(
        branch=os.getenv('GIT_BRANCH'),
        commit=os.getenv('COMMIT_HASH'),
        version=lidarrmetadata.__version__,
        replication_date=data
    )