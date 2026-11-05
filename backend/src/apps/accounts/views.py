from django.contrib.auth import authenticate
from rest_framework import permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import ChangeOwnPasswordSerializer, UserSerializer


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(
            username=username,
            password=password,
        )

        if user is None:
            return Response(
                {"detail": "Credenciales inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=user)

        return Response(
            {
                "token": token.key,
                "user": UserSerializer(user).data,
            }
        )


class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        request.user.auth_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class ChangeOwnPasswordView(APIView):
    """
    Cambio de la propia contraseña. Devuelve un token nuevo para que la
    persona siga trabajando donde estaba, mientras cualquier otra sesión
    abierta con el token viejo queda cerrada.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangeOwnPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        if not user.check_password(
            serializer.validated_data["current_password"],
        ):
            return Response(
                {
                    "current_password": [
                        "La contraseña actual no es correcta.",
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(
            serializer.validated_data["new_password"],
        )
        user.save(update_fields=["password"])

        Token.objects.filter(user=user).delete()
        token = Token.objects.create(user=user)

        return Response({"token": token.key})
