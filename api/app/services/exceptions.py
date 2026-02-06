"""
Service Layer Exceptions

Custom exception classes for service layer operations.
"""

from typing import Any, Dict, Optional


class NLPProcessingError(Exception):
    """
    Raised when NLP processing fails.

    This exception is raised when the NLP pipeline fails to process
    a natural language description into an alert specification.
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        stage: Optional[str] = None
    ):
        """
        Initialize NLP processing error.

        Args:
            message: Human-readable error message
            details: Additional error details (pipeline metadata, etc.)
            stage: Which pipeline stage failed (e.g., 'intent_classification')
        """
        super().__init__(message)
        self.details = details or {}
        self.stage = stage

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            'error': str(self),
            'details': self.details,
            'stage': self.stage,
        }


class AlertCreationError(Exception):
    """
    Raised when alert creation fails after NLP processing.

    This exception is raised when the alert creation process fails
    during template or instance creation, after NLP has succeeded.
    """

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize alert creation error.

        Args:
            message: Human-readable error message
            details: Additional error details
        """
        super().__init__(message)
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response."""
        return {
            'error': str(self),
            'details': self.details,
        }


class NLPNotConfiguredError(Exception):
    """
    Raised when NLP service is not configured.

    This exception is raised when attempting to use NLP features
    but the NLP service has not been properly configured.
    """

    def __init__(self, message: str = "NLP service not configured. Check GEMINI_API_KEY setting."):
        super().__init__(message)
