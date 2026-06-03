from django.contrib.auth import authenticate, get_user_model, login, logout
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import LoginSerializer, SignupSerializer, UserSerializer

User = get_user_model()


class CsrfView(APIView):
    """Mint and return a CSRF token (sets the csrftoken cookie via middleware).

    The local auth POST endpoints below enforce CSRF (SessionAuthentication
    requires it). The frontend calls this once on app boot to obtain a token,
    then sends it in the X-CSRFToken header on subsequent POSTs.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None or not user.is_active:
            return Response(
                {"detail": "Invalid email or password."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response(UserSerializer(user).data)


class SignupView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        full_name = serializer.validated_data.get("full_name") or email.split("@")[0]

        user = User(
            admin_email=email,
            email=email,
            full_name=full_name,
            is_active=True,
        )
        user.set_password(password)
        user.save()

        # Django requires an explicit backend when multiple are configured
        # (ModelBackend for local auth + OIDC backend). Without it, login()
        # raises ValueError. We bypass authenticate() on signup since the
        # password we just set hasn't gone through the auth pipeline yet.
        login(
            request, user, backend="django.contrib.auth.backends.ModelBackend"
        )
        return Response(
            UserSerializer(user).data, status=status.HTTP_201_CREATED
        )


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)
