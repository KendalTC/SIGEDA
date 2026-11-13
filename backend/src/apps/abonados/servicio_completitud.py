"""
Q3 (RF-14): completitud del expediente de un abonado. Lo usa hoy el
indicador breve de PAN-04 ("Incompleto · faltan N"); la pantalla
completa (PAN-07) es del Incremento 4 y reutilizará este mismo
servicio.

Regla (Modelo ER v1.1 + RF-14):
- Para cada `tipo_documento` sin grupo (suelto) cuya `obligatoriedad`
  sea `abonado.tipo_abonado` o `AMBAS`, hace falta un `documento`
  VIGENTE de ese tipo aportado por el titular vigente; si además
  `es_exigido_a_cotitulares=True`, hace falta uno por cada cotitular
  vigente.
- Para cada `grupo_alternativas` cuya `obligatoriedad` sea
  `abonado.tipo_abonado` o `AMBAS`, basta con que al menos uno de sus
  tipos tenga documento VIGENTE del titular (ídem cotitulares, si
  algún tipo del grupo trae `es_exigido_a_cotitulares=True`).

Solo cuentan documentos VIGENTE aportados por el titular vigente o por
cotitulares vigentes (RF-14): nunca por la persona apoderada ni por
titulares anteriores. `abonado.tipo_abonado = PENDIENTE` no necesita
caso especial: naturalmente solo le aplican los tipos/grupos con
obligatoriedad AMBAS (ningún tipo tiene obligatoriedad PENDIENTE).
"""

from apps.abonados.models import RolVinculo, VinculoAbonado
from apps.configuration.models import GrupoAlternativas, TipoDocumento
from apps.documents.models import Documento, EstadoDocumento


def calcular_completitud(abonado) -> dict:
    """{"completo": bool, "faltantes": [str, ...]}"""

    vinculos_vigentes = list(
        VinculoAbonado.objects
        .filter(abonado=abonado, fecha_fin__isnull=True)
        .exclude(rol=RolVinculo.APODERADA)
        .select_related("persona")
    )

    titular = next(
        (v for v in vinculos_vigentes if v.rol == RolVinculo.TITULAR), None,
    )
    cotitulares = [v for v in vinculos_vigentes if v.rol == RolVinculo.COTITULAR]

    personas_relevantes_ids = {v.persona_id for v in vinculos_vigentes}

    aportes_vigentes = set(
        Documento.objects.filter(
            abonado=abonado,
            estado=EstadoDocumento.VIGENTE,
            persona_id__in=personas_relevantes_ids,
        ).values_list("tipo_documento_id", "persona_id")
    )

    faltantes = []

    tipos_sueltos = TipoDocumento.objects.filter(
        grupo_alternativas__isnull=True,
        obligatoriedad__in=[abonado.tipo_abonado, "AMBAS"],
    )

    for tipo in tipos_sueltos:
        if titular is not None and (
            tipo.id_tipo_documento, titular.persona_id,
        ) not in aportes_vigentes:
            faltantes.append(f"{tipo.nombre} (titular)")

        if tipo.es_exigido_a_cotitulares:
            for cotitular in cotitulares:
                if (
                    tipo.id_tipo_documento, cotitular.persona_id,
                ) not in aportes_vigentes:
                    faltantes.append(
                        f"{tipo.nombre} del cotitular {cotitular.persona.nombre}",
                    )

    grupos = (
        GrupoAlternativas.objects
        .filter(obligatoriedad__in=[abonado.tipo_abonado, "AMBAS"])
        .prefetch_related("tipos_documento")
    )

    for grupo in grupos:
        tipos_del_grupo = list(grupo.tipos_documento.all())
        ids_tipos_del_grupo = [t.id_tipo_documento for t in tipos_del_grupo]
        exigido_a_cotitulares = any(
            t.es_exigido_a_cotitulares for t in tipos_del_grupo
        )

        if titular is not None and not any(
            (id_tipo, titular.persona_id) in aportes_vigentes
            for id_tipo in ids_tipos_del_grupo
        ):
            faltantes.append(f"{grupo.nombre} (titular)")

        if exigido_a_cotitulares:
            for cotitular in cotitulares:
                if not any(
                    (id_tipo, cotitular.persona_id) in aportes_vigentes
                    for id_tipo in ids_tipos_del_grupo
                ):
                    faltantes.append(
                        f"{grupo.nombre} del cotitular {cotitular.persona.nombre}",
                    )

    return {"completo": len(faltantes) == 0, "faltantes": faltantes}
