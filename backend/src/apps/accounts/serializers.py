from django.contrib.auth.models import Group, User
from rest_framework import serializers

from apps.core.permissions import ROLE_ADMIN


class UserSerializer(serializers.ModelSerializer):
    groups = serializers.SlugRelatedField(
        many=True,
        slug_field="name",
        queryset=Group.objects.all(),
    )

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "is_staff",
            "is_superuser",
            "groups",
        )
        read_only_fields = (
            "is_superuser",
        )

    def validate(self, attrs):
        request = self.context.get("request")

        if (
            self.instance is not None
            and request is not None
            and self.instance == request.user
        ):
            if attrs.get("is_active") is False:
                raise serializers.ValidationError(
                    {
                        "is_active": [
                            "No puede desactivar su propio usuario.",
                        ]
                    }
                )

            if (
                self.instance.is_staff
                and attrs.get("is_staff") is False
            ):
                raise serializers.ValidationError(
                    {
                        "is_staff": [
                            "No puede quitarse su propio acceso administrativo (is_staff).",
                        ]
                    }
                )

            groups = attrs.get("groups")

            if (
                groups is not None
                and self.instance.groups.filter(name=ROLE_ADMIN).exists()
                and not any(group.name == ROLE_ADMIN for group in groups)
            ):
                raise serializers.ValidationError(
                    {
                        "groups": [
                            "No puede quitarse su propio rol de administrador.",
                        ]
                    }
                )

        return attrs


class ChangeOwnPasswordSerializer(serializers.Serializer):
    """
    Cambio de la propia contraseña: exige la actual para que nadie pueda
    cambiarla desde una sesión que quedó abierta.
    """

    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
