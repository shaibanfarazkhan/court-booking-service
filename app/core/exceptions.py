"""Domain exception definitions."""


class DomainException(Exception):
    """Base domain exception."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DuplicateEmailError(DomainException):
    """Raised when registering an account with an existing email."""


class InvalidCredentialsError(DomainException):
    """Raised when authentication fails due to incorrect credentials."""


class AccountInactiveError(DomainException):
    """Raised when an inactive account attempts to log in or perform actions."""


class InvalidTokenError(DomainException):
    """Raised when a provided JWT token is invalid, malformed, or expired."""


class UserNotFoundError(DomainException):
    """Raised when a requested user entity does not exist."""


class InsufficientPermissionsError(DomainException):
    """Raised when a user lacks the required role or privileges."""


class ResourceNotFoundError(DomainException):
    """Raised when a venue, court, or availability record does not exist."""


class DuplicateAvailabilityError(DomainException):
    """Raised when a court already has the requested weekly time window."""


class ResourceConflictError(DomainException):
    """Raised when a resource conflicts with an existing database record."""
