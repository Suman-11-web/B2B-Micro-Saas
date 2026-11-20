"""
Custom exception handling for consistent API error responses.
"""
from rest_framework.views import exception_handler
from rest_framework.exceptions import (
    AuthenticationFailed, NotAuthenticated, PermissionDenied,
    NotFound, ValidationError, Throttled
)
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """Custom exception handler for consistent error responses with correlation trace ID."""
    request = context.get('request') if context else None
    trace_id = getattr(request, 'trace_id', None)

    # Call DRF's default handler first
    response = exception_handler(exc, context)

    # If DRF couldn't handle it, create a generic response
    if response is None:
        logger.exception('Unhandled exception', exc_info=exc, extra={'trace_id': trace_id})
        return Response(
            {'error': 'internal_error', 'message': 'An unexpected error occurred.', 'trace_id': trace_id},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    # Customize response format
    custom_data = {
        'error': get_error_code(exc),
        'message': get_error_message(exc, response),
        'details': response.data if isinstance(response.data, (dict, list)) else None,
        'trace_id': trace_id,
    }

    response.data = custom_data
    return response


def get_error_code(exc):
    """Map exception types to error codes."""
    error_codes = {
        AuthenticationFailed: 'authentication_failed',
        NotAuthenticated: 'not_authenticated',
        PermissionDenied: 'permission_denied',
        NotFound: 'not_found',
        ValidationError: 'validation_error',
        Throttled: 'rate_limited',
        DjangoValidationError: 'validation_error',
        IntegrityError: 'integrity_error',
    }
    return error_codes.get(type(exc), 'unknown_error')


def get_error_message(exc, response):
    """Extract user-friendly error message."""
    if isinstance(exc, ValidationError):
        if isinstance(response.data, dict):
            # Return first field error
            for field, errors in response.data.items():
                if isinstance(errors, list) and errors:
                    return f"{field}: {errors[0]}"
                elif isinstance(errors, str):
                    return f"{field}: {errors}"
        return 'Validation failed.'
    elif isinstance(exc, Throttled):
        return f'Rate limit exceeded. Try again in {exc.wait} seconds.'
    elif isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
        return str(exc.detail) if hasattr(exc, 'detail') else 'Authentication required.'
    elif isinstance(exc, PermissionDenied):
        return str(exc.detail) if hasattr(exc, 'detail') else 'Permission denied.'
    elif isinstance(exc, NotFound):
        return 'The requested resource was not found.'
    return str(exc) if str(exc) else 'An error occurred.'


# Import Response for the fallback case
from rest_framework.response import Response