import secrets

from django.db import models
from django.db.models import CheckConstraint, Q


class PerfilCuenta(models.TextChoices):
    SECRETARIA = "SECRETARIA", "Secretaría"
    ADMINISTRADORA = "ADMINISTRADORA", "Administración"


class Cuenta(models.Model):
    """
    Modelo ER v1.1: cuenta(id_cuenta, usuario UQ, hash_contrasena,
    perfil CHECK, intentos_fallidos >= 0, bloqueada_hasta opc.,
    es_contrasena_temporal). Es el modelo de autenticación propio de
    SIGEDA (RF-01, RNF-09): no reemplaza ni toca el `auth.User` que
    todavía usan las apps de negocio heredadas de LICS (apps.sales,
    apps.customers, etc.), que siguen intactas hasta que se retiren.

    `hash_contrasena` usa los mismos hashers de contraseña de Django
    (`django.contrib.auth.hashers`), que no dependen de AUTH_USER_MODEL.
    """

    id_cuenta = models.BigAutoField(primary_key=True)
    usuario = models.CharField(max_length=50, unique=True)
    hash_contrasena = models.CharField(max_length=255)
    perfil = models.CharField(max_length=20, choices=PerfilCuenta.choices)
    intentos_fallidos = models.PositiveSmallIntegerField(default=0)
    bloqueada_hasta = models.DateTimeField(null=True, blank=True)
    es_contrasena_temporal = models.BooleanField(default=False)

    class Meta:
        db_table = "cuenta"
        ordering = ["usuario"]
        constraints = [
            CheckConstraint(
                condition=Q(intentos_fallidos__gte=0),
                name="cuenta_intentos_fallidos_no_negativos",
            ),
            CheckConstraint(
                condition=Q(perfil__in=PerfilCuenta.values),
                name="cuenta_perfil_dominio",
            ),
        ]

    def __str__(self):
        return self.usuario


def _generar_token() -> str:
    return secrets.token_hex(32)


class TokenCuenta(models.Model):
    """
    Token de sesión de `Cuenta`. NO es una tabla del Modelo ER v1.1: es
    plomería de autenticación propia de SIGEDA, igual que
    `rest_framework.authtoken.Token` lo es para `auth.User` en el resto
    de LICS. Por eso no lleva `db_table` fijado a un nombre del modelo.
    """

    key = models.CharField(max_length=64, primary_key=True, default=_generar_token)
    cuenta = models.OneToOneField(
        Cuenta, on_delete=models.CASCADE, related_name="token",
    )
    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"token de {self.cuenta.usuario}"
