import {
  ApiError,
  ApiNetworkError,
  ApiTimeoutError,
  getApiErrorMessage,
} from "@/lib/api/errors";

import type {
  AgregarPersonaDatos,
  AltaAbonadoDatos,
  ArchivoCuarentena,
  CambiarTitularDatos,
  CargaDocumentosError,
  CargaDocumentosExito,
  ContrasenaTemporalGenerada,
  CriteriosBusqueda,
  Cuenta,
  DatosGrupoAlternativas,
  DatosPruebaRestauracion,
  DatosRestaurar,
  DatosTipoDocumento,
  DetalleCompletitud,
  Expediente,
  FiltrosBitacora,
  FiltrosCompletitud,
  FiltrosExpediente,
  GrupoAlternativas,
  MetadatoArchivo,
  ModificarAbonadoDatos,
  OtraCuenta,
  PersonaBusqueda,
  PersonaExistenteConflicto,
  PersonaReferencia,
  PruebaRestauracion,
  Respaldo,
  RespuestaBitacora,
  RespuestaBusqueda,
  RespuestaCompletitud,
  RespuestaRespaldos,
  ResultadoExportacion,
  ResultadoImportacion,
  SectorCatalogo,
  TipoDocumentoAdmin,
  TipoDocumentoCatalogo,
  VistaPreviaImportacion,
} from "./types";
import { borrarSesionLocal } from "./sesion-storage";

const TIMEOUT_MS = 20_000;

/**
 * RNF-09: si el servidor ya cerró la sesión por inactividad (o el
 * token ya no es válido por cualquier otro motivo), `AutenticacionCuenta`
 * lanza `AuthenticationFailed`, que DRF convierte en **403** (no 401)
 * porque ese autenticador no define `authenticate_header()` —
 * convención ya existente en el proyecto, confirmada con el agente de
 * backend. Acá se limpia la sesión guardada y se manda a la usuaria
 * de vuelta a iniciar sesión, sin esperar a que el vigilante del
 * cliente lo note (p. ej. la laptop estuvo suspendida más de 15
 * minutos).
 *
 * SUPUESTO: por ahora cualquier 403 en una llamada con `token` se
 * trata como sesión vencida, porque las dos cuentas tienen los mismos
 * permisos (RN-09) y hoy no hay ningún endpoint que devuelva 403 por
 * un permiso denegado de verdad. Si un incremento futuro agrega uno
 * (p. ej. restaurar respaldos, exclusivo de Administración, según la
 * excepción propuesta a RN-09), esta regla habrá que afinarla para no
 * confundir "permiso denegado" con "sesión vencida".
 */
function manejarSesionExpirada(): void {
  borrarSesionLocal();

  if (typeof window !== "undefined") {
    window.location.assign("/sigeda/login");
  }
}

async function sigedaFetch<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token, headers, ...rest } = options;
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), TIMEOUT_MS);

  const requestHeaders = new Headers(headers);
  requestHeaders.set("Accept", "application/json");

  if (token) {
    requestHeaders.set("Authorization", `Bearer ${token}`);
  }

  try {
    const response = await fetch(path, {
      ...rest,
      headers: requestHeaders,
      credentials: "same-origin",
      signal: controller.signal,
    });

    const contentType = response.headers.get("content-type") ?? "";
    const payload =
      response.status === 204
        ? null
        : contentType.includes("application/json")
          ? await response.json()
          : await response.text();

    if (!response.ok) {
      if (response.status === 403 && token) {
        manejarSesionExpirada();
      }

      throw new ApiError({
        message: getApiErrorMessage(payload),
        status: response.status,
        payload,
      });
    }

    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) {
      throw error;
    }

    if (error instanceof DOMException && error.name === "AbortError") {
      throw new ApiTimeoutError();
    }

    throw new ApiNetworkError();
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

export function sigedaLogin(usuario: string, contrasena: string) {
  return sigedaFetch<{ token: string; cuenta: Cuenta }>(
    "/api/sigeda/auth/login/",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ usuario, contrasena }),
    },
  );
}

export function sigedaLogout(token: string) {
  return sigedaFetch<null>("/api/sigeda/auth/logout/", {
    method: "POST",
    token,
  });
}

export function obtenerMiCuenta(token: string) {
  return sigedaFetch<Cuenta>("/api/sigeda/auth/me/", { token });
}

export function obtenerOtraCuenta(token: string) {
  return sigedaFetch<OtraCuenta>("/api/sigeda/auth/otra-cuenta/", { token });
}

