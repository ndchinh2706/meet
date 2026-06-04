"""Personal Access Token authentication for Meet API."""

from django.utils import timezone

from rest_framework import authentication, exceptions

from core import models, utils


class PersonalAccessTokenAuthentication(authentication.BaseAuthentication):
    """Authenticate via `Authorization: Bearer meet_pat_<...>` header.

    Reads a Personal Access Token from the Authorization header, validates it
    against the database (looking up by SHA-256 hash for indexed access), and
    returns the associated user. Updates `last_used_at` on success.
    """

    keyword = "Bearer"

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != self.keyword.lower():
            return None

        raw_token = parts[1]
        if not raw_token.startswith(utils.PAT_PREFIX):
            # Not a PAT — let other auth classes handle (OIDC, Application JWT, etc.)
            return None

        token_hash = utils.hash_pat_token(raw_token)

        try:
            pat = models.PersonalAccessToken.objects.select_related("user").get(
                token_hash=token_hash
            )
        except models.PersonalAccessToken.DoesNotExist as e:
            raise exceptions.AuthenticationFailed("Invalid token.") from e

        if not pat.is_usable:
            raise exceptions.AuthenticationFailed("Token is revoked or expired.")

        if not pat.user.is_active:
            raise exceptions.AuthenticationFailed("User account is inactive.")

        pat.last_used_at = timezone.now()
        pat.save(update_fields=["last_used_at"])

        return (pat.user, pat)

    def authenticate_header(self, request):
        return self.keyword
