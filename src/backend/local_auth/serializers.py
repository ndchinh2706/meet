from django.contrib.auth import get_user_model
from rest_framework import serializers

from core.api.serializers import UserSerializer  # noqa: F401  (re-exported)

User = get_user_model()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class SignupSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(
        write_only=True, min_length=8, trim_whitespace=False
    )
    full_name = serializers.CharField(required=False, allow_blank=True, max_length=100)

    def validate_email(self, value):
        if User.objects.filter(admin_email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
