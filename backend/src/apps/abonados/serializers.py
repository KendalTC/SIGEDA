from rest_framework import serializers

from .models import Abonado, Persona, VinculoAbonado
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
        ]

    def get_titular_vigente(self, abonado):
        vinculo = (
            abonado.vinculos
            .filter(rol="TITULAR", fecha_fin__isnull=True)
            .select_related("persona")
            .first()
        )

        return PersonaSerializer(vinculo.persona).data if vinculo else None

    def get_completitud(self, abonado):
        """Q3 (RF-14): indicador breve para PAN-04; detalle en PAN-07."""

        return calcular_completitud(abonado)
