"""
Custom exceptions for AEGIS backend.

This module defines a hierarchy of exceptions that provide:
- Consistent error codes for API clients
- Appropriate HTTP status codes
- Structured error context for debugging
- Security: internal details are not exposed to clients
"""

from typing import Any


class AEGISException(Exception):
    """Base exception for all AEGIS errors.

    Attributes:
        code: Unique error code for client identification
        status_code: HTTP status code to return
        message: Human-readable error message
        context: Additional context for debugging (not exposed to clients)
    """

    code: str = "AEGIS_ERROR"
    status_code: int = 500
    message: str = "An unexpected error occurred"

    def __init__(
        self,
        message: str | None = None,
        **context: Any,
    ) -> None:
        self.message = message or self.__class__.message
        self.context = context
        super().__init__(self.message)

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


# =============================================================================
# Resource Errors (4xx)
# =============================================================================

class ResourceNotFoundError(AEGISException):
    """Base class for resource not found errors (404)."""

    code = "RESOURCE_NOT_FOUND"
    status_code = 404
    message = "Requested resource not found"


class FileNotFoundError(ResourceNotFoundError):
    """File or path not found."""

    code = "FILE_NOT_FOUND"
    message = "File not found"

    def __init__(self, path: str | None = None, **context: Any) -> None:
        message = f"File not found: {path}" if path else None
        super().__init__(message, path=path, **context)


class RunNotFoundError(ResourceNotFoundError):
    """Audit run not found."""

    code = "RUN_NOT_FOUND"
    message = "Audit run not found"

    def __init__(self, run_id: int | None = None, **context: Any) -> None:
        message = f"Audit run not found: {run_id}" if run_id else None
        super().__init__(message, run_id=run_id, **context)


class ReportNotFoundError(ResourceNotFoundError):
    """Linter report not found."""

    code = "REPORT_NOT_FOUND"
    message = "Report not found"

    def __init__(self, report_id: int | None = None, **context: Any) -> None:
        message = f"Report not found: {report_id}" if report_id else None
        super().__init__(message, report_id=report_id, **context)


class NotificationNotFoundError(ResourceNotFoundError):
    """Notification not found."""

    code = "NOTIFICATION_NOT_FOUND"
    message = "Notification not found"

    def __init__(self, notification_id: int | None = None, **context: Any) -> None:
        message = f"Notification not found: {notification_id}" if notification_id else None
        super().__init__(message, notification_id=notification_id, **context)


class EventNotFoundError(ResourceNotFoundError):
    """Audit event not found."""

    code = "EVENT_NOT_FOUND"
    message = "Event not found"


# =============================================================================
# Validation Errors (400)
# =============================================================================

class ValidationError(AEGISException):
    """Base class for validation errors (400)."""

    code = "VALIDATION_ERROR"
    status_code = 400
    message = "Invalid request data"


class InvalidPathError(ValidationError):
    """Invalid file or directory path."""

    code = "INVALID_PATH"
    message = "Invalid path"

    def __init__(self, path: str | None = None, reason: str | None = None, **context: Any) -> None:
        if path and reason:
            message = f"Invalid path '{path}': {reason}"
        elif path:
            message = f"Invalid path: {path}"
        else:
            message = reason
        super().__init__(message, path=path, reason=reason, **context)


class InvalidConfigError(ValidationError):
    """Invalid configuration value."""

    code = "INVALID_CONFIG"
    message = "Invalid configuration"

    def __init__(self, field: str | None = None, reason: str | None = None, **context: Any) -> None:
        if field and reason:
            message = f"Invalid configuration for '{field}': {reason}"
        elif field:
            message = f"Invalid configuration: {field}"
        else:
            message = reason
        super().__init__(message, field=field, reason=reason, **context)


class InvalidDateFormatError(ValidationError):
    """Invalid date format."""

    code = "INVALID_DATE_FORMAT"
    message = "Invalid date format"


class ModelNotConfiguredError(ValidationError):
    """Required model not configured."""

    code = "MODEL_NOT_CONFIGURED"
    message = "Model not configured"

    def __init__(self, model_name: str | None = None, **context: Any) -> None:
        message = f"Model not configured: {model_name}" if model_name else None
        super().__init__(message, model_name=model_name, **context)


# =============================================================================
# Permission Errors (403)
# =============================================================================

class PermissionDeniedError(AEGISException):
    """Permission denied for the requested operation (403)."""

    code = "PERMISSION_DENIED"
    status_code = 403
    message = "Permission denied"

    def __init__(self, path: str | None = None, operation: str | None = None, **context: Any) -> None:
        if path and operation:
            message = f"Permission denied: cannot {operation} '{path}'"
        elif path:
            message = f"Permission denied for: {path}"
        else:
            message = None
        super().__init__(message, path=path, operation=operation, **context)


# =============================================================================
# Content Errors (4xx)
# =============================================================================

class ContentError(AEGISException):
    """Base class for content-related errors."""

    code = "CONTENT_ERROR"
    status_code = 400
    message = "Content error"


class FileTooLargeError(ContentError):
    """File exceeds size limit (413)."""

    code = "FILE_TOO_LARGE"
    status_code = 413
    message = "File too large"

    def __init__(
        self,
        path: str | None = None,
        size: int | None = None,
        max_size: int | None = None,
        **context: Any,
    ) -> None:
        if size and max_size:
            message = f"File too large: {size} bytes (max: {max_size})"
        elif path:
            message = f"File too large: {path}"
        else:
            message = None
        super().__init__(message, path=path, size=size, max_size=max_size, **context)


class BinaryFileError(ContentError):
    """Cannot process binary file."""

    code = "BINARY_FILE"
    status_code = 415
    message = "Cannot process binary file"

    def __init__(self, path: str | None = None, **context: Any) -> None:
        message = f"Cannot process binary file: {path}" if path else None
        super().__init__(message, path=path, **context)


class EncodingError(ContentError):
    """File encoding error."""

    code = "ENCODING_ERROR"
    status_code = 415
    message = "Unable to decode file content"


# =============================================================================
# External Service Errors (5xx)
# =============================================================================

class ExternalServiceError(AEGISException):
    """Base class for external service errors (502)."""

    code = "EXTERNAL_SERVICE_ERROR"
    status_code = 502
    message = "External service error"


class OllamaError(ExternalServiceError):
    """Ollama service error."""

    code = "OLLAMA_ERROR"
    message = "Ollama service error"

    def __init__(
        self,
        message: str | None = None,
        endpoint: str | None = None,
        original_error: str | None = None,
        **context: Any,
    ) -> None:
        super().__init__(message, endpoint=endpoint, original_error=original_error, **context)


class OllamaStartError(OllamaError):
    """Failed to start Ollama server."""

    code = "OLLAMA_START_ERROR"
    message = "Failed to start Ollama server"


class OllamaChatError(OllamaError):
    """Ollama chat request failed."""

    code = "OLLAMA_CHAT_ERROR"
    message = "Ollama chat request failed"

    def __init__(
        self,
        message: str | None = None,
        endpoint: str | None = None,
        original_error: str | None = None,
        status_code_response: int | None = None,
        reason_code: str | None = None,
        retry_after_seconds: int | None = None,
        loading_since: str | None = None,
        **context: Any,
    ) -> None:
        super().__init__(
            message,
            endpoint=endpoint,
            original_error=original_error,
            status_code_response=status_code_response,
            reason_code=reason_code,
            retry_after_seconds=retry_after_seconds,
            loading_since=loading_since,
            **context,
        )


class GitError(ExternalServiceError):
    """Git operation error."""

    code = "GIT_ERROR"
    status_code = 500
    message = "Git operation failed"


class SimilarityServiceError(ExternalServiceError):
    """C++ similarity service error."""

    code = "SIMILARITY_ERROR"
    status_code = 502
    message = "Similarity service error"


class CppBridgeError(ExternalServiceError):
    """C++ bridge error."""

    code = "CPP_BRIDGE_ERROR"
    status_code = 502
    message = "C++ bridge error"


# =============================================================================
# Service Availability Errors (503)
# =============================================================================

class ServiceUnavailableError(AEGISException):
    """Service temporarily unavailable (503)."""

    code = "SERVICE_UNAVAILABLE"
    status_code = 503
    message = "Service temporarily unavailable"


class AnalysisInProgressError(ServiceUnavailableError):
    """Analysis is already in progress."""

    code = "ANALYSIS_IN_PROGRESS"
    message = "Analysis is already in progress"


# =============================================================================
# Database Errors (500)
# =============================================================================

class DatabaseError(AEGISException):
    """Database operation error."""

    code = "DATABASE_ERROR"
    status_code = 500
    message = "Database operation failed"


# =============================================================================
# Internal Errors (500)
# =============================================================================

class InternalError(AEGISException):
    """Internal server error - details hidden from client."""

    code = "INTERNAL_ERROR"
    status_code = 500
    message = "An internal error occurred"
