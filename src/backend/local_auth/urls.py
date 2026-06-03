from django.urls import path

from .views import CsrfView, LoginView, LogoutView, SignupView

urlpatterns = [
    path("auth/csrf/", CsrfView.as_view(), name="local_auth_csrf"),
    path("auth/login/", LoginView.as_view(), name="local_auth_login"),
    path("auth/signup/", SignupView.as_view(), name="local_auth_signup"),
    path("auth/logout/", LogoutView.as_view(), name="local_auth_logout"),
]
