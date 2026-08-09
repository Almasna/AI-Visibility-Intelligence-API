from __future__ import annotations

import logging
from typing import Any

from flask import Flask, jsonify
from pydantic import ValidationError
from werkzeug.exceptions import HTTPException


logger = logging.getLogger(__name__)


class ApiError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class AgentError(Exception):
    pass


class LLMServiceError(Exception):
    pass


class ExternalDataError(Exception):
    pass


class ExternalAuthenticationError(ExternalDataError):
    pass


class ExternalRateLimitError(ExternalDataError):
    pass


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        error: dict[str, Any] = {"code": exc.code, "message": exc.message}
        if exc.details is not None:
            error["details"] = exc.details
        return jsonify({"error": error}), exc.status_code

    @app.errorhandler(ValidationError)
    def handle_validation_error(exc: ValidationError):
        details = [
            {
                "field": ".".join(str(part) for part in error["loc"]),
                "message": error["msg"],
            }
            for error in exc.errors(include_url=False, include_input=False)
        ]
        return (
            jsonify(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request validation failed.",
                        "details": details,
                    }
                }
            ),
            422,
        )

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        return (
            jsonify(
                {
                    "error": {
                        "code": f"HTTP_{exc.code}",
                        "message": exc.description,
                    }
                }
            ),
            exc.code,
        )

    @app.errorhandler(Exception)
    def handle_unexpected_error(exc: Exception):
        logger.exception("unhandled_exception", exc_info=exc)
        return (
            jsonify(
                {
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "An unexpected error occurred.",
                    }
                }
            ),
            500,
        )
