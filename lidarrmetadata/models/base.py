"""
Base models and common types used across the API.
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Standard error response model"""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")
    error_code: Optional[str] = Field(None, description="Machine-readable error code")


class HealthResponse(BaseModel):
    """Health check response model"""
    status: str = Field(..., description="Health status")
    framework: str = Field(..., description="Framework name")


class InfoResponse(BaseModel):
    """API information response model"""
    branch: Optional[str] = Field(None, description="Git branch")
    commit: Optional[str] = Field(None, description="Git commit hash")
    version: str = Field(..., description="API version")
    replication_date: Optional[str] = Field(None, description="Data replication date")