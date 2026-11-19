"""
Colour theme - each signed-in person's own choice (light / dark / follow device, plus an accent colour), kept on their user so it
follows them to another device. Identity display, not a permission-gated action: everyone manages their own.
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

THEME_MODES = ('system', 'light', 'dark')
THEME_ACCENTS = ('royal', 'ocean', 'forest', 'sunset')


class ThemeSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=THEME_MODES)
    accent = serializers.ChoiceField(choices=THEME_ACCENTS)


def _theme_of(user) -> dict:
    """What is saved, or None for both when the person never chose."""
    return {'mode': user.theme_mode or None, 'accent': user.theme_accent or None}


class MyThemeView(APIView):
    """
    GET /api/employees/me/theme/  - the saved theme ({mode, accent}, each null if never chosen)
    PUT /api/employees/me/theme/  - save it
    """

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return success('Theme loaded.', _theme_of(request.user))

    def put(self, request: Request) -> Response:
        serializer = ThemeSerializer(data=request.data)
        if not serializer.is_valid():
            return error(first_error(serializer.errors), data=serializer.errors)
        user = request.user
        user.theme_mode = serializer.validated_data['mode']
        user.theme_accent = serializer.validated_data['accent']
        user.save(update_fields=['theme_mode', 'theme_accent', 'updated_at'])
        return success('Theme saved.', _theme_of(user))