export function asignarContrasenaTemporal(token: string) {
  return sigedaFetch<ContrasenaTemporalGenerada>(
    "/api/sigeda/auth/asignar-contrasena-temporal/",
    { method: "POST", token },
  );
}

export function cambiarContrasena(
  token: string,
  datos: {
    nueva_contrasena: string;
    contrasena_actual?: string;
    repetir_contrasena?: string;
  },
) {
  return sigedaFetch<{ token: string }>(
    "/api/sigeda/auth/cambiar-contrasena/",
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    },
  );
}

export function obtenerExpediente(
  token: string,
  numeroPaja: string,
  filtros?: FiltrosExpediente,
) {
  const params = new URLSearchParams();

  if (filtros?.id_tipo_documento) {
    params.set("id_tipo_documento", String(filtros.id_tipo_documento));
  }
  if (filtros?.nombre_identificador) {
    params.set("nombre_identificador", filtros.nombre_identificador);
  }
  if (filtros?.fecha_desde) params.set("fecha_desde", filtros.fecha_desde);
  if (filtros?.fecha_hasta) params.set("fecha_hasta", filtros.fecha_hasta);
  if (filtros?.mostrar_anulados) params.set("mostrar_anulados", "true");

  const query = params.toString();

  return sigedaFetch<Expediente>(
    `/api/sigeda/abonados/${encodeURIComponent(numeroPaja)}/expediente/` +
      (query ? `?${query}` : ""),
    { token },
  );
}

/** D-01 / RF-19: anular un documento (no se borra). */
export function anularDocumento(
  token: string,
  idDocumento: number,
  motivo: string,
) {
  return sigedaFetch<{ detail: string }>(
    `/api/sigeda/documentos/${idDocumento}/anular/`,
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ motivo }),
    },
  );
}

/** D-02 / RF-22: tipo y nombre identificador del documento (no toca el
 * archivo, la fecha del documento ni las versiones anteriores). */
export function editarDatosDocumento(
  token: string,
  idDocumento: number,
  datos: { id_tipo_documento: number; nombre_identificador: string | null },
) {
  return sigedaFetch<{ detail: string }>(
    `/api/sigeda/documentos/${idDocumento}/editar-datos/`,
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    },
  );
}

/** D-03 / RF-17: dar de baja (no borra documentos; RN-08). */
export function darDeBajaAbonado(
  token: string,
  numeroPaja: string,
  fechaBaja: string,
) {
  return sigedaFetch<{ detail: string }>(
    `/api/sigeda/abonados/${encodeURIComponent(numeroPaja)}/dar-de-baja/`,
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ fecha_baja: fechaBaja }),
    },
  );
}

/** D-03 / RF-17: reactivar un abonado de baja. */
export function reactivarAbonado(token: string, numeroPaja: string) {
  return sigedaFetch<{ detail: string }>(
    `/api/sigeda/abonados/${encodeURIComponent(numeroPaja)}/reactivar/`,
    { method: "POST", token },
  );
}

export function listarTiposDocumento(token: string) {
  return sigedaFetch<TipoDocumentoCatalogo[]>(
    "/api/sigeda/catalogos/tipos-documento/",
    { token },
  );
}

export function listarSectores(token: string) {
  return sigedaFetch<SectorCatalogo[]>(
    "/api/sigeda/catalogos/sectores/",
    { token },
  );
}

export function buscarExpedientes(token: string, criterios: CriteriosBusqueda) {
  const params = new URLSearchParams();

  if (criterios.numero_paja) params.set("numero_paja", criterios.numero_paja);
  if (criterios.nombre) params.set("nombre", criterios.nombre);
  if (criterios.identificacion) {
    params.set("identificacion", criterios.identificacion);
  }
  if (criterios.id_sector) {
    params.set("id_sector", String(criterios.id_sector));
  }
  params.set("incluir_baja", String(criterios.incluir_baja));

  return sigedaFetch<RespuestaBusqueda>(
    `/api/sigeda/abonados/buscar/?${params.toString()}`,
    { token },
  );
}

export async function cargarDocumentos({
  token,
  numeroPaja,
  archivos,
  metadatos,
}: {
  token: string;
  numeroPaja: string;
  archivos: File[];
  metadatos: MetadatoArchivo[];
}): Promise<CargaDocumentosExito> {
  const formData = new FormData();
  formData.set("numero_paja", numeroPaja);
  formData.set("metadatos", JSON.stringify(metadatos));

  for (const archivo of archivos) {
    formData.append("archivos", archivo);
  }

  try {
    return await sigedaFetch<CargaDocumentosExito>(
      "/api/sigeda/documentos/cargar/",
      { method: "POST", token, body: formData },
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 400) {
      // El cuerpo ya tiene la forma CargaDocumentosError; se relanza
      // tal cual para que la pantalla muestre un error por archivo.
      throw error;
    }

    throw error;
  }
}

