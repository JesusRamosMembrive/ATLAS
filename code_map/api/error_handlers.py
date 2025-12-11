"""
FastAPI exception handlers for AEGIS.

This module provides centralized error handling that:
- Converts AEGISException to consistent JSON responses
- Logs errors appropriately
- Hides internal details from clients for security
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..exceptions import AEGISException

logger = logging.getLogger(__name__)


class ErrorDetail(BaseModel):
    """Structured error detail for API responses."""

    code: str
    message: str
    timestamp: str
    path: str
    details: Optional[dict] = None


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: ErrorDetail


async def aegis_exception_handler(
    request: Request, exc: AEGISException
) -> JSONResponse:
    """Handler for AEGIS custom exceptions.

    Logs the error with context and returns a structured JSON response.
    The exception's context is included in logs but only exposed to clients
    if it contains safe, useful information.
    """
    logger.warning(
        "AEGIS error: %s",
        exc,
        extra={
            "error_code": exc.code,
            "status_code": exc.status_code,
            "path": str(request.url.path),
            "context": exc.context,
        },
    )

    # Only include context details that are safe for clients
    safe_details = None
    if exc.context:
        # Filter out internal details, keep only user-relevant ones
        safe_keys = {
            "path",
            "field",
            "reason",
            "endpoint",
            "run_id",
            "report_id",
            "notification_id",
            "event_id",
            "reason_code",
            "retry_after_seconds",
            "loading_since",
            "status_code_response",
        }
        safe_details = {
            k: v for k, v in exc.context.items() if k in safe_keys and v is not None
        }
        if not safe_details:
            safe_details = None

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": str(request.url.path),
                "details": safe_details,
            }
        },
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handler for unhandled exceptions.

    IMPORTANT: This handler intentionally does NOT expose exception details
    to prevent information leakage. All details are logged server-side.
    """
    logger.exception(
        "Unhandled exception at %s: %s",
        request.url.path,
        exc,
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "exception_type": type(exc).__name__,
        },
    )

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An internal error occurred",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "path": str(request.url.path),
            }
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app.

    Call this during app initialization to enable centralized error handling.
    """
    app.add_exception_handler(AEGISException, aegis_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
