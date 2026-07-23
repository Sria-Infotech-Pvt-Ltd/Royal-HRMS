import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.utils import OperationalError as DBOperationalError
from django.http import Http404

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    # Let DRF handle what it knows first
    response = exception_handler(exc, context)

    if response is not None:
        # Normalize DRF error shapes into our standard format
        data = response.data
        if isinstance(data, dict) and 'detail' in data:
            message = str(data['detail'])
        elif isinstance(data, list):
            message = data[0] if data else 'An error occurred.'
        elif isinstance(data, dict):
            # Field-level validation errors — flatten into message
            first_field, first_errors = next(iter(data.items()))
            first_error = first_errors[0] if isinstance(first_errors, list) else first_errors
            message = f'{first_field}: {first_error}'
        else:
            message = str(data)

        return Response({
            'status': 'error',
            'message': message,
            'data': data if isinstance(data, dict) else {},
        }, status=response.status_code)

    # Django-level errors not caught by DRF
    if isinstance(exc, Http404):
        return Response({
            'status': 'error',
            'message': 'The requested resource was not found.',
            'data': {},
        }, status=status.HTTP_404_NOT_FOUND)

    if isinstance(exc, DjangoValidationError):
        return Response({
            'status': 'error',
            'message': exc.messages[0] if exc.messages else 'Validation error.',
            'data': {},
        }, status=status.HTTP_400_BAD_REQUEST)

    if isinstance(exc, DBOperationalError):
        view = context.get('view')
        logger.error(
            'Database unavailable in %s: %s',
            view.__class__.__name__ if view else 'unknown view',
            str(exc),
        )
        return Response({
            'status': 'error',
            'message': 'Database is temporarily unavailable. Please try again in a moment.',
            'data': {},
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    # Truly unexpected errors — log and return generic message
    view = context.get('view')
    logger.exception(
        'Unhandled exception in %s: %s',
        view.__class__.__name__ if view else 'unknown view',
        str(exc),
    )
    return Response({
        'status': 'error',
        'message': 'An unexpected error occurred. Please try again later.',
        'data': {},
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
