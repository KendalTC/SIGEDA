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

from apps.abonados.models import Abonado, EstadoAbonado, RolVinculo, TipoAbonado, VinculoAbonado
from apps.configuration.models import GrupoAlternativas, TipoDocumento
from apps.documents.models import Documento, EstadoDocumento


def _personas_y_aportes(abonado):
    """
    (titular: VinculoAbonado|None, cotitulares: list[VinculoAbonado],
    aportes_vigentes: set[(id_tipo_documento, id_persona)]). Comparte
    la base de datos cruda entre `calcular_completitud` y
    `matriz_completitud` (PAN-07), sin duplicar la consulta.
    """

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

    return titular, cotitulares, aportes_vigentes


def _todo_el_catalogo():
    """
    (tipos_sueltos, grupos): TODO el catálogo, sin filtrar por
    tipo_abonado. El catálogo es chico (una quincena de tipos, un
    puñado de grupos — RF-09), así que traerlo completo una sola vez y
    filtrar en memoria por `tipo_abonado` es más barato que repetir la
    consulta filtrada por cada abonado (ver `_requisitos_aplicables_de`).
    """

    tipos_sueltos = list(TipoDocumento.objects.filter(grupo_alternativas__isnull=True))
    grupos = list(
        GrupoAlternativas.objects.prefetch_related("tipos_documento"),
    )

    return tipos_sueltos, grupos


def _requisitos_aplicables_de(tipo_abonado, todos_tipos_sueltos, todos_grupos):
    """Filtra el catálogo completo (ya traído de la base) a lo aplicable
    a `tipo_abonado` (obligatoriedad propia o AMBAS)."""

    tipos_sueltos = [
        t for t in todos_tipos_sueltos
        if t.obligatoriedad in (tipo_abonado, "AMBAS")
    ]
    grupos = [
        g for g in todos_grupos
        if g.obligatoriedad in (tipo_abonado, "AMBAS")
    ]

    return tipos_sueltos, grupos


def _requisitos_aplicables(abonado):
    """(tipos_sueltos: list[TipoDocumento], grupos: list[GrupoAlternativas])
    aplicables a `abonado.tipo_abonado` (obligatoriedad propia o AMBAS).
    Para un solo abonado (PAN-04, PAN-07 detalle) — para listas de
    muchos abonados (PAN-07 panel) usar `_todo_el_catalogo` +
    `_requisitos_aplicables_de` una sola vez, ver `resumen_completitud_global`."""

    todos_tipos_sueltos, todos_grupos = _todo_el_catalogo()

    return _requisitos_aplicables_de(abonado.tipo_abonado, todos_tipos_sueltos, todos_grupos)


def _calcular_faltantes(titular, cotitulares, aportes_vigentes, tipos_sueltos, grupos) -> list[str]:
    faltantes = []

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

    return faltantes


def calcular_completitud(abonado) -> dict:
    """{"completo": bool, "faltantes": [str, ...]}"""

    titular, cotitulares, aportes_vigentes = _personas_y_aportes(abonado)
    tipos_sueltos, grupos = _requisitos_aplicables(abonado)
    faltantes = _calcular_faltantes(titular, cotitulares, aportes_vigentes, tipos_sueltos, grupos)

    return {"completo": len(faltantes) == 0, "faltantes": faltantes}


def matriz_completitud(abonado) -> list[dict]:
    """
    PAN-07 (vista detalle): una fila por tipo/grupo aplicable a este
    abonado, con una columna por persona vigente relevante (titular y
    cotitulares) marcando si aporta o no el documento. `aplica=False`
    marca una columna que no corresponde (p. ej. un tipo que no se
    exige a cotitulares, para una columna de cotitular).
    """

    titular, cotitulares, aportes_vigentes = _personas_y_aportes(abonado)
    tipos_sueltos, grupos = _requisitos_aplicables(abonado)

    personas_columna = []

    if titular is not None:
        personas_columna.append(("titular", titular))

    for cotitular in cotitulares:
        personas_columna.append(("cotitular", cotitular))

    def _fila(nombre, es_grupo, ids_tipos, exigido_a_cotitulares):
        columnas = []

        for rol_etiqueta, vinculo in personas_columna:
            aplica = rol_etiqueta == "titular" or exigido_a_cotitulares
            tiene_documento = (
                any(
                    (id_tipo, vinculo.persona_id) in aportes_vigentes
                    for id_tipo in ids_tipos
                )
                if aplica
                else None
            )
            columnas.append(
                {
                    "id_persona": vinculo.persona_id,
                    "nombre": vinculo.persona.nombre,
                    "rol": rol_etiqueta,
                    "aplica": aplica,
                    "tiene_documento": tiene_documento,
                },
            )

        return {"nombre": nombre, "es_grupo": es_grupo, "columnas": columnas}

    filas = [
        _fila(
            tipo.nombre, False,
            [tipo.id_tipo_documento], tipo.es_exigido_a_cotitulares,
        )
        for tipo in tipos_sueltos
    ]

    for grupo in grupos:
        tipos_del_grupo = list(grupo.tipos_documento.all())
        ids_tipos_del_grupo = [t.id_tipo_documento for t in tipos_del_grupo]
        exigido_a_cotitulares = any(
            t.es_exigido_a_cotitulares for t in tipos_del_grupo
        )
        filas.append(
            _fila(grupo.nombre, True, ids_tipos_del_grupo, exigido_a_cotitulares),
        )

    return filas


