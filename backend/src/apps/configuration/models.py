from django.db import models
from django.db.models import CheckConstraint, Q


class ObligatoriedadGrupo(models.TextChoices):
    """grupo_alternativas.obligatoriedad: sin NINGUNA (obs. 12 del Modelo ER)."""

    PERSONA_FISICA = "PERSONA_FISICA", "Persona física"
    PERSONA_JURIDICA = "PERSONA_JURIDICA", "Persona jurídica"
    AMBAS = "AMBAS", "Ambas"


class ObligatoriedadTipoDocumento(models.TextChoices):
    PERSONA_FISICA = "PERSONA_FISICA", "Persona física"
    PERSONA_JURIDICA = "PERSONA_JURIDICA", "Persona jurídica"
    AMBAS = "AMBAS", "Ambas"
    NINGUNA = "NINGUNA", "Ninguna"


class GrupoAlternativas(models.Model):
    """
    Modelo ER v1.1: grupo_alternativas(id_grupo_alternativas, nombre
    UQ, obligatoriedad CHECK). Un grupo agrupa 2 o más tipos de
    documento donde basta con aportar uno de ellos (CU-09); esa regla
    de "2 o más" la valida la aplicación, no la base de datos.
    """

    id_grupo_alternativas = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=150, unique=True)
    obligatoriedad = models.CharField(
        max_length=20,
        choices=ObligatoriedadGrupo.choices,
    )

    class Meta:
        db_table = "grupo_alternativas"
        ordering = ["nombre"]
        constraints = [
            CheckConstraint(
                condition=Q(obligatoriedad__in=ObligatoriedadGrupo.values),
                name="grupo_alternativas_obligatoriedad_dominio",
            ),
        ]

    def __str__(self):
        return self.nombre


class TipoDocumento(models.Model):
    """
    Modelo ER v1.1: tipo_documento(id_tipo_documento, id_grupo_alternativas
    FK opc., nombre UQ, prioridad > 0, obligatoriedad CHECK opc.,
    es_exigido_a_cotitulares). Tiene grupo u obligatoriedad, nunca las
    dos ni ninguna.
    """

    id_tipo_documento = models.BigAutoField(primary_key=True)
    grupo_alternativas = models.ForeignKey(
        GrupoAlternativas,
        on_delete=models.RESTRICT,
        db_column="id_grupo_alternativas",
        null=True,
        blank=True,
        related_name="tipos_documento",
    )
    nombre = models.CharField(max_length=150, unique=True)
    prioridad = models.PositiveSmallIntegerField()
    obligatoriedad = models.CharField(
        max_length=20,
        choices=ObligatoriedadTipoDocumento.choices,
        null=True,
        blank=True,
    )
    es_exigido_a_cotitulares = models.BooleanField(default=False)

    class Meta:
        db_table = "tipo_documento"
        ordering = ["prioridad", "nombre"]
        constraints = [
            CheckConstraint(
                condition=(
                    Q(grupo_alternativas__isnull=False, obligatoriedad__isnull=True)
                    | Q(grupo_alternativas__isnull=True, obligatoriedad__isnull=False)
                ),
                name="tipo_documento_grupo_xor_obligatoriedad",
            ),
            CheckConstraint(
                condition=Q(prioridad__gt=0),
                name="tipo_documento_prioridad_positiva",
            ),
            CheckConstraint(
                condition=(
                    Q(obligatoriedad__isnull=True)
                    | Q(obligatoriedad__in=ObligatoriedadTipoDocumento.values)
                ),
                name="tipo_documento_obligatoriedad_dominio",
            ),
        ]

    def __str__(self):
        return self.nombre
