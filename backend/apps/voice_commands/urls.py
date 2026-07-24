from django.urls import path

from apps.voice_commands.views import VoiceParseView

urlpatterns = [
    path('parse/', VoiceParseView.as_view(), name='voice-parse'),
]
