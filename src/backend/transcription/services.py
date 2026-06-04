"""Read-side helpers used by MCP query tools.

Kept separate from viewsets so the MCP layer doesn't reach into HTTP
plumbing it doesn't need. Each function takes the requesting user so
access control is enforced centrally.
"""

from datetime import datetime
from typing import Optional

from django.core.exceptions import ValidationError
from django.db.models import Count, Max

from core import models as core_models
from transcription import models


def _accessible_rooms(user):
    """Rooms the user has any role on.

    Mirrors the rule used elsewhere for room access — owners, admins, and
    members can all see content. Anonymous callers see nothing.
    """
    if not user or not user.is_authenticated:
        return core_models.Room.objects.none()
    return core_models.Room.objects.filter(accesses__user=user).distinct()


def list_meetings(
    user, limit: int = 20, since: Optional[datetime] = None
) -> list[dict]:
    """Return rooms the user can access, annotated with transcript metrics."""

    qs = _accessible_rooms(user).annotate(
        utterance_count=Count("utterances"),
        last_utterance_at=Max("utterances__created_at"),
    )
    if since is not None:
        qs = qs.filter(utterances__created_at__gte=since)

    qs = qs.order_by("-last_utterance_at", "-created_at")[: max(1, min(limit, 100))]

    return [
        {
            "room_id": str(room.id),
            "slug": room.slug,
            "name": room.name,
            "created_at": room.created_at.isoformat(),
            "utterance_count": room.utterance_count,
            "last_utterance_at": (
                room.last_utterance_at.isoformat()
                if room.last_utterance_at
                else None
            ),
        }
        for room in qs
    ]


def get_meeting_transcript(
    user,
    room_ref: str,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    include_partial: bool = False,
) -> Optional[list[dict]]:
    """Return all utterances for the room in chronological order.

    Returns `None` when the room doesn't exist OR the user has no access
    — the MCP layer turns that into a single "not found" error so we don't
    leak whether the room exists.
    """

    rooms = _accessible_rooms(user)
    try:
        room = rooms.get(id=room_ref)
    except (core_models.Room.DoesNotExist, ValueError, ValidationError):
        room = rooms.filter(slug=room_ref).first()
    if room is None:
        return None

    qs = models.MeetingUtterance.objects.filter(room=room)
    if not include_partial:
        qs = qs.filter(is_final=True)
    if since is not None:
        qs = qs.filter(started_at__gte=since)
    if until is not None:
        qs = qs.filter(started_at__lte=until)

    qs = qs.order_by("started_at")

    return [
        {
            "id": str(u.id),
            "speaker_identity": u.speaker_identity,
            "speaker_name": u.speaker_name,
            "text": u.text,
            "language": u.language,
            "started_at": u.started_at.isoformat(),
            "ended_at": u.ended_at.isoformat() if u.ended_at else None,
            "is_final": u.is_final,
        }
        for u in qs
    ]
