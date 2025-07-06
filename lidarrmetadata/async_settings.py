"""
Async operation timeout settings using pydantic-settings.
This provides a modern, type-safe way to manage async operation timeouts.
"""
from pydantic_settings import BaseSettings


class AsyncTimeoutSettings(BaseSettings):
    """
    Async operation timeout configuration.
    
    These can be overridden via environment variables with ASYNC_TIMEOUT_ prefix:
    - ASYNC_TIMEOUT_ARTIST_INFO: Timeout for artist info operations (default: 15s)
    - ASYNC_TIMEOUT_ALBUM_INFO: Timeout for album info operations (default: 20s)
    - ASYNC_TIMEOUT_SEARCH_ALL: Timeout for combined search operations (default: 20s)
    - ASYNC_TIMEOUT_DATABASE_QUERY: Timeout for database queries (default: 10s)
    - ASYNC_TIMEOUT_DEFAULT: Default timeout for unspecified operations (default: 10s)
    """
    
    # Core API operations
    artist_info: int = 15           # Getting artist info + albums
    album_info: int = 20            # Getting album info (includes database queries)
    
    # Search operations
    search_all: int = 20            # Combined artist + album search
    search_artist: int = 15         # Artist search only
    search_album: int = 15          # Album search only
    fingerprint_search: int = 15    # Fingerprint-based album search
    
    # Data fetching operations
    release_group_artists: int = 15 # Getting artists for release groups
    artist_images: int = 10         # Fetching artist images
    
    # Infrastructure operations
    database_query: int = 10        # Database operations
    external_api: int = 10          # External API calls (Spotify, Last.fm, etc.)
    
    # Default fallback
    default: int = 10               # Default timeout for unspecified operations
    
    class Config:
        env_prefix = "ASYNC_TIMEOUT_"
        case_sensitive = False
    
    def get_timeout(self, operation_name: str) -> int:
        """
        Get timeout for a specific operation.
        
        Args:
            operation_name: Name of the operation (e.g., 'artist_info', 'database_query')
            
        Returns:
            Timeout in seconds for the operation
        """
        # Convert operation name to attribute name (e.g., 'artist-info' -> 'artist_info')
        attr_name = operation_name.replace('-', '_').replace(' ', '_').lower()
        
        return getattr(self, attr_name, self.default)


# Global settings instance
_async_timeout_settings = None


def get_async_timeout_settings() -> AsyncTimeoutSettings:
    """Get the global async timeout settings instance"""
    global _async_timeout_settings
    if _async_timeout_settings is None:
        _async_timeout_settings = AsyncTimeoutSettings()
    return _async_timeout_settings


def get_timeout(operation_name: str) -> int:
    """
    Convenience function to get timeout for an operation.
    
    Args:
        operation_name: Name of the operation
        
    Returns:
        Timeout in seconds
    """
    return get_async_timeout_settings().get_timeout(operation_name)