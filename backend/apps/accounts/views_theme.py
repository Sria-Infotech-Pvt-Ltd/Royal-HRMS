"""
Colour theme - each signed-in person's own choice (light / dark / follow device, an accent colour, a look such as soft or compact, and optional own colours), kept on their user so it
follows them to another device. Identity display, not a permission-gated action: everyone manages their own.
"""
from __future__ import annotations

import logging
import re

from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from core.responses import error, first_error, success

logger = logging.getLogger(__name__)

THEME_MODES = ('system', 'light', 'dark')
THEME_ACCENTS = ('royal', 'ocean', 'forest', 'sunset')
# Keep in step with THEME_STYLES / CUSTOM_COLOUR_KEYS in frontend/lib/theme.ts.
THEME_STYLES = ('classic', 'soft', 'compact', 'glass', 'amoled', 'contrast')
CUSTOM_COLOUR_KEYS = ('brand', 'background', 'card', 'text', 'header')
HEX_COLOUR = re.compile(r'^#[0-9a-fA-F]{6}$')


class ThemeSerializer(serializers.Serializer):
    mode = serializers.ChoiceField(choices=THEME_MODES)
    accent = serializers.ChoiceField(choices=THEME_ACCENTS)
    style = serializers.ChoiceField(choices=THEME_STYLES, required=False)
    custom = serializers.DictField(child=serializers.CharField(), required=False)

    def validate_custom(self, value: dict) -> dict:
        for key, colour in value.items():
            if key not in CUSTOM_COLOUR_KEYS:
                raise serializers.ValidationError(f'"{key}" is not a colour you can change.')
            if not HEX_COLOUR.match(colour):
                raise serializers.ValidationError('Colours must be written like #7c3aed (a # and six letters or digits).')
        return {key: colour.lower() for key, colour in value.items()}


def _theme_of(user) -> dict:
    """What is saved, or None for both when the person never chose."""
    return {
        'mode': user.theme_mode or None, 'accent': user.theme_accent or None,
        'style': user.theme_style or None, 'custom': user.theme_custom or {},
    }


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
        # Style and colours are optional so older clients that only send mode + accent keep working; a client that sends them replaces them.
        if 'style' in serializer.validated_data:
            user.theme_style = serializer.validated_data['style']
        if 'custom' in serializer.validated_data:
            user.theme_custom = serializer.validated_data['custom']
        user.save(update_fields=['theme_mode', 'theme_accent', 'theme_style', 'theme_custom', 'updated_at'])
        return success('Theme saved.', _theme_of(user))
