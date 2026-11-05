from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeOperators
from django.db import models
from django.db.models import CheckConstraint, F, Func, Q, UniqueConstraint, Value


class TipoAbonado(models.TextChoices):
    PERSONA_FISICA = "PERSONA_FISICA", "Persona física"
    PERSONA_JURIDICA = "PERSONA_JURIDICA", "Persona jurídica"
    PENDIENTE = "PENDIENTE", "Pendiente"


class EstadoAbonado(models.TextChoices):
    ACTIVO = "ACTIVO", "Activo"
    DE_BAJA = "DE_BAJA", "De baja"


class TipoIdentificacion(models.TextChoices):
    CEDULA_FISICA = "CEDULA_FISICA", "Cédula física"
    CEDULA_JURIDICA = "CEDULA_JURIDICA", "Cédula jurídica"
    DIMEX = "DIMEX", "DIMEX"
    PASAPORTE = "PASAPORTE", "Pasaporte"


class RolVinculo(models.TextChoices):
    TITULAR = "TITULAR", "Titular"
    COTITULAR = "COTITULAR", "Cotitular"
    APODERADA = "APODERADA", "Persona apoderada"


class Sector(models.Model):
    """Modelo ER v1.1: sector(id_sector, nombre UQ)."""

    id_sector = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "sector"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Abonado(models.Model):
    """
    Modelo ER v1.1: abonado(id_abonado, numero_paja UQ, id_sector FK
    opc., tipo_abonado CHECK, estado CHECK, fecha_baja opc.).
    """

    id_abonado = models.BigAutoField(primary_key=True)
    numero_paja = models.CharField(max_length=20, unique=True)
    sector = models.ForeignKey(
        Sector,
        on_delete=models.RESTRICT,
        db_column="id_sector",
        null=True,
        blank=True,
        related_name="abonados",
    )
    tipo_abonado = models.CharField(
        max_length=20,
        choices=TipoAbonado.choices,
    )
    estado = models.CharField(
        max_length=10,
        choices=EstadoAbonado.choices,
        default=EstadoAbonado.ACTIVO,
    )
    fecha_baja = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "abonado"
        ordering = ["numero_paja"]
        constraints = [
            CheckConstraint(
                condition=(
                    Q(estado=EstadoAbonado.DE_BAJA, fecha_baja__isnull=False)
                    | Q(estado=EstadoAbonado.ACTIVO, fecha_baja__isnull=True)
                ),
                name="abonado_de_baja_tiene_fecha_baja",
            ),
        ]

    def __str__(self):
        return self.numero_paja


class Persona(models.Model):
    """
    Modelo ER v1.1: persona(id_persona, nombre, tipo_identificacion
    CHECK opc., identificacion opc.). Decisión del 04/11/2026: sin
    id_persona_fusionada_en (la fusión queda como mejora futura).
    """

    id_persona = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    tipo_identificacion = models.CharField(
        max_length=20,
        choices=TipoIdentificacion.choices,
        null=True,
        blank=True,
    )
    identificacion = models.CharField(
        max_length=20,
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "persona"
        ordering = ["nombre"]
        constraints = [
            CheckConstraint(
                condition=(
                    Q(tipo_identificacion__isnull=True, identificacion__isnull=True)
                    | Q(tipo_identificacion__isnull=False, identificacion__isnull=False)
                ),
                name="persona_identificacion_completa_o_vacia",
            ),
            UniqueConstraint(
                fields=["tipo_identificacion", "identificacion"],
                condition=Q(
                    tipo_identificacion__isnull=False,
                    identificacion__isnull=False,
                ),
                name="persona_identificacion_unica",
            ),
        ]

    def __str__(self):
        return self.nombre


class VinculoAbonado(models.Model):
    """
    Modelo ER v1.1: vinculo_abonado(id_abonado, id_persona, fecha_inicio
    PK compuesta; rol CHECK; fecha_fin opc.). RN-02: un solo titular
    vigente por abonado. Requiere la extensión btree_gist (ver
    migración 0002).
    """

    pk = models.CompositePrimaryKey("abonado_id", "persona_id", "fecha_inicio")
    abonado = models.ForeignKey(
        Abonado,
        on_delete=models.RESTRICT,
        db_column="id_abonado",
        related_name="vinculos",
    )
    persona = models.ForeignKey(
        Persona,
        on_delete=models.RESTRICT,
        db_column="id_persona",
        related_name="vinculos",
    )
    fecha_inicio = models.DateField()
    rol = models.CharField(max_length=10, choices=RolVinculo.choices)
    fecha_fin = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "vinculo_abonado"
        ordering = ["abonado_id", "fecha_inicio"]
        constraints = [
            CheckConstraint(
                condition=(
                    Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=F("fecha_inicio"))
                ),
                name="vinculo_abonado_fecha_fin_no_anterior",
            ),
            UniqueConstraint(
                fields=["abonado"],
                condition=Q(rol=RolVinculo.TITULAR, fecha_fin__isnull=True),
                name="vinculo_abonado_un_titular_vigente",
            ),
            UniqueConstraint(
                fields=["abonado", "persona"],
                condition=Q(fecha_fin__isnull=True),
                name="vinculo_abonado_persona_vigente_unica",
            ),
            ExclusionConstraint(
                name="vinculo_abonado_sin_solape_pareja",
                expressions=[
                    ("abonado", RangeOperators.EQUAL),
                    ("persona", RangeOperators.EQUAL),
                    (
                        Func(
                            F("fecha_inicio"),
                            F("fecha_fin"),
                            Value("[)"),
                            function="daterange",
                            output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
            ),
            ExclusionConstraint(
                name="vinculo_abonado_sin_solape_titular",
                expressions=[
                    ("abonado", RangeOperators.EQUAL),
                    (
                        Func(
                            F("fecha_inicio"),
                            F("fecha_fin"),
                            Value("[)"),
                            function="daterange",
                            output_field=DateRangeField(),
                        ),
                        RangeOperators.OVERLAPS,
                    ),
                ],
                condition=Q(rol=RolVinculo.TITULAR),
            ),
        ]

    def __str__(self):
        return f"{self.abonado_id} · {self.persona_id} · {self.rol}"
