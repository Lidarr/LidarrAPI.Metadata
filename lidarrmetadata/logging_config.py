"""
Structured logging configuration using structlog.
Integrates with the standard library logging and provides async-aware logging.
"""
import logging
import sys
from typing import Any

import structlog
from structlog.types import Processor


def configure_structlog(
    debug: bool = False,
    json_logs: bool = True,
    include_logger_name: bool = True
) -> None:
    """
    Configure structlog with integration to stdlib logging.
    
    Args:
        debug: Enable debug level logging
        json_logs: Use JSON formatting for structured logs
        include_logger_name: Include logger name in log records
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if debug else logging.INFO,
    )

    # Shared processors for both stdlib and structlog
    shared_processors: list[Processor] = [
        # Add timestamp
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name if include_logger_name else structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if json_logs:
        # JSON formatting for production
        shared_processors.append(structlog.processors.JSONRenderer())
    else:
        # Human-readable formatting for development
        shared_processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Configure structlog
    structlog.configure(
        processors=shared_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog rendering
    handler = logging.StreamHandler()
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=not json_logs) if not json_logs 
        else structlog.processors.JSONRenderer()
    ))
    
    # Update root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


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