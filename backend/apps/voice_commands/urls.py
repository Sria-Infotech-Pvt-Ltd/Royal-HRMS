from django.urls import path

from apps.voice_commands.views import VoiceParseView
from apps.voice_commands.views_speak import VoiceSpeakView
from apps.voice_commands.views_transcribe import VoiceTranscribeFallbackView

urlpatterns = [
    path('parse/', VoiceParseView.as_view(), name='voice-parse'),
    path('transcribe-fallback/', VoiceTranscribeFallbackView.as_view(), name='voice-transcribe-fallback'),
    path('speak/', VoiceSpeakView.as_view(), name='voice-speak'),
]