export function esErrorDeCarga(
  payload: unknown,
): payload is CargaDocumentosError {
  return (
    !!payload &&
    typeof payload === "object" &&
    Array.isArray((payload as CargaDocumentosError).errores)
  );
}

/** `titular`/`persona` en el contrato aceptan una persona ya registrada
 * (`id_persona`) o los datos para crear una nueva; acá se arma el
 * fragmento del cuerpo según cuál llegó. */
function personaReferenciaABody(
  persona: PersonaReferencia,
): Record<string, unknown> {
  if ("id_persona" in persona) {
    return { id_persona: persona.id_persona };
  }

  return {
    nombre: persona.nombre,
    tipo_identificacion: persona.tipo_identificacion,
    identificacion: persona.identificacion,
  };
}

/** RF-02/D-06/D-04: personas ya registradas (nombre o identificación),
 * con sus vínculos vigentes, para no duplicarlas. */
export function buscarPersonas(token: string, q: string) {
  const params = new URLSearchParams({ q });

  return sigedaFetch<PersonaBusqueda[]>(
    `/api/sigeda/abonados/personas/buscar/?${params.toString()}`,
    { token },
  );
}

/** Body 409 cuando la identificación ya pertenece a una persona
 * registrada (ficha PAN-06, estado "persona-existente"). */
export function esPersonaExistente(
  payload: unknown,
): payload is { persona_existente: PersonaExistenteConflicto } {
  return (
    !!payload &&
    typeof payload === "object" &&
    "persona_existente" in payload &&
    !!(payload as { persona_existente?: unknown }).persona_existente
  );
}

/** RF-02: alta de abonado (PAN-06 "Registrar abonado"). Abonado +
 * persona (nueva o reutilizada) + vínculo TITULAR, en una transacción. */
export function registrarAbonado(token: string, datos: AltaAbonadoDatos) {
  return sigedaFetch<{ detail: string; numero_paja: string }>(
    "/api/sigeda/abonados/alta/",
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      // El backend recibe los datos del titular al mismo nivel que
      // numero_paja/id_sector/tipo_abonado (sin anidar "titular").
      body: JSON.stringify({
        numero_paja: datos.numero_paja,
        id_sector: datos.id_sector,
        tipo_abonado: datos.tipo_abonado,
        ...personaReferenciaABody(datos.titular),
      }),
    },
  );
}

/** RF-21: sector y tipo (PAN-06 "Modificar abonado y personas"). La
 * paja y el estado no se tocan acá. */
export function modificarAbonado(
  token: string,
  numeroPaja: string,
  datos: ModificarAbonadoDatos,
) {
  return sigedaFetch<{ detail: string }>(
    `/api/sigeda/abonados/${encodeURIComponent(numeroPaja)}/modificar/`,
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    },
  );
}

/** D-06: agrega un cotitular o una persona apoderada (nunca titular). */
export function agregarPersonaAsociada(
  token: string,
  numeroPaja: string,
  datos: AgregarPersonaDatos,
) {
  return sigedaFetch<{ detail: string }>(
    `/api/sigeda/abonados/${encodeURIComponent(numeroPaja)}/personas/`,
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...personaReferenciaABody(datos.persona),
        rol: datos.rol,
        fecha_inicio: datos.fecha_inicio,
      }),
    },
  );
}

/** PAN-06 modificar, tabla de personas: cierra el vínculo (no borra
 * documentos ya aportados por esa persona). */
export function quitarPersonaAsociada(
  token: string,
  numeroPaja: string,
  idPersona: number,
) {
  return sigedaFetch<{ detail: string }>(
    `/api/sigeda/abonados/${encodeURIComponent(numeroPaja)}/personas/${idPersona}/quitar/`,
    { method: "POST", token },
  );
}

/** PAN-06 modificar, tabla de personas: cambia el rol en el mismo
 * vínculo abierto (no abre uno nuevo; la fecha de inicio no cambia). */
