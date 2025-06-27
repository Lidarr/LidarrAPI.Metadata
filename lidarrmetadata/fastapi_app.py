import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

import lidarrmetadata
from lidarrmetadata import config, util, provider
from lidarrmetadata.logging_config import configure_structlog, get_logger

# Get configuration first
CONFIG = config.get_config()

# Configure structured logging
configure_structlog(
    debug=CONFIG.DEBUG,
    json_logs=not CONFIG.DEBUG,  # Use JSON in production, human-readable in debug
)

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