"""URL config for transcription endpoints."""

from django.urls import path

from transcription.api.viewsets import UtteranceWriteViewSet

urlpatterns = [
    path(
        "rooms/<str:room_id>/utterances/",
        UtteranceWriteViewSet.as_view({"post": "create"}),
        name="transcription_utterance_write",
    ),
]