export function cambiarRolPersonaAsociada(
  token: string,
  numeroPaja: string,
  idPersona: number,
  rol: "COTITULAR" | "APODERADA",
) {
  return sigedaFetch<{ detail: string }>(
    `/api/sigeda/abonados/${encodeURIComponent(numeroPaja)}/personas/${idPersona}/cambiar-rol/`,
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rol }),
    },
  );
}

/** D-04/RF-13: cierra el vínculo del titular actual y abre uno nuevo,
 * en una transacción (hallazgo H-02: se abre directo desde el
 * expediente, sin pasar por "Modificar abonado"). */
export function cambiarTitular(
  token: string,
  numeroPaja: string,
  datos: CambiarTitularDatos,
) {
  return sigedaFetch<{ detail: string }>(
    `/api/sigeda/abonados/${encodeURIComponent(numeroPaja)}/cambiar-titular/`,
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...personaReferenciaABody(datos.persona),
        fecha_cambio: datos.fecha_cambio,
      }),
    },
  );
}

// --- RF-16 Respaldo y restauración (PAN-08, D-05) -------------------

/** PAN-08 e insignia global: lista de respaldos con sus copias, más el
 * resumen para la insignia (ver SUPUESTO en `types.ts`). */
export function obtenerRespaldos(token: string) {
  return sigedaFetch<RespuestaRespaldos>("/api/sigeda/respaldos/", { token });
}

/** "Respaldar ahora": respaldo manual inmediato (empaqueta la base y el
 * almacén de documentos; puede tardar varios segundos). */
export function crearRespaldoManual(token: string) {
  return sigedaFetch<Respaldo>("/api/sigeda/respaldos/manual/", {
    method: "POST",
    token,
  });
}

/** D-05 Restaurar un respaldo. Operación destructiva: reemplaza la base
 * y el almacén completos por los del respaldo elegido (la bitácora no
 * se borra, RNF-11). NUNCA se llama en pruebas contra el entorno de
 * desarrollo compartido. */
export function restaurarRespaldo(
  token: string,
  idRespaldo: number,
  datos: DatosRestaurar,
) {
  return sigedaFetch<{ detail: string }>(
    `/api/sigeda/respaldos/${idRespaldo}/restaurar/`,
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    },
  );
}

/** Sub-pantalla "Archivos en cuarentena". */
export function obtenerCuarentena(token: string) {
  return sigedaFetch<ArchivoCuarentena[]>(
    "/api/sigeda/respaldos/cuarentena/",
    { token },
  );
}

/** Sub-pantalla "Registrar una prueba de restauración": listado para el
 * historial debajo del formulario. */
export function listarPruebasRestauracion(token: string) {
  return sigedaFetch<PruebaRestauracion[]>(
    "/api/sigeda/respaldos/pruebas-restauracion/",
    { token },
  );
}

export function registrarPruebaRestauracion(
  token: string,
  datos: DatosPruebaRestauracion,
) {
  return sigedaFetch<PruebaRestauracion>(
    "/api/sigeda/respaldos/pruebas-restauracion/",
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    },
  );
}

// --- RF-04 Importar listado de SADA (PAN-09) ------------------------

/** Paso 2 "Revisar columnas": parsea el archivo (ADR-04) y devuelve sus
 * columnas reales más un ejemplo de la fila 2, sin guardar nada
 * todavía. 400 si la extensión no es .xlsx/.csv. */
export function vistaPreviaImportacionSada(token: string, archivo: File) {
  const formData = new FormData();
  formData.append("archivo", archivo);

  return sigedaFetch<VistaPreviaImportacion>(
    "/api/sigeda/abonados/importar/vista-previa/",
    { method: "POST", token, body: formData },
  );
}

/** Paso 3 "Importar": manda el archivo otra vez (decisión de hoy: más
 * simple que guardarlo temporalmente en el servidor entre pasos) junto
 * con el mapeo de columnas elegido en el paso 2. */
export function importarSada(
  token: string,
  archivo: File,
  columnaPaja: string,
  columnaNombre: string,
) {
  const formData = new FormData();
  formData.append("archivo", archivo);
  formData.set("columna_paja", columnaPaja);
  formData.set("columna_nombre", columnaNombre);

  return sigedaFetch<ResultadoImportacion>(
    "/api/sigeda/abonados/importar/",
    { method: "POST", token, body: formData },
  );
}

export async function descargarVersion(
  token: string,
  idDocumento: number,
  numeroVersion: number,
): Promise<Blob> {
  const response = await fetch(
    `/api/sigeda/documentos/${idDocumento}/versiones/${numeroVersion}/descargar/`,
    { headers: { Authorization: `Bearer ${token}` } },
  );

  if (!response.ok) {
    throw new ApiError({
      message: "No fue posible abrir el documento.",
      status: response.status,
      payload: null,
    });
  }

  return response.blob();
}

// --- RF-09 Tipos de documento y grupos de alternativas (PAN-10) -----

/** Lista administrativa completa (con obligatoriedad/grupo), distinta
 * del catálogo liviano que usa PAN-05 (`listarTiposDocumento`).
 * Ruta real del backend: vive bajo `/catalogos/` junto al resto de
 * `apps.configuration.sigeda_urls`, no en la raíz `/api/sigeda/` que
 * describía el contrato inicial de este incremento. */
export function listarTiposDocumentoAdmin(token: string) {
  return sigedaFetch<TipoDocumentoAdmin[]>(
    "/api/sigeda/catalogos/tipos-documento/administracion/",
    { token },
  );
}

export function crearTipoDocumento(token: string, datos: DatosTipoDocumento) {
  return sigedaFetch<{ detail: string; id_tipo_documento: number }>(
    "/api/sigeda/catalogos/tipos-documento/crear/",
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    },
  );
}

export function editarTipoDocumento(
  token: string,
  idTipoDocumento: number,
  datos: DatosTipoDocumento,
) {
  return sigedaFetch<{ detail: string; id_tipo_documento: number }>(
    `/api/sigeda/catalogos/tipos-documento/${idTipoDocumento}/editar/`,
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    },
  );
}

export function listarGruposAlternativas(token: string) {
  return sigedaFetch<GrupoAlternativas[]>(
    "/api/sigeda/catalogos/grupos-alternativas/",
    { token },
  );
}

export function crearGrupoAlternativas(
  token: string,
  datos: DatosGrupoAlternativas,
) {
  return sigedaFetch<{ detail: string; id_grupo_alternativas: number }>(
    "/api/sigeda/catalogos/grupos-alternativas/crear/",
    {
      method: "POST",
      token,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    },
  );
}

// --- RF-14 Completitud (PAN-07) --------------------------------------
// Rutas reales: cuelgan de `apps.abonados.urls` (bajo
// `/api/sigeda/abonados/`), no de una raíz `/api/sigeda/completitud/`
// aparte como describía el contrato inicial.

export function obtenerCompletitud(token: string, filtros?: FiltrosCompletitud) {
  const params = new URLSearchParams();

  if (filtros?.id_sector) params.set("id_sector", String(filtros.id_sector));
  if (filtros?.tipo_abonado) params.set("tipo_abonado", filtros.tipo_abonado);
  if (filtros?.documento_faltante) {
    params.set("documento_faltante", filtros.documento_faltante);
  }
  if (filtros?.mostrar_de_baja) params.set("mostrar_de_baja", "true");

  const query = params.toString();

  return sigedaFetch<RespuestaCompletitud>(
    `/api/sigeda/abonados/completitud/${query ? `?${query}` : ""}`,
    { token },
  );
}

export function obtenerDetalleCompletitud(token: string, numeroPaja: string) {
  return sigedaFetch<DetalleCompletitud>(
    `/api/sigeda/abonados/${encodeURIComponent(numeroPaja)}/completitud/`,
    { token },
  );
}

// --- RF-15 Bitácora (PAN-11) ------------------------------------------

export function obtenerBitacora(token: string, filtros?: FiltrosBitacora) {
  const params = new URLSearchParams();

  if (filtros?.usuario) params.set("usuario", filtros.usuario);
  if (filtros?.desde) params.set("desde", filtros.desde);
  if (filtros?.hasta) params.set("hasta", filtros.hasta);
  if (filtros?.numero_paja) params.set("numero_paja", filtros.numero_paja);
  if (filtros?.accion) params.set("accion", filtros.accion);
  params.set("limit", String(filtros?.limit ?? 50));
  params.set("offset", String(filtros?.offset ?? 0));

  return sigedaFetch<RespuestaBitacora>(
    `/api/sigeda/bitacora/?${params.toString()}`,
    { token },
  );
}

// --- RF-18 Exportar documentos (PAN-12) -------------------------------

export function exportarDocumentos(
  token: string,
  numeroPaja: string,
  idsDocumento: number[],
) {
  return sigedaFetch<ResultadoExportacion>("/api/sigeda/documentos/exportar/", {
    method: "POST",
    token,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      numero_paja: numeroPaja,
      ids_documento: idsDocumento,
    }),
  });
}
