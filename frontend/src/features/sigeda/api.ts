import {
  ApiError,
  ApiNetworkError,
  ApiTimeoutError,
  getApiErrorMessage,
} from "@/lib/api/errors";

import type {
  CargaDocumentosError,
  CargaDocumentosExito,
  Cuenta,
  Expediente,
  MetadatoArchivo,
  TipoDocumentoCatalogo,
} from "./types";

const TIMEOUT_MS = 20_000;

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

export function obtenerExpediente(token: string, numeroPaja: string) {
  return sigedaFetch<Expediente>(
    `/api/sigeda/abonados/${encodeURIComponent(numeroPaja)}/expediente/`,
    { token },
  );
}

export function listarTiposDocumento(token: string) {
  return sigedaFetch<TipoDocumentoCatalogo[]>(
    "/api/sigeda/catalogos/tipos-documento/",
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
