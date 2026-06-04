"""Meeting transcription storage."""

import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class MeetingUtterance(models.Model):
    """A single utterance produced by an STT pipeline during a meeting.

    One row per speaker turn (final transcript) plus optional interim drafts.
    Rows are append-only — edits/deletes only happen at retention sweep time.

    Indexing:
      - PK uuid for safe external reference (used by MCP results).
      - composite (room, started_at) for the dominant query pattern:
        'give me everything for room X in time order'.
    """

    id = models.UUIDField(
        primary_key=True, default=uuid.uuid4, editable=False
    )
    room = models.ForeignKey(
        "core.Room",
        on_delete=models.CASCADE,
        related_name="utterances",
    )
    # Stable LiveKit identity for the speaker. This is what queries dedupe
    # against; the display name is denormalised for nicer output.
    speaker_identity = models.CharField(max_length=255, db_index=True)
    speaker_name = models.CharField(max_length=255, blank=True)
    text = models.TextField()
    # BCP-47-ish language code (vi, en, en-US, …) or empty when unknown.
    language = models.CharField(max_length=10, blank=True)
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    is_final = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        db_table = "meet_meeting_utterance"
        ordering = ("room", "started_at")
        indexes = [
            models.Index(
                fields=("room", "started_at"),
                name="meet_utt_room_time_idx",
            ),
        ]
        verbose_name = _("Meeting utterance")
        verbose_name_plural = _("Meeting utterances")

    def __str__(self) -> str:
        return f"{self.speaker_name or self.speaker_identity}: {self.text[:50]}"
