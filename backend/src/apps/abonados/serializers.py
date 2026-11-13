from rest_framework import serializers

from .models import Abonado, Persona, TipoAbonado, VinculoAbonado
from .servicio_completitud import calcular_completitud


class PersonaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Persona
        fields = ["id_persona", "nombre", "tipo_identificacion", "identificacion"]


class VinculoAbonadoSerializer(serializers.ModelSerializer):
    persona = PersonaSerializer()

    class Meta:
        model = VinculoAbonado
        fields = ["persona", "rol", "fecha_inicio", "fecha_fin"]


class AbonadoSerializer(serializers.ModelSerializer):
    sector = serializers.CharField(source="sector.nombre", default=None)
    titular_vigente = serializers.SerializerMethodField()
    completitud = serializers.SerializerMethodField()
    es_importado_pendiente = serializers.SerializerMethodField()
    fecha_importacion = serializers.SerializerMethodField()

    class Meta:
        model = Abonado
        fields = [
            "id_abonado",
            "numero_paja",
            "sector",
            "tipo_abonado",
            "estado",
            "fecha_baja",
            "titular_vigente",
            "completitud",
            "es_importado_pendiente",
            "fecha_importacion",
        ]

    def _vinculo_titular(self, abonado):
        """Memoizado en la propia instancia: PAN-06 modificar pide este
        vínculo tres veces (titular, es_importado_pendiente, fecha)."""

        if not hasattr(abonado, "_vinculo_titular_cache"):
            abonado._vinculo_titular_cache = (
                abonado.vinculos
                .filter(rol="TITULAR", fecha_fin__isnull=True)
                .select_related("persona")
                .first()
            )

        return abonado._vinculo_titular_cache

    def get_titular_vigente(self, abonado):
        vinculo = self._vinculo_titular(abonado)

        return PersonaSerializer(vinculo.persona).data if vinculo else None

    def get_completitud(self, abonado):
        """Q3 (RF-14): indicador breve para PAN-04; detalle en PAN-07."""

        return calcular_completitud(abonado)

    def get_es_importado_pendiente(self, abonado):
        """
        RF-04/PAN-06: banner de "abonado importado de SADA, pendiente"
        (decisión del 13/11/2026). Un abonado queda así mientras nadie
        complete el tipo (RF-21) y la identificación del titular (SADA
        nunca la exporta).
        """

        if abonado.tipo_abonado != TipoAbonado.PENDIENTE:
            return False

        vinculo = self._vinculo_titular(abonado)

        return vinculo is not None and vinculo.persona.identificacion is None

    def get_fecha_importacion(self, abonado):
        """
        `vinculo_abonado.fecha_inicio` del titular: coincide con el día
        de la importación (no hace falta una columna nueva ni consultar
        la bitácora para esto, ver el plan).
        """

        if not self.get_es_importado_pendiente(abonado):
            return None

        vinculo = self._vinculo_titular(abonado)

        return vinculo.fecha_inicio if vinculo else None
