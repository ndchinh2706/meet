"""Authentication for the transcription write path.

Agent workers are servers, not users — they authenticate with a single
shared bearer secret (`settings.AGENT_API_KEY`). Compared to the OIDC/PAT
auth used for human-facing endpoints, this is intentionally minimal:
service-to-service trust, rotated by changing the env var.

If the secret is missing or the supplied bearer doesn't match, every
request is rejected. There is no anonymous fallback.
"""

from secrets import compare_digest

from django.conf import settings
from django.contrib.auth.models import AnonymousUser

from rest_framework import authentication, exceptions


class AgentApiKeyUser(AnonymousUser):
    """Placeholder request.user so DRF permissions see an authenticated principal.

    Agent writes are never bound to a real Django user — the principal is
    the agent fleet as a whole. We still need `is_authenticated == True`
    so views guarded by IsAuthenticated work.
    """

    @property
    def is_authenticated(self) -> bool:  # type: ignore[override]
        return True

    def __str__(self) -> str:
        return "agent-fleet"


class AgentApiKeyAuthentication(authentication.BaseAuthentication):
    """Validate `Authorization: Bearer <AGENT_API_KEY>`."""

    keyword = "Bearer"

    def authenticate(self, request):
        header = request.headers.get("Authorization")
        if not header:
            return None

        parts = header.split()
        if len(parts) != 2 or parts[0].lower() != self.keyword.lower():
            return None

        presented = parts[1]
        expected = getattr(settings, "AGENT_API_KEY", None) or ""
        if not expected:
            # Endpoint disabled until the operator provisions a key.
            raise exceptions.AuthenticationFailed(
                "Agent API is not configured on this deployment."
            )

        # `compare_digest` so a bad token never short-circuits early.
        if not compare_digest(presented, expected):
            raise exceptions.AuthenticationFailed("Invalid agent token.")

        return (AgentApiKeyUser(), None)

    def authenticate_header(self, request):
        return self.keyword
