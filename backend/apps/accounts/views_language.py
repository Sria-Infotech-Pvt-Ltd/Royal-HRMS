"""
Interface language - each signed-in person's own choice, kept on their user so it follows them to another device. Like the theme, it is
identity display, not a permission-gated action: everyone manages their own.
"""
from __future__ import annotations

import logging

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, first_error, success

logger = logging.getLogger(__name__)

# Keep in step with LANGUAGES in frontend/lib/i18n/languages.ts.
LANGUAGE_CODES = ('en', 'hi', 'te', 'bn', 'mr', 'ta', 'gu', 'ur', 'kn', 'or', 'ml', 'pa', 'as')


class LanguageSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=LANGUAGE_CODES)


class MyLanguageView(APIView):
    """
    GET /api/employees/me/language/  - the saved language code, or null if never chosen
    PUT /api/employees/me/language/  - save it
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return success('Language loaded.', {'language': request.user.language or None})

    def put(self, request: Request) -> Response:
        serializer = LanguageSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        user = request.user
        user.language = serializer.validated_data['language']
        user.save(update_fields=['language', 'updated_at'])
        return success('Language saved.', {'language': user.language})
