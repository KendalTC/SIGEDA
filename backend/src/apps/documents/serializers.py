from rest_framework import serializers

from .models import Documento, VersionDocumento


class VersionDocumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = VersionDocumento
        fields = [
            "numero_version",
            "nombre_original",
            "formato",
            "tamano_bytes",
            "fecha_documento",
            "fecha_carga",
            "hash_sha256",
        ]


class DocumentoExpedienteSerializer(serializers.ModelSerializer):
    tipo_documento = serializers.CharField(source="tipo_documento.nombre")
    prioridad = serializers.IntegerField(source="tipo_documento.prioridad")
    persona = serializers.CharField(source="persona.nombre", default=None)
    version_vigente = serializers.SerializerMethodField()
    numero_versiones = serializers.SerializerMethodField()
    aportante_titular_anterior = serializers.SerializerMethodField()

    class Meta:
        model = Documento
        fields = [
            "id_documento",
            "tipo_documento",
            "prioridad",
            "nombre_identificador",
            "persona",
            "estado",
            "motivo_anulacion",
            "fecha_anulacion",
            "version_vigente",
            "numero_versiones",
            "aportante_titular_anterior",
        ]

    def get_version_vigente(self, documento):
        version = documento.versiones.order_by("-numero_version").first()

        return VersionDocumentoSerializer(version).data if version else None

    def get_numero_versiones(self, documento):
        return documento.versiones.count()

    def get_aportante_titular_anterior(self, documento):
        """
        True si la persona que aportó el documento tuvo con este
        abonado un vínculo TITULAR ya cerrado (fecha_fin no nula). El
        contexto trae el conjunto de id_persona en esa situación,
        calculado una sola vez por expediente (ver `ExpedienteView`).
        """

        personas_titulares_anteriores = self.context.get(
            "personas_titulares_anteriores",
        ) or set()

        return documento.persona_id in personas_titulares_anteriores
