"""
Circuit breaker pattern for external service calls to prevent cascading failures.
"""
import time
import asyncio
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass, field
from enum import Enum

from lidarrmetadata.logging_config import get_logger

logger = get_logger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit breaker is open, calls fail fast
    HALF_OPEN = "half_open"  # Testing if service is back

@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5      # Number of failures before opening
    recovery_timeout: int = 60      # Seconds to wait before trying again
    success_threshold: int = 2      # Successes needed to close from half-open
    timeout: float = 10.0           # Default timeout for calls

@dataclass
class CircuitBreakerStats:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeouts: int = 0
    circuit_opens: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None

class CircuitBreaker:
    """
    Circuit breaker implementation for external service calls.
    
    Prevents cascading failures by failing fast when a service is down.
    """
    
    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()
    
    async def call(self, coro_func: Callable, *args, **kwargs):
        """
        Execute a coroutine function through the circuit breaker.
        
        Args:
            coro_func: The async function to call
            *args, **kwargs: Arguments to pass to the function
        """
        async with self._lock:
            self.stats.total_calls += 1
            
            # Check if circuit is open
            if self.state == CircuitState.OPEN:
                if time.time() - self.stats.last_failure_time > self.config.recovery_timeout:
                    logger.info(f"Circuit breaker {self.name} transitioning to HALF_OPEN")
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    logger.warning(f"Circuit breaker {self.name} is OPEN, failing fast")
                    raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is open")
        
        # Execute the call
        try:
            logger.debug(f"Circuit breaker {self.name} executing call")
            result = await asyncio.wait_for(coro_func(*args, **kwargs), timeout=self.config.timeout)
            await self._record_success()
            return result
            
        except asyncio.TimeoutError:
            self.stats.timeouts += 1
            await self._record_failure()
            logger.warning(f"Circuit breaker {self.name} call timed out after {self.config.timeout}s")
            raise
            
        except Exception as e:
            await self._record_failure()
            logger.warning(f"Circuit breaker {self.name} call failed: {e}")
            raise
    
    async def _record_success(self):
        """Record a successful call"""
        async with self._lock:
            self.stats.successful_calls += 1
            self.stats.last_success_time = time.time()
            self.failure_count = 0
            
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    logger.info(f"Circuit breaker {self.name} transitioning to CLOSED")
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
    
    async def _record_failure(self):
        """Record a failed call"""
        async with self._lock:
            self.stats.failed_calls += 1
            self.stats.last_failure_time = time.time()
            self.failure_count += 1
            
            if (self.state == CircuitState.CLOSED and 
                self.failure_count >= self.config.failure_threshold):
                logger.warning(f"Circuit breaker {self.name} opening due to {self.failure_count} failures")
                self.state = CircuitState.OPEN
                self.stats.circuit_opens += 1
            elif self.state == CircuitState.HALF_OPEN:
                logger.warning(f"Circuit breaker {self.name} returning to OPEN from HALF_OPEN")
                self.state = CircuitState.OPEN
                self.success_count = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current circuit breaker statistics"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout
            },
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "timeouts": self.stats.timeouts,
                "circuit_opens": self.stats.circuit_opens,
                "last_failure_time": self.stats.last_failure_time,
                "last_success_time": self.stats.last_success_time,
                "success_rate": (
                    self.stats.successful_calls / self.stats.total_calls 
                    if self.stats.total_calls > 0 else 0
                )
            }
        }

class CircuitBreakerOpenError(Exception):
    """Exception raised when circuit breaker is open"""
    pass

# Global circuit breakers for different services
class CircuitBreakers:
    """Registry of circuit breakers for different services"""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
    
    def get_breaker(self, service_name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
        """Get or create a circuit breaker for a service"""
        if service_name not in self.breakers:
            self.breakers[service_name] = CircuitBreaker(service_name, config)
        return self.breakers[service_name]
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers"""
        return {name: breaker.get_stats() for name, breaker in self.breakers.items()}

# Global instance
circuit_breakers = CircuitBreakers()

# Convenience function for common use cases
async def protected_call(service_name: str, coro_func: Callable, *args, 
                        config: Optional[CircuitBreakerConfig] = None, **kwargs):
    """
    Execute a call through a circuit breaker.
    
    Usage:
        result = await protected_call("spotify", spotify_api.get_artist, artist_id)
    """
    breaker = circuit_breakers.get_breaker(service_name, config)
    return await breaker.call(coro_func, *args, **kwargs)