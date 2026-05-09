from __future__ import annotations


class AppError(Exception):
    """Base exception for application errors."""


class QueryError(AppError):
    """Base exception for query parsing/execution errors."""


class InvalidQueryError(QueryError):
    """Raised when query syntax or semantics are invalid."""


class CatalogueError(AppError):
    """Raised when the virtual catalogue is inconsistent or missing data."""

