from django.db import models
from django.db.models import CheckConstraint, Q

from apps.accounts.models import Cuenta


class TipoRespaldo(models.TextChoices):
    AUTOMATICO = "AUTOMATICO", "Automático"
    MANUAL = "MANUAL", "Manual"


class EstadoRespaldo(models.TextChoices):
    COMPLETO = "COMPLETO", "Completo"
    PENDIENTE = "PENDIENTE", "Pendiente"
    FALLIDO = "FALLIDO", "Fallido"


class DestinoCopiaRespaldo(models.TextChoices):
    DISCO_EXTERNO = "DISCO_EXTERNO", "Disco externo"
    ONEDRIVE = "ONEDRIVE", "OneDrive"


class EstadoCopiaRespaldo(models.TextChoices):
    PENDIENTE = "PENDIENTE", "Pendiente"
    VERIFICADA = "VERIFICADA", "Verificada"
    FALLIDA = "FALLIDA", "Fallida"


class Respaldo(models.Model):
    """
    Modelo ER v1.1: respaldo(id_respaldo, id_cuenta FK opc., fecha_hora,
    tipo CHECK, estado CHECK, nombre_paquete UQ opc., hash_sha256 opc.,
    tamano_bytes opc.). `estado` es un derivado guardado: COMPLETO ⇔
    existe una copia_respaldo VERIFICADA; lo mantiene la aplicación en
    la misma transacción que la copia (ver Modelo_Relacional_SIGEDA_v1.1_Contexto.md,
    desnormalización #3). Sin lógica todavía: modelado para el DDL
    completo del Avance de Construcción; se activa en Incremento 3.
    """

    id_respaldo = models.BigAutoField(primary_key=True)
    cuenta = models.ForeignKey(
        Cuenta,
        on_delete=models.RESTRICT,
        db_column="id_cuenta",
        null=True,
        blank=True,
        related_name="respaldos",
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=10, choices=TipoRespaldo.choices)
    estado = models.CharField(max_length=10, choices=EstadoRespaldo.choices)
    nombre_paquete = models.CharField(
        max_length=200, unique=True, null=True, blank=True,
    )
    hash_sha256 = models.CharField(max_length=64, null=True, blank=True)
    tamano_bytes = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "respaldo"
        ordering = ["-fecha_hora"]
        constraints = [
            CheckConstraint(
                condition=Q(tamano_bytes__isnull=True) | Q(tamano_bytes__gt=0),
                name="respaldo_tamano_bytes_positivo",
            ),
            CheckConstraint(
                condition=Q(tipo__in=TipoRespaldo.values),
                name="respaldo_tipo_dominio",
            ),
            CheckConstraint(
                condition=Q(estado__in=EstadoRespaldo.values),
                name="respaldo_estado_dominio",
            ),
        ]

    def __str__(self):
        return self.nombre_paquete or f"respaldo {self.id_respaldo}"


class CopiaRespaldo(models.Model):
    """
    Modelo ER v1.1: copia_respaldo(id_respaldo, destino PK compuesta,
    estado CHECK, fecha_hora_verificacion opc.). Como máximo 2 copias
    por respaldo (DISCO_EXTERNO y ONEDRIVE).
    """

    pk = models.CompositePrimaryKey("respaldo_id", "destino")
    respaldo = models.ForeignKey(
        Respaldo,
        on_delete=models.RESTRICT,
        db_column="id_respaldo",
        related_name="copias",
    )
    destino = models.CharField(
        max_length=20, choices=DestinoCopiaRespaldo.choices,
    )
    estado = models.CharField(max_length=10, choices=EstadoCopiaRespaldo.choices)
    fecha_hora_verificacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "copia_respaldo"
        ordering = ["respaldo_id", "destino"]
        constraints = [
            CheckConstraint(
                condition=Q(destino__in=DestinoCopiaRespaldo.values),
                name="copia_respaldo_destino_dominio",
            ),
            CheckConstraint(
                condition=Q(estado__in=EstadoCopiaRespaldo.values),
                name="copia_respaldo_estado_dominio",
            ),
        ]

    def __str__(self):
        return f"{self.respaldo_id} · {self.destino}"
