import {
  ApiError,
  ApiNetworkError,
  ApiTimeoutError,
  getApiErrorMessage,
} from "@/lib/api/errors";

import type {
  CargaDocumentosError,
  CargaDocumentosExito,
  ContrasenaTemporalGenerada,
  CriteriosBusqueda,
  Cuenta,
  Expediente,
  FiltrosExpediente,
  MetadatoArchivo,
  OtraCuenta,
  RespuestaBusqueda,
  SectorCatalogo,
  TipoDocumentoCatalogo,
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
