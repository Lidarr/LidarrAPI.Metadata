import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

import lidarrmetadata
from lidarrmetadata import config, util

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.INFO)
logger.info('Have FastAPI logger')

# Get configuration
CONFIG = config.get_config()

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
        integrations=[FastApiIntegration(auto_enabling_integrations=False)],
        release=f"lidarr-metadata-{lidarrmetadata.__version__}",
        before_send=processor.create_event,
        send_default_pii=True
    )

# Basic health check endpoint
@fastapi_app.get("/health")
async def health_check():
    """Health check endpoint for FastAPI"""
    return {"status": "healthy", "framework": "fastapi"}