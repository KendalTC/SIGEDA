"""
IBitacora (DAS v1.1): registra eventos en registro_bitacora. La
bitácora es de solo inserción (RNF-11, ADR-05): este módulo solo
inserta filas, nunca las edita ni las borra.
"""

from .models import AccionBitacora, OrigenBitacora, RegistroBitacora


def registrar(
    *,
    cuenta,
    accion: AccionBitacora,
    elemento_afectado: str,
    id_abonado: int | None = None,
) -> RegistroBitacora:
    """
    Inserta un evento de bitácora a nombre de `cuenta`. Debe llamarse
    dentro de la misma transacción que la operación que registra (ver
    `apps.documents.controlador.ControladorDocumentos`).
    """

    return RegistroBitacora.objects.create(
        cuenta=cuenta,
        id_abonado=id_abonado,
        accion=accion,
        elemento_afectado=elemento_afectado,
        origen=OrigenBitacora.USUARIA if cuenta else OrigenBitacora.SISTEMA,
    )


def registrar_modificaciones(registro_bitacora: RegistroBitacora, cambios: dict):
    """
    Agrega 1..* filas de detalle a `registro_modificacion` para un
    evento MODIFICACION o ANULACION ya creado. `cambios` es
    {"tabla.columna": (valor_anterior, valor_nuevo), ...}.
    """

    from .models import RegistroModificacion

    RegistroModificacion.objects.bulk_create(
        [
            RegistroModificacion(
                registro_bitacora=registro_bitacora,
                campo_modificado=campo,
                valor_anterior=str(anterior) if anterior is not None else None,
                valor_nuevo=str(nuevo) if nuevo is not None else None,
            )
            for campo, (anterior, nuevo) in cambios.items()
        ]
    )