def _contexto_lote(ids_abonado: list[int]):
    """
    Trae, en 2 consultas (sin importar cuántos abonados sean), lo que
    `_personas_y_aportes` trae en 2 consultas POR abonado: evita el
    N+1 real que hacía tardar ~10s el panel de completitud con los
    ~1015 abonados reales (visto al verificar PAN-07 — antes de este
    fix, `resumen_completitud_global`/`listar_incompletos` llamaban
    `calcular_completitud` abonado por abonado).

    Devuelve (vinculos_por_abonado, aportes_por_abonado):
    - vinculos_por_abonado[id_abonado] -> list[VinculoAbonado] vigentes
      (sin APODERADA), igual que arma `_personas_y_aportes`.
    - aportes_por_abonado[id_abonado] -> set[(id_tipo_documento, id_persona)]
      de documentos VIGENTE de ese abonado (superconjunto de
      `aportes_vigentes`: incluye aportes de cualquier persona, no solo
      las relevantes, pero como `_calcular_faltantes` solo consulta
      pares (tipo, persona) de titular/cotitulares vigentes, el
      resultado es idéntico al filtrado estricto original).
    """

    vinculos_por_abonado: dict[int, list] = {i: [] for i in ids_abonado}

    for vinculo in (
        VinculoAbonado.objects
        .filter(abonado_id__in=ids_abonado, fecha_fin__isnull=True)
        .exclude(rol=RolVinculo.APODERADA)
        .select_related("persona")
    ):
        vinculos_por_abonado[vinculo.abonado_id].append(vinculo)

    aportes_por_abonado: dict[int, set] = {i: set() for i in ids_abonado}

    for id_abonado, id_tipo_documento, id_persona in (
        Documento.objects
        .filter(abonado_id__in=ids_abonado, estado=EstadoDocumento.VIGENTE)
        .values_list("abonado_id", "tipo_documento_id", "persona_id")
    ):
        aportes_por_abonado[id_abonado].add((id_tipo_documento, id_persona))

    return vinculos_por_abonado, aportes_por_abonado


def _faltantes_con_contexto(abonado, vinculos, aportes_vigentes, cache_catalogo) -> list[str]:
    titular = next((v for v in vinculos if v.rol == RolVinculo.TITULAR), None)
    cotitulares = [v for v in vinculos if v.rol == RolVinculo.COTITULAR]

    if "_todos" not in cache_catalogo:
        cache_catalogo["_todos"] = _todo_el_catalogo()

    if abonado.tipo_abonado not in cache_catalogo:
        todos_tipos_sueltos, todos_grupos = cache_catalogo["_todos"]
        cache_catalogo[abonado.tipo_abonado] = _requisitos_aplicables_de(
            abonado.tipo_abonado, todos_tipos_sueltos, todos_grupos,
        )

    tipos_sueltos, grupos = cache_catalogo[abonado.tipo_abonado]

    return _calcular_faltantes(titular, cotitulares, aportes_vigentes, tipos_sueltos, grupos)


def resumen_completitud_global(filtros=None) -> dict:
    """
    {"completos", "incompletos", "tipo_pendiente", "total_activos",
    "avance_pct"}, sobre abonados ACTIVOS (los de baja no cuentan,
    RF-14). `filtros`: {"id_sector"?, "tipo_abonado"?}.
    """

    filtros = filtros or {}
    queryset = Abonado.objects.filter(estado=EstadoAbonado.ACTIVO)

    if filtros.get("id_sector"):
        queryset = queryset.filter(sector_id=filtros["id_sector"])

    if filtros.get("tipo_abonado"):
        queryset = queryset.filter(tipo_abonado=filtros["tipo_abonado"])

    abonados = list(queryset)
    vinculos_por_abonado, aportes_por_abonado = _contexto_lote(
        [a.id_abonado for a in abonados],
    )
    cache_catalogo: dict = {}

    completos = 0
    incompletos = 0
    tipo_pendiente = 0

    for abonado in abonados:
        if abonado.tipo_abonado == TipoAbonado.PENDIENTE:
            tipo_pendiente += 1
            continue

        faltantes = _faltantes_con_contexto(
            abonado,
            vinculos_por_abonado[abonado.id_abonado],
            aportes_por_abonado[abonado.id_abonado],
            cache_catalogo,
        )

        if not faltantes:
            completos += 1
        else:
            incompletos += 1

    total_activos = completos + incompletos + tipo_pendiente
    avance_pct = (
        round((completos / total_activos) * 100, 1) if total_activos else 0.0
    )

    return {
        "completos": completos,
        "incompletos": incompletos,
        "tipo_pendiente": tipo_pendiente,
        "total_activos": total_activos,
        "avance_pct": avance_pct,
    }


def listar_incompletos(filtros=None) -> list[dict]:
    """
    Abonados ACTIVOS e INCOMPLETOS (nunca PENDIENTE: ningún tipo/grupo
    tiene obligatoriedad PENDIENTE, así que nunca saldrían incompletos
    de verdad). `filtros`: {"id_sector"?, "tipo_abonado"?,
    "documento_faltante"?} — el último se aplica después de calcular,
    porque es derivado (no es una columna de `abonado`).
    """

    filtros = filtros or {}
    queryset = (
        Abonado.objects
        .filter(estado=EstadoAbonado.ACTIVO)
        .exclude(tipo_abonado=TipoAbonado.PENDIENTE)
        .select_related("sector")
    )

    if filtros.get("id_sector"):
        queryset = queryset.filter(sector_id=filtros["id_sector"])

    if filtros.get("tipo_abonado"):
        queryset = queryset.filter(tipo_abonado=filtros["tipo_abonado"])

    documento_faltante = filtros.get("documento_faltante")
    abonados = list(queryset)
    vinculos_por_abonado, aportes_por_abonado = _contexto_lote(
        [a.id_abonado for a in abonados],
    )
    cache_catalogo: dict = {}
    resultados = []

    for abonado in abonados:
        vinculos = vinculos_por_abonado[abonado.id_abonado]
        faltantes = _faltantes_con_contexto(
            abonado, vinculos, aportes_por_abonado[abonado.id_abonado], cache_catalogo,
        )

        if not faltantes:
            continue

        if documento_faltante and not any(
            faltante.startswith(documento_faltante) for faltante in faltantes
        ):
            continue

        titular = next((v for v in vinculos if v.rol == RolVinculo.TITULAR), None)

        resultados.append(
            {
                "numero_paja": abonado.numero_paja,
                "titular_vigente": titular.persona.nombre if titular else None,
                "sector": abonado.sector.nombre if abonado.sector else None,
                "tipo_abonado": abonado.tipo_abonado,
                "faltantes": faltantes,
            },
        )

    return resultados


def listar_tipo_pendiente(filtros=None) -> list[dict]:
    """
    Abonados con `tipo_abonado=PENDIENTE` y `estado=ACTIVO` (RF-04),
    con la fecha del vínculo TITULAR vigente — mismo campo que usa el
    banner de "importado, pendiente" de `ModificarAbonadoView`
    (`apps/abonados/views.py`).
    """

    filtros = filtros or {}
    queryset = Abonado.objects.filter(
        estado=EstadoAbonado.ACTIVO, tipo_abonado=TipoAbonado.PENDIENTE,
    )

    if filtros.get("id_sector"):
        queryset = queryset.filter(sector_id=filtros["id_sector"])

    abonados = list(queryset)
    titulares_por_abonado: dict[int, object] = {}

    for vinculo in (
        VinculoAbonado.objects
        .filter(
            abonado_id__in=[a.id_abonado for a in abonados],
            rol=RolVinculo.TITULAR,
            fecha_fin__isnull=True,
        )
        .select_related("persona")
    ):
        titulares_por_abonado[vinculo.abonado_id] = vinculo

    resultados = []

    for abonado in abonados:
        vinculo_titular = titulares_por_abonado.get(abonado.id_abonado)

        resultados.append(
            {
                "numero_paja": abonado.numero_paja,
                "titular_vigente": (
                    vinculo_titular.persona.nombre if vinculo_titular else None
                ),
                "fecha_inicio": (
                    vinculo_titular.fecha_inicio if vinculo_titular else None
                ),
            },
        )

    return resultados
