from django.db import models
from django.db.models import CheckConstraint, Q

from apps.accounts.models import Cuenta


class AccionBitacora(models.TextChoices):
    CREACION = "CREACION", "Creación"
    MODIFICACION = "MODIFICACION", "Modificación"
    ANULACION = "ANULACION", "Anulación"
    CAMBIO_TITULAR = "CAMBIO_TITULAR", "Cambio de titular"
    BAJA = "BAJA", "Baja"
    REACTIVACION = "REACTIVACION", "Reactivación"
    IMPORTACION = "IMPORTACION", "Importación"
    EXPORTACION = "EXPORTACION", "Exportación"
    RESPALDO = "RESPALDO", "Respaldo"
    RESTAURACION = "RESTAURACION", "Restauración"
    RESTABLECIMIENTO_CONTRASENA = (
        "RESTABLECIMIENTO_CONTRASENA",
        "Restablecimiento de contraseña",
    )
    CUARENTENA = "CUARENTENA", "Cuarentena"


class OrigenBitacora(models.TextChoices):
    USUARIA = "USUARIA", "Usuaria"
    SISTEMA = "SISTEMA", "Sistema"


class RegistroBitacora(models.Model):
    """
    Modelo ER v1.1: registro_bitacora(id_registro_bitacora, id_cuenta
    FK opc., id_abonado referencia lógica SIN FK opc., fecha_hora,
    accion CHECK, elemento_afectado, origen CHECK). RNF-11: solo
    INSERT/SELECT para el usuario de BD de la aplicación (ver
    migración 0002 de esta app).
    """

    id_registro_bitacora = models.BigAutoField(primary_key=True)
    cuenta = models.ForeignKey(
        Cuenta,
        on_delete=models.RESTRICT,
        db_column="id_cuenta",
        null=True,
        blank=True,
        related_name="registros_bitacora",
    )
    # Referencia lógica a abonado.id_abonado, a propósito sin FK: un
    # abonado nunca se borra, pero la bitácora tampoco debe depender de
    # la existencia de la fila (ver Modelo_Relacional_SIGEDA_v1.1_Contexto.md).
    id_abonado = models.BigIntegerField(null=True, blank=True)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    accion = models.CharField(max_length=30, choices=AccionBitacora.choices)
    elemento_afectado = models.CharField(max_length=200)
    origen = models.CharField(max_length=10, choices=OrigenBitacora.choices)

    class Meta:
        db_table = "registro_bitacora"
        ordering = ["-fecha_hora", "-id_registro_bitacora"]
        constraints = [
            CheckConstraint(
                condition=(
                    Q(origen=OrigenBitacora.USUARIA, cuenta__isnull=False)
                    | Q(origen=OrigenBitacora.SISTEMA, cuenta__isnull=True)
                ),
                name="registro_bitacora_origen_usuaria_tiene_cuenta",
            ),
        ]

    def __str__(self):
        return f"{self.accion} · {self.elemento_afectado}"


class RegistroModificacion(models.Model):
    """
    Modelo ER v1.1: registro_modificacion(id_registro_bitacora,
    campo_modificado PK compuesta; valor_anterior/valor_nuevo opc.).
    1..* filas por evento MODIFICACION o ANULACION. campo_modificado
    usa el formato `tabla.columna`.
    """

    pk = models.CompositePrimaryKey("registro_bitacora_id", "campo_modificado")
    registro_bitacora = models.ForeignKey(
        RegistroBitacora,
        on_delete=models.RESTRICT,
        db_column="id_registro_bitacora",
        related_name="modificaciones",
    )
    campo_modificado = models.CharField(max_length=100)
    valor_anterior = models.TextField(null=True, blank=True)
    valor_nuevo = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "registro_modificacion"
        ordering = ["registro_bitacora_id", "campo_modificado"]

    def __str__(self):
        return self.campo_modificado


class RegistroRestauracion(models.Model):
    """
    Modelo ER v1.1: registro_restauracion(id_registro_bitacora PK
    FK→registro_bitacora, nombre_paquete, fecha_respaldo_restaurado).
    Exactamente 1 fila por evento RESTAURACION.
    """

    registro_bitacora = models.OneToOneField(
        RegistroBitacora,
        on_delete=models.RESTRICT,
        db_column="id_registro_bitacora",
        primary_key=True,
        related_name="restauracion",
    )
    nombre_paquete = models.CharField(max_length=200)
    fecha_respaldo_restaurado = models.DateTimeField()

    class Meta:
        db_table = "registro_restauracion"

    def __str__(self):
        return self.nombre_paquete
