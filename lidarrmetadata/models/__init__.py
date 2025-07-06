"""
Pydantic models for the Lidarr Metadata API.

Organized by logical domains:
- base: Common models used across the API
- monitoring: Health checks, async operations, circuit breakers
- music: Artist, album, and music-related models
"""

# Import all models for convenience
from .base import ErrorResponse, HealthResponse, InfoResponse
from .monitoring import (
    HangingOperationDetail, FailedOperationDetail, CircuitBreakerStats,
    CircuitBreakerConfig, CircuitBreakerInfo, AsyncHealthResponse, CleanupResponse
)
from .music import ArtistImage, Album, Artist, ArtistFilterParams

__all__ = [
    # Base models
    "ErrorResponse", "HealthResponse", "InfoResponse",
    # Monitoring models
    "HangingOperationDetail", "FailedOperationDetail", "CircuitBreakerStats",
    "CircuitBreakerConfig", "CircuitBreakerInfo", "AsyncHealthResponse", "CleanupResponse",
    # Music models
    "ArtistImage", "Album", "Artist", "ArtistFilterParams"
]