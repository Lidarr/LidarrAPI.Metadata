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
    FailedOperationDetail, Artist
)
from lidarrmetadata.db_monitor import db_monitor
from lidarrmetadata.async_settings import get_timeout
import asyncio
from fastapi import HTTPException, Request, status, Query, Path
from fastapi.responses import Response
import uuid
from typing import Optional, Dict, Any
import json

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

# Helper function for UUID validation
def validate_uuid(mbid: str) -> None:
    """Validate MusicBrainz UUID format"""
    try:
        uuid.UUID(mbid, version=4)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ErrorResponse(error="Invalid UUID", detail=f"'{mbid}' is not a valid UUID").dict()
        )

# Artist endpoint - migrated from Quart
@fastapi_app.get("/artist/{mbid}")
async def get_artist_info(
    mbid: str = Path(..., description="MusicBrainz Artist ID"),
    prim_types: Optional[str] = Query(None, alias="primTypes", description="Primary release group types (pipe-separated)"),
    sec_types: Optional[str] = Query(None, alias="secTypes", description="Secondary release group types (pipe-separated)"),
    release_statuses: Optional[str] = Query(None, alias="releaseStatuses", description="Release statuses (pipe-separated)"),
    response: Response = None
) -> Artist:
    """
    Get artist information by MusicBrainz ID.
    
    Returns detailed artist information including albums, with optional filtering
    by release group types and statuses.
    """
    # Validate UUID format
    validate_uuid(mbid)
    
    # Use utility function for timeout handling
    from lidarrmetadata.api import execute_async_tasks_with_timeout
    
    artist_coroutine = api.get_artist_info(mbid)
    albums_coroutine = api.get_artist_albums(mbid)
    
    results, valid_indices = await execute_async_tasks_with_timeout(
        [artist_coroutine, albums_coroutine],
        timeout=get_timeout("artist_info"),
        task_name="artist_info",
        default_result=(None, provider.utcnow())
    )
    
    # Extract artist info (first task)
    if 0 in valid_indices and results[0] is not None:
        artist_data, expiry = results[0]
    else:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=ErrorResponse(error="Artist info request timed out or failed").dict()
        )
    
    # Extract albums (second task)
    if 1 in valid_indices and results[1] is not None:
        albums = results[1]
    else:
        albums = []
    
    # Filter release group types (legacy compatibility)
    if prim_types:
        primary_types = prim_types.split('|')
        albums = [album for album in albums if album.get('Type') in primary_types]
    
    if sec_types:
        secondary_types = set(sec_types.split('|'))
        albums = [
            album for album in albums 
            if (album.get('SecondaryTypes', []) == [] and 'Studio' in secondary_types)
            or secondary_types.intersection(album.get('SecondaryTypes', []))
        ]
    
    if release_statuses:
        release_status_set = set(release_statuses.split('|'))
        albums = [
            album for album in albums 
            if release_status_set.intersection(album.get('ReleaseStatuses', []))
        ]
    
    # Add albums to artist data
    artist_data['Albums'] = albums
    
    # Set cache control headers (FastAPI equivalent of add_cache_control_header)
    if response and expiry:
        from datetime import timedelta
        cache_seconds = int((expiry - provider.utcnow()).total_seconds())
        if cache_seconds > 0:
            response.headers["Cache-Control"] = f"public, s-maxage={cache_seconds}, max-age=0"
            response.headers["Expires"] = (provider.utcnow() - timedelta(days=1)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    
    # Convert to Pydantic model for validation and proper serialization
    return Artist.parse_obj(artist_data)

# Debug endpoints for performance monitoring
@fastapi_app.get("/debug/database")
async def get_database_metrics() -> Dict[str, Any]:
    """
    Get detailed database performance metrics for debugging.
    Shows connection pool status, query performance, and slow queries.
    """
    return db_monitor.get_metrics()

@fastapi_app.get("/debug/artist/{mbid}")
async def debug_artist_performance(
    mbid: str = Path(..., description="MusicBrainz Artist ID"),
    include_db_metrics: bool = Query(True, description="Include database metrics"),
    include_async_status: bool = Query(True, description="Include async operation status")
) -> Dict[str, Any]:
    """
    Debug endpoint for artist performance monitoring.
    
    This endpoint provides detailed debugging information for artist operations
    including database metrics, async operation status, and circuit breaker status.
    Use this to diagnose timeout issues.
    """
    # Validate UUID format
    validate_uuid(mbid)
    
    debug_info = {
        "artist_id": mbid,
        "timestamp": provider.utcnow().isoformat(),
        "timeouts": {
            "artist_info": get_timeout("artist_info"),
            "database_query": get_timeout("database_query"),
            "external_api": get_timeout("external_api"),
            "artist_images": get_timeout("artist_images")
        }
    }
    
    if include_db_metrics:
        debug_info["database_metrics"] = db_monitor.get_metrics()
    
    if include_async_status:
        async_status = operation_tracker.get_status()
        debug_info["async_operations"] = {
            "active_operations": async_status["active_operations"],
            "hanging_operations": async_status["hanging_operations"],
            "hanging_details": async_status["hanging_details"],
            "recent_failures": async_status["recent_failures"][-5:]  # Last 5 failures
        }
        
        # Add circuit breaker status
        debug_info["circuit_breakers"] = circuit_breakers.get_all_stats()
    
    # Add provider information
    artist_providers = provider.get_providers_implementing(provider.ArtistByIdMixin)
    artist_art_providers = provider.get_providers_implementing(provider.ArtistArtworkMixin)
    
    debug_info["providers"] = {
        "artist_providers": [type(p).__name__ for p in artist_providers],
        "artist_art_providers": [type(p).__name__ for p in artist_art_providers]
    }
    
    return debug_info

@fastapi_app.post("/debug/database/reset")
async def reset_database_metrics() -> Dict[str, str]:
    """
    Reset database monitoring metrics (useful for testing).
    """
    db_monitor.reset_metrics()
    return {"message": "Database metrics reset successfully"}

@fastapi_app.get("/debug/operations/hanging")
async def get_hanging_operations() -> Dict[str, Any]:
    """
    Get detailed information about currently hanging operations.
    """
    status = operation_tracker.get_status()
    return {
        "hanging_operations_count": status["hanging_operations"],
        "hanging_details": status["hanging_details"],
        "timestamp": provider.utcnow().isoformat()
    }