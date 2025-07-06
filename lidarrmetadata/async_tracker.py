"""
Async operation tracking for better visibility and debugging of hanging operations.
"""
import asyncio
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Dict, List, Any, Optional

from lidarrmetadata.logging_config import get_logger

logger = get_logger(__name__)

@dataclass
class AsyncOperation:
    name: str
    start_time: float
    timeout: float
    task_id: str
    context: Dict[str, Any]
    success: Optional[bool] = None
    duration: Optional[float] = None

class AsyncOperationTracker:
    """Track async operations to identify hanging calls and failures"""
    
    def __init__(self):
        self.active_operations: Dict[str, AsyncOperation] = {}
        self.completed_operations: List[AsyncOperation] = []
        self.max_history = 100
    
    def add_operation(self, name: str, timeout: float, **context) -> str:
        """Start tracking an async operation"""
        current_task = asyncio.current_task()
        task_id = f"{name}_{time.time()}_{id(current_task) if current_task else 'no_task'}"
        
        operation = AsyncOperation(
            name=name,
            start_time=time.time(),
            timeout=timeout,
            task_id=task_id,
            context=context
        )
        self.active_operations[task_id] = operation
        
        logger.debug(f"Started tracking operation: {name}", extra={
            'task_id': task_id,
            'timeout': timeout,
            **context
        })
        return task_id
    
    def complete_operation(self, task_id: str, success: bool = True):
        """Mark an operation as completed"""
        if task_id in self.active_operations:
            op = self.active_operations.pop(task_id)
            op.success = success
            op.duration = time.time() - op.start_time
            
            self.completed_operations.append(op)
            if len(self.completed_operations) > self.max_history:
                self.completed_operations.pop(0)
            
            log_level = logger.debug if success else logger.warning
            log_level(f"Completed operation: {op.name}", extra={
                'task_id': task_id,
                'duration': op.duration,
                'success': success
            })
    
    def get_hanging_operations(self) -> List[AsyncOperation]:
        """Get operations that have been running longer than their timeout"""
        current_time = time.time()
        hanging = []
        for op in self.active_operations.values():
            if current_time - op.start_time > op.timeout:
                hanging.append(op)
        return hanging
    
    async def cleanup_hanging_operations(self):
        """Force cleanup operations that have been hanging for too long"""
        current_time = time.time()
        cleanup_threshold = 30  # Force cleanup after 30 seconds past timeout
        
        to_cleanup = []
        for task_id, op in list(self.active_operations.items()):
            time_past_timeout = current_time - op.start_time - op.timeout
            if time_past_timeout > cleanup_threshold:
                to_cleanup.append((task_id, op, time_past_timeout))
        
        for task_id, op, time_past_timeout in to_cleanup:
            logger.warning(f"Force cleaning up hanging operation: {op.name}", extra={
                'task_id': task_id,
                'time_past_timeout': time_past_timeout,
                'operation': op.name,
                **op.context
            })
            self.complete_operation(task_id, success=False)
        
        return len(to_cleanup)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current status of all async operations"""
        hanging_ops = self.get_hanging_operations()
        
        return {
            'active_operations': len(self.active_operations),
            'hanging_operations': len(hanging_ops),
            'hanging_details': [
                {
                    'name': op.name,
                    'running_time': time.time() - op.start_time,
                    'timeout': op.timeout,
                    'context': op.context
                }
                for op in hanging_ops
            ],
            'recent_failures': [
                {
                    'name': op.name,
                    'duration': op.duration,
                    'success': op.success,
                    'context': op.context
                }
                for op in self.completed_operations[-10:]
                if op.success is False
            ]
        }

# Global tracker instance
operation_tracker = AsyncOperationTracker()

@asynccontextmanager
async def track_async_operation(name: str, timeout: float = 10, **context):
    """
    Context manager to track async operations for debugging hanging calls.
    
    Usage:
        async with track_async_operation("get_artist_info", timeout=10, mbid=mbid):
            result = await some_async_call()
    """
    task_id = operation_tracker.add_operation(name, timeout, **context)
    
    try:
        yield task_id
        operation_tracker.complete_operation(task_id, success=True)
    except Exception as e:
        operation_tracker.complete_operation(task_id, success=False)
        logger.error(f"Async operation failed: {name}", extra={
            'task_id': task_id,
            'error': str(e),
            'error_type': type(e).__name__,
            **context
        })
        raise

async def safe_async_call(
    coro,
    timeout: float = 10,
    operation_name: str = "unknown_operation",
    context: Optional[Dict] = None
):
    """
    Wrapper for individual async calls with timeout and tracking.
    
    Args:
        coro: The coroutine to execute
        timeout: Timeout in seconds
        operation_name: Name for logging and tracking
        context: Additional context for logging
    """
    context = context or {}
    
    async with track_async_operation(operation_name, timeout, **context):
        try:
            result = await asyncio.wait_for(coro, timeout=timeout)
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Operation {operation_name} timed out after {timeout}s", extra={
                'operation': operation_name,
                'timeout': timeout,
                **context
            })
            raise
        except Exception as e:
            logger.error(f"Operation {operation_name} failed: {e}", extra={
                'operation': operation_name,
                'error': str(e),
                'error_type': type(e).__name__,
                **context
            })
            raise