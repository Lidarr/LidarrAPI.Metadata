"""
Logging configuration settings using pydantic-settings.
This provides a modern, type-safe way to manage logging configuration.
"""
import logging
from enum import Enum

from pydantic_settings import BaseSettings


class LogLevel(str, Enum):
    """Supported log levels"""
    CRITICAL = "critical"
    ERROR = "error" 
    WARNING = "warning"
    WARN = "warn"  # Alias for warning
    INFO = "info"
    DEBUG = "debug"


class LogFormat(str, Enum):
    """Supported log formats"""
    JSON = "json"
    TEXT = "text"


class LoggingSettings(BaseSettings):
    """
    Logging configuration settings.
    
    These can be overridden via environment variables:
    - LOG_LEVEL: Set log level (debug, info, warning, error, critical)
    - LOG_FORMAT: Set log format (json, text)
    """
    
    log_level: LogLevel = LogLevel.INFO
    log_format: LogFormat = LogFormat.JSON
    
    class Config:
        env_prefix = ""  # No prefix, use direct env var names
        case_sensitive = False  # Allow LOG_LEVEL or log_level
        
    def to_python_log_level(self) -> int:
        """Convert LogLevel enum to Python logging level constant"""
        level_map = {
            LogLevel.CRITICAL: logging.CRITICAL,
            LogLevel.ERROR: logging.ERROR,
            LogLevel.WARNING: logging.WARNING,
            LogLevel.WARN: logging.WARNING,  # Alias
            LogLevel.INFO: logging.INFO,
            LogLevel.DEBUG: logging.DEBUG,
        }
        return level_map[self.log_level]
    
    def is_debug(self) -> bool:
        """Check if debug logging is enabled"""
        return self.log_level == LogLevel.DEBUG
    
    def use_json_format(self) -> bool:
        """Check if JSON format should be used"""
        return self.log_format == LogFormat.JSON


# Global settings instance
_logging_settings = None


def get_logging_settings() -> LoggingSettings:
    """Get the global logging settings instance"""
    global _logging_settings
    if _logging_settings is None:
        _logging_settings = LoggingSettings()
    return _logging_settings