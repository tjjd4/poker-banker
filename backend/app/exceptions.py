"""
Domain exceptions for the Poker Banker application.

Services raise these plain Python exceptions instead of FastAPI's HTTPException.
The exception handlers registered in main.py translate them to HTTP responses.
This decouples business logic from the HTTP transport layer.
"""


class PokerBankerError(Exception):
    """Base class for all domain-level errors in this application."""


class NotFoundError(PokerBankerError):
    """Raised when a requested resource does not exist. → HTTP 404"""


class ForbiddenError(PokerBankerError):
    """Raised when the current user lacks permission to access a resource. → HTTP 403"""


class ConflictError(PokerBankerError):
    """Raised when an operation would violate a uniqueness or state constraint. → HTTP 409"""


class ValidationError(PokerBankerError):
    """Raised when input data fails business-rule validation. → HTTP 400"""


class AuthenticationError(PokerBankerError):
    """Raised when credentials are invalid or the user is not authenticated. → HTTP 401"""
