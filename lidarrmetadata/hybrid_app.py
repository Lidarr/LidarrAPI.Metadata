"""
Hybrid application that routes requests between Quart and FastAPI based on feature flags.
This allows for gradual migration of endpoints from Quart to FastAPI.
"""
import os
from typing import Dict, Set

from quart import Quart
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware

from lidarrmetadata.app import app as quart_app
from lidarrmetadata.fastapi_app import fastapi_app
from lidarrmetadata import config
from lidarrmetadata.logging_config import get_logger

logger = get_logger(__name__)

# Configuration for which endpoints should use FastAPI
# Set environment variable FASTAPI_ENDPOINTS to comma-separated list of endpoints
# Example: FASTAPI_ENDPOINTS="/health,/,/recent/artist"
FASTAPI_ENDPOINTS = set()
if os.environ.get('FASTAPI_ENDPOINTS'):
    FASTAPI_ENDPOINTS = set(os.environ.get('FASTAPI_ENDPOINTS').split(','))

# For development, you can also configure this programmatically
FASTAPI_ENABLED_ENDPOINTS: Set[str] = {
    '/health',  # Health check endpoint (FastAPI only)
    '/health/async',  # Async health check endpoint (FastAPI only)
    '/',        # Root endpoint - migrated to FastAPI
    # Add more endpoints here as we migrate them
}

# Merge environment configuration with programmatic configuration
FASTAPI_ENABLED_ENDPOINTS.update(FASTAPI_ENDPOINTS)

logger.info(f"FastAPI enabled for endpoints: {FASTAPI_ENABLED_ENDPOINTS}")

class HybridApplication:
    """
    Hybrid application that routes between Quart and FastAPI apps.
    """
    
    def __init__(self, quart_app: Quart, fastapi_app: FastAPI):
        self.quart_app = quart_app
        self.fastapi_app = fastapi_app
        self.fastapi_enabled_endpoints = FASTAPI_ENABLED_ENDPOINTS.copy()
    
    def should_use_fastapi(self, path: str) -> bool:
        """
        Determine if a request path should be handled by FastAPI.
        """
        # Exact path match
        if path in self.fastapi_enabled_endpoints:
            return True
        
        # Check for path patterns (for parameterized routes)
        for pattern in self.fastapi_enabled_endpoints:
            if pattern.endswith('*') and path.startswith(pattern[:-1]):
                return True
        
        return False
    
    def enable_fastapi_for_endpoint(self, endpoint: str):
        """
        Enable FastAPI for a specific endpoint (for runtime switching).
        """
        self.fastapi_enabled_endpoints.add(endpoint)
        logger.info(f"Enabled FastAPI for endpoint: {endpoint}")
    
    def disable_fastapi_for_endpoint(self, endpoint: str):
        """
        Disable FastAPI for a specific endpoint (rollback to Quart).
        """
        self.fastapi_enabled_endpoints.discard(endpoint)
        logger.info(f"Disabled FastAPI for endpoint: {endpoint} (using Quart)")

# Create the hybrid application instance
hybrid_app = HybridApplication(quart_app, fastapi_app)

# For now, we'll create a simple wrapper that directs traffic
# In production, you'd use a proper ASGI application or reverse proxy
async def route_request(scope, receive, send):
    """
    ASGI application that routes requests between Quart and FastAPI.
    """
    if scope['type'] == 'http':
        path = scope['path']
        
        if hybrid_app.should_use_fastapi(path):
            # Route to FastAPI
            await fastapi_app(scope, receive, send)
        else:
            # Route to Quart (need to convert ASGI to WSGI for Quart)
            # This is a simplified approach - in production you'd want proper ASGI handling
            await quart_app(scope, receive, send)
    else:
        # Handle websockets and other protocols with Quart
        await quart_app(scope, receive, send)

# Export the main application
app = route_request