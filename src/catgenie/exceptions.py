"""Exception hierarchy for the CatGenie API client."""


class CatGenieException(Exception):
    """Base exception for all CatGenie library errors.

    Downstream consumers (e.g. Home Assistant integrations) can catch this
    single type instead of bare ``Exception`` to handle any library-specific
    error while still letting programming errors propagate.
    """


class CatGenieAuthenticationError(CatGenieException):
    """Raised when authentication or token refresh fails."""


class CatGenieAPIError(CatGenieException):
    """Raised when an API request returns an unexpected HTTP status."""
