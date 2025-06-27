"""
Structured logging configuration using structlog.
Based on structlog documentation best practices with pydantic-settings integration.
"""
import logging
import sys
from typing import Any, Optional

import structlog

from lidarrmetadata.logging_settings import get_logging_settings, LoggingSettings


def configure_structlog(
    settings: Optional[LoggingSettings] = None,
    # Legacy parameters for backward compatibility
    debug: Optional[bool] = None,
    json_logs: Optional[bool] = None,
) -> None:
    """
    Configure structlog with integration to stdlib logging.
    
    Args:
        settings: LoggingSettings instance. If None, will get global settings.
        debug: DEPRECATED - Use LOG_LEVEL=debug instead. Enable debug level logging
        json_logs: DEPRECATED - Use LOG_FORMAT=text instead. Use JSON formatting for structured logs
    """
    # Get settings or use provided ones
    if settings is None:
        settings = get_logging_settings()
    
    # Handle legacy parameters for backward compatibility
    if debug is not None or json_logs is not None:
        # Override settings based on legacy parameters
        if debug is not None:
            log_level = logging.DEBUG if debug else logging.INFO
        else:
            log_level = settings.to_python_log_level()
            
        if json_logs is not None:
            use_json = json_logs
        else:
            use_json = settings.use_json_format()
    else:
        # Use new settings
        log_level = settings.to_python_log_level()
        use_json = settings.use_json_format()
    # Configure timestamping and log level
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    
    if use_json:
        # JSON output for production
        processors = [
            # Filter out logs by level
            structlog.stdlib.filter_by_level,
            # Add logger name, log level, and timestamp
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            timestamper,
            # Add caller info
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            # Format stack info and exceptions
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            # Ensure strings are unicode
            structlog.processors.UnicodeDecoder(),
            # Render as JSON
            structlog.processors.JSONRenderer()
        ]
    else:
        # Human-readable output for development
        processors = [
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            timestamper,
            structlog.processors.CallsiteParameterAdder(
                parameters=[
                    structlog.processors.CallsiteParameter.FILENAME,
                    structlog.processors.CallsiteParameter.FUNC_NAME,
                    structlog.processors.CallsiteParameter.LINENO,
                ]
            ),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # Use colored console output
            structlog.dev.ConsoleRenderer(colors=True)
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def add_context(**kwargs) -> None:
    """
    Add context to all subsequent log messages in this context.
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(**kwargs)


# Convenience function for timing operations
async def log_async_operation(
    logger: structlog.stdlib.BoundLogger,
    operation_name: str,
    func,
    *args,
    **kwargs
) -> Any:
    """
    Log an async operation with timing information.
    
    Args:
        logger: Structlog logger instance
        operation_name: Name of the operation being performed
        func: Async function to execute
        *args: Arguments to pass to func
        **kwargs: Keyword arguments to pass to func
        
    Returns:
        Result of the async function
    """
    import time
    start_time = time.time()
    
    logger.debug(
        "Operation started",
        operation=operation_name,
        args_count=len(args),
        kwargs_keys=list(kwargs.keys())
    )
    
    try:
        result = await func(*args, **kwargs)
        elapsed = time.time() - start_time
        
        logger.info(
            "Operation completed",
            operation=operation_name,
            elapsed_seconds=round(elapsed, 4),
            success=True
        )
        
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        
        logger.error(
            "Operation failed",
            operation=operation_name,
            elapsed_seconds=round(elapsed, 4),
            error=str(e),
            error_type=type(e).__name__,
            success=False
        )
        raise