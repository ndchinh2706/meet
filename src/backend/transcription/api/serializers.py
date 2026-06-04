"""Serializers for the transcription write endpoint."""

from rest_framework import serializers

from transcription.models import MeetingUtterance


class MeetingUtteranceWriteSerializer(serializers.ModelSerializer):
    """Validate utterance payloads sent by an agent worker.

    `room` is taken from the URL, never the body — we don't want a
    misconfigured agent writing into someone else's room.
    """

    class Meta:
        model = MeetingUtterance
        fields = [
            "id",
            "speaker_identity",
            "speaker_name",
            "text",
            "language",
            "started_at",
            "ended_at",
            "is_final",
        ]
        read_only_fields = ["id"]

    def validate_text(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("Utterance text cannot be empty.")
        return value


class MeetingUtteranceReadSerializer(serializers.ModelSerializer):
    """Read shape used by MCP query tools."""

    class Meta:
        model = MeetingUtterance
        fields = [
            "id",
            "speaker_identity",
            "speaker_name",
            "text",
            "language",
            "started_at",
            "ended_at",
            "is_final",
        ]
        read_only_fields = fields
