from django.db import models
from django.db.models import CheckConstraint, Q

from apps.abonados.models import Abonado, Persona
from apps.configuration.models import TipoDocumento


class EstadoDocumento(models.TextChoices):
    VIGENTE = "VIGENTE", "Vigente"
    ANULADO = "ANULADO", "Anulado"


class FormatoVersionDocumento(models.TextChoices):
    PDF = "PDF", "PDF"
    PNG = "PNG", "PNG"


class Documento(models.Model):
    """
    Modelo ER v1.1: documento(id_documento, id_abonado FK, id_tipo_documento
    FK, id_persona FK opc., nombre_identificador opc., estado CHECK,
    motivo_anulacion opc., fecha_anulacion opc.). No confundir con el
    resto de `apps.documents`, que todavía trae la generación de PDF de
    etiquetas/facturas heredada de LICS (`pdf.py`, `views.py`,
    `report_pdf.py`) — queda intacta hasta que se retiren las apps de
    negocio; este modelo es el único punto nuevo de esta app.
    """

    id_documento = models.BigAutoField(primary_key=True)
    abonado = models.ForeignKey(
        Abonado,
        on_delete=models.RESTRICT,
        db_column="id_abonado",
        related_name="documentos",
    )
    tipo_documento = models.ForeignKey(
        TipoDocumento,
        on_delete=models.RESTRICT,
        db_column="id_tipo_documento",
        related_name="documentos",
    )
    persona = models.ForeignKey(
        Persona,
        on_delete=models.RESTRICT,
        db_column="id_persona",
        null=True,
        blank=True,
        related_name="documentos_aportados",
    )
    nombre_identificador = models.CharField(
        max_length=200, null=True, blank=True,
    )
    estado = models.CharField(
        max_length=10,
        choices=EstadoDocumento.choices,
        default=EstadoDocumento.VIGENTE,
    )
    motivo_anulacion = models.TextField(null=True, blank=True)
    fecha_anulacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "documento"
        ordering = ["tipo_documento__prioridad", "tipo_documento__nombre", "id_documento"]
        constraints = [
            CheckConstraint(
                condition=(
                    Q(
                        estado=EstadoDocumento.ANULADO,
                        motivo_anulacion__isnull=False,
                        fecha_anulacion__isnull=False,
                    )
                    | Q(
                        estado=EstadoDocumento.VIGENTE,
                        motivo_anulacion__isnull=True,
                        fecha_anulacion__isnull=True,
                    )
                ),
                name="documento_anulado_tiene_motivo_y_fecha",
            ),
        ]

    def __str__(self):
        return self.nombre_identificador or f"documento {self.id_documento}"

    def obtener_version_vigente(self):
        return self.versiones.order_by("-numero_version").first()


class VersionDocumento(models.Model):
    """
    Modelo ER v1.1: version_documento(id_documento, numero_version PK
    compuesta; nombre_original, ruta_archivo UQ, formato CHECK,
    tamano_bytes > 0, fecha_documento, fecha_carga, hash_sha256).
    `ruta_archivo` es el nombre generado en el almacén cifrado (no
    revela abonado ni persona); `tamano_bytes` y `hash_sha256` se
    calculan sobre el archivo original, antes de cifrarlo (ver DAS
    v1.1, ADR-02).
    """

    pk = models.CompositePrimaryKey("documento_id", "numero_version")
    documento = models.ForeignKey(
        Documento,
        on_delete=models.RESTRICT,
        db_column="id_documento",
        related_name="versiones",
    )
    numero_version = models.PositiveIntegerField()
    nombre_original = models.CharField(max_length=255)
    ruta_archivo = models.CharField(max_length=255, unique=True)
    formato = models.CharField(
        max_length=5, choices=FormatoVersionDocumento.choices,
    )
    tamano_bytes = models.BigIntegerField()
    fecha_documento = models.DateField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
    hash_sha256 = models.CharField(max_length=64)

    class Meta:
        db_table = "version_documento"
        ordering = ["documento_id", "numero_version"]
        constraints = [
            CheckConstraint(
                condition=Q(formato__in=FormatoVersionDocumento.values),
                name="version_documento_formato_dominio",
            ),
            CheckConstraint(
                condition=Q(tamano_bytes__gt=0),
                name="version_documento_tamano_bytes_positivo",
            ),
        ]

    def __str__(self):
        return f"{self.documento_id} · v{self.numero_version}"
