"""
Models for monitoring and health check endpoints.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HangingOperationDetail(BaseModel):
    """Details of a hanging operation"""
    name: str = Field(..., description="Operation name")
    running_time: float = Field(..., description="How long the operation has been running (seconds)")
    timeout: float = Field(..., description="Configured timeout for the operation (seconds)")
    context: Dict[str, Any] = Field(default_factory=dict, description="Operation context (e.g., mbid, query)")


class FailedOperationDetail(BaseModel):
    """Details of a failed operation"""
    name: str = Field(..., description="Operation name")
    duration: Optional[float] = Field(None, description="How long the operation took before failing (seconds)")
    success: bool = Field(..., description="Whether the operation succeeded")
    context: Dict[str, Any] = Field(default_factory=dict, description="Operation context")


class CircuitBreakerStats(BaseModel):
    """Circuit breaker statistics"""
    total_calls: int = Field(..., description="Total number of calls made")
    successful_calls: int = Field(..., description="Number of successful calls")
    failed_calls: int = Field(..., description="Number of failed calls")
    timeouts: int = Field(..., description="Number of timeout failures")
    circuit_opens: int = Field(..., description="Number of times circuit has opened")
    last_failure_time: Optional[float] = Field(None, description="Timestamp of last failure")
    last_success_time: Optional[float] = Field(None, description="Timestamp of last success")
    success_rate: float = Field(..., description="Success rate (0.0 to 1.0)")


class CircuitBreakerConfig(BaseModel):
    """Circuit breaker configuration"""
    failure_threshold: int = Field(..., description="Number of failures before opening")
    recovery_timeout: int = Field(..., description="Seconds to wait before trying again")
    success_threshold: int = Field(..., description="Successes needed to close from half-open")
    timeout: float = Field(..., description="Default timeout for calls")


class CircuitBreakerInfo(BaseModel):
    """Complete circuit breaker information"""
    name: str = Field(..., description="Circuit breaker name")
    state: str = Field(..., description="Current state (closed, open, half_open)")
    failure_count: int = Field(..., description="Current failure count")
    success_count: int = Field(..., description="Current success count in half-open state")
    config: CircuitBreakerConfig = Field(..., description="Circuit breaker configuration")
    stats: CircuitBreakerStats = Field(..., description="Circuit breaker statistics")


class AsyncHealthResponse(BaseModel):
    """Async operations health check response model"""
    healthy: bool = Field(..., description="Whether async operations are healthy")
    active_operations: int = Field(..., description="Number of currently active operations")
    hanging_operations: int = Field(..., description="Number of hanging operations")
    total_recent_operations: int = Field(..., description="Total recent operations tracked")
    framework: str = Field(..., description="Framework name")
    hanging_details: List[HangingOperationDetail] = Field(default_factory=list, description="Details of hanging operations")
    recent_failures: List[FailedOperationDetail] = Field(default_factory=list, description="Recent failed operations")
    circuit_breakers: Dict[str, CircuitBreakerInfo] = Field(default_factory=dict, description="Circuit breaker information")


class CleanupResponse(BaseModel):
    """Response for manual cleanup operations"""
    cleaned_operations: int = Field(..., description="Number of operations cleaned up")
    message: str = Field(..., description="Human-readable result message")