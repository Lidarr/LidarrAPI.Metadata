import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

import lidarrmetadata
from lidarrmetadata import config, util, provider
from lidarrmetadata.logging_config import configure_structlog, get_logger
from lidarrmetadata.logging_settings import get_logging_settings
from lidarrmetadata.async_tracker import operation_tracker
from lidarrmetadata.circuit_breaker import circuit_breakers

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
async def health_check():
    """Health check endpoint for FastAPI"""
    return {"status": "healthy", "framework": "fastapi"}

# Async operations health check endpoint
@fastapi_app.get("/health/async")
async def async_health_check():
    """
    Health check endpoint showing async operation status and hanging operations.
    Useful for monitoring and debugging hanging async calls.
    """
    status = operation_tracker.get_status()
    
    # Add circuit breaker information
    circuit_stats = circuit_breakers.get_all_stats()
    
    # Add some basic health indicators
    status["healthy"] = status["hanging_operations"] == 0
    status["total_recent_operations"] = len(operation_tracker.completed_operations)
    status["framework"] = "fastapi"
    status["circuit_breakers"] = circuit_stats
    
    return status

# Root endpoint - migrated from Quart
@fastapi_app.get("/")
async def default_route():
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

    info = {
        'branch': os.getenv('GIT_BRANCH'),
        'commit': os.getenv('COMMIT_HASH'),
        'version': lidarrmetadata.__version__,
        'replication_date': data
    }
    return info