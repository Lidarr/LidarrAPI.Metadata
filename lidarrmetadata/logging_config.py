"""
Structured logging configuration using structlog.
Based on structlog documentation best practices.
"""
import logging
import sys
from typing import Any

import structlog


def configure_structlog(
    debug: bool = False,
    json_logs: bool = True,
) -> None:
    """
    Configure structlog with integration to stdlib logging.
    
    Args:
        debug: Enable debug level logging
        json_logs: Use JSON formatting for structured logs
    """
    # Configure timestamping and log level
    timestamper = structlog.processors.TimeStamper(fmt="iso")
    
    if json_logs:
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
        level=logging.DEBUG if debug else logging.INFO,
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