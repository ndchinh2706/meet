"""URL configuration for the core app."""

from django.conf import settings
from django.urls import include, path

from lasuite.oidc_login.urls import urlpatterns as oidc_urls
from local_auth.urls import urlpatterns as local_auth_urls
from rest_framework.routers import DefaultRouter, SimpleRouter

from core.addons import viewsets as addons_viewsets
from core.api import get_frontend_configuration, viewsets
from core.api.mcp import mcp_endpoint
from core.external_api import viewsets as external_viewsets
from transcription.api.urls import urlpatterns as transcription_urls

# - Main endpoints
router = DefaultRouter()
router.register("users", viewsets.UserViewSet, basename="users")
router.register("pats", viewsets.PersonalAccessTokenViewSet, basename="pats")
router.register("rooms", viewsets.RoomViewSet, basename="rooms")
router.register("recordings", viewsets.RecordingViewSet, basename="recordings")
router.register("files", viewsets.FileViewSet, basename="files")
router.register(
    "resource-accesses", viewsets.ResourceAccessViewSet, basename="resource_accesses"
)
router.register(
    "addons/sessions",
    addons_viewsets.SessionViewSet,
    basename="addons_sessions",
)

# - External API
external_router = SimpleRouter()
external_router.register(
    "application",
    external_viewsets.ApplicationViewSet,
    basename="external_application",
)
external_router.register(
    "rooms",
    external_viewsets.RoomViewSet,
    basename="external_room",
)

urlpatterns = [
    path(
        f"api/{settings.API_VERSION}/",
        include(
            [
                *router.urls,
                *oidc_urls,
                *local_auth_urls,
                path("config/", get_frontend_configuration, name="config"),
                path("mcp/", mcp_endpoint, name="mcp"),
            ]
        ),
    ),
]

if settings.EXTERNAL_API_ENABLED:
    urlpatterns.append(
        path(
            f"external-api/{settings.EXTERNAL_API_VERSION}/",
            include(
                [
                    *external_router.urls,
                    *transcription_urls,
                ]
            ),
        )
    )
