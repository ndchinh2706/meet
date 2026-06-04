"""Agent-facing write endpoint for meeting utterances."""

from logging import getLogger

from django.conf import settings
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core import models as core_models
from transcription import models
from transcription.api.serializers import MeetingUtteranceWriteSerializer
from transcription.authentication import AgentApiKeyAuthentication

logger = getLogger(__name__)


class UtteranceWriteViewSet(viewsets.ViewSet):
    """POST /external-api/v1/rooms/{room_id}/utterances/

    Agent writes go here. The room id can be either the UUID PK or the slug;
    we accept both because the agent receives `ctx.room.name` from LiveKit
    which is the UUID, but humans curling for tests use slugs.
    """

    authentication_classes = [AgentApiKeyAuthentication]
    permission_classes = [IsAuthenticated]

    @staticmethod
    def _resolve_room(room_ref: str):
        qs = core_models.Room.objects.all()
        # Try UUID first; fall back to slug. Mirrors the MCP tool helper.
        # ValidationError covers non-UUID strings rejected by UUIDField.
        try:
            return qs.get(id=room_ref)
        except (core_models.Room.DoesNotExist, ValueError, ValidationError):
            pass
        return get_object_or_404(qs, slug=room_ref)

    def create(self, request, room_id=None):
        if not getattr(settings, "TRANSCRIPTION_ENABLED", False):
            return Response(
                {"detail": "Transcription is disabled."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        room = self._resolve_room(room_id)
        serializer = MeetingUtteranceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        utterance = models.MeetingUtterance.objects.create(
            room=room, **serializer.validated_data
        )

        logger.info(
            "Utterance saved: room=%s speaker=%s len=%d final=%s",
            room.id,
            utterance.speaker_identity,
            len(utterance.text),
            utterance.is_final,
        )
        return Response(
            MeetingUtteranceWriteSerializer(utterance).data,
            status=status.HTTP_201_CREATED,
        )
