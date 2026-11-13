import type { Respaldo, ResumenRespaldos } from "./types";

export type EstadoGlobalRespaldo =
  | "completo"
  | "pendiente"
  | "fallido"
  | "sin_respaldos";

export type ResumenCalculado = {
  estadoGlobal: EstadoGlobalRespaldo;
  ultimoCompleto: Respaldo | null;
  ultimoIntento: Respaldo | null;
};

/**
 * Deriva el estado para la insignia global y PAN-08 a partir de la
 * propia lista de respaldos (se ordena por `fecha_hora` descendente,
 * igual que `Respaldo.Meta.ordering` en el backend), en vez de depender
 * de la redacción exacta de `resumen` — así la pantalla no se rompe si
 * el backend todavía no manda ese campo o le pone otro nombre (ver
 * SUPUESTO en `types.ts`). Si `resumen.estado_global` sí viene, se
 * respeta: puede saber cosas que la lista sola no sabe (p. ej. que el
 * automático de hoy todavía ni se ha intentado).
 */
export function calcularResumen(
  respaldos: Respaldo[],
  resumen?: ResumenRespaldos,
): ResumenCalculado {
  const ordenados = [...respaldos].sort(
    (a, b) => new Date(b.fecha_hora).getTime() - new Date(a.fecha_hora).getTime(),
  );
  const ultimoIntento = ordenados[0] ?? null;
  const ultimoCompleto = ordenados.find((r) => r.estado === "COMPLETO") ?? null;

  let estadoGlobal: EstadoGlobalRespaldo;

  if (resumen?.estado_global) {
    estadoGlobal = resumen.estado_global;
  } else if (!ultimoIntento) {
    estadoGlobal = "sin_respaldos";
  } else if (ultimoIntento.estado === "COMPLETO") {
    estadoGlobal = "completo";
  } else if (ultimoIntento.estado === "FALLIDO") {
    estadoGlobal = "fallido";
  } else {
    estadoGlobal = "pendiente";
  }

  return { estadoGlobal, ultimoCompleto, ultimoIntento };
}

/** dd/mm/aaaa hh:mm (CLAUDE.md sección 2: fechas dd/mm/aaaa, horas de
 * 24 h). SUPUESTO: se formatea en la hora local del navegador; falta
 * confirmar con el backend ya construido en qué huso serializa
 * `fecha_hora` (la laptop de la ASADA no cambia de huso, así que en la
 * práctica da igual, pero queda anotado). */
export function formatearFechaHora(iso: string): string {
  const fecha = new Date(iso);

  if (Number.isNaN(fecha.getTime())) return iso;

  const dia = String(fecha.getDate()).padStart(2, "0");
  const mes = String(fecha.getMonth() + 1).padStart(2, "0");
  const anio = fecha.getFullYear();
  const horas = String(fecha.getHours()).padStart(2, "0");
  const minutos = String(fecha.getMinutes()).padStart(2, "0");

  return `${dia}/${mes}/${anio} ${horas}:${minutos}`;
}

export function formatearFecha(iso: string): string {
  const [anio, mes, dia] = iso.slice(0, 10).split("-");
  if (!anio || !mes || !dia) return iso;
  return `${dia}/${mes}/${anio}`;
}

/** Tamaño en MB con coma decimal (es-CR), como en la ficha ("14,2 MB"). */
export function formatearTamano(bytes: number | null): string {
  if (bytes === null) return "—";

  const mb = bytes / (1024 * 1024);
  return `${mb.toLocaleString("es-CR", { maximumFractionDigits: 1 })} MB`;
}

export function textoTipoRespaldo(tipo: Respaldo["tipo"]): string {
  return tipo === "AUTOMATICO" ? "Automático" : "Manual";
}

export function textoEstadoRespaldo(estado: Respaldo["estado"]): string {
  if (estado === "COMPLETO") return "Completo";
  if (estado === "PENDIENTE") return "Pendiente";
  return "Fallido";
}

/** Columna "Disco externo"/"OneDrive" de la tabla "Últimos respaldos".
 * SUPUESTO de redacción exacta por destino (la ficha solo capturó el
 * ejemplo del disco externo); se usa el mismo vocabulario que ya define
 * la guía de estilo del prototipo para los demás estados. */
export function textoCopiaDestino(
  copia: Respaldo["copias"][number] | undefined,
  destino: "DISCO_EXTERNO" | "ONEDRIVE",
): string {
  if (!copia) return destino === "ONEDRIVE" ? "No configurado" : "—";

  if (copia.estado === "VERIFICADA") return "Verificada ✓";
  if (copia.estado === "FALLIDA") return "La copia no coincide";

  return destino === "DISCO_EXTERNO" ? "Disco no conectado" : "No configurado";
}
