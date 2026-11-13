"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { FechaInput } from "@/components/forms/fecha-input";
import { obtenerBitacora } from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import { formatearFecha, formatearFechaHora } from "@/features/sigeda/respaldos-estado";
import {
  ETIQUETAS_ACCION_BITACORA,
  type AccionBitacora,
  type CuentaBitacora,
  type RegistroBitacoraFila,
  type RespuestaBitacora,
} from "@/features/sigeda/types";

const LIMITE_PAGINA = 20;

function textoCuenta(cuenta: CuentaBitacora): string {
  if (cuenta === "secretaria") return "Secretaría";
  if (cuenta === "administracion") return "Administración";
  return "Sistema";
}

/** Mensaje "sin resultados" (ficha PAN-11): se construye con los
 * filtros reales que la usuaria puso, no con un texto genérico. */
function mensajeSinResultados(filtros: {
  numeroPaja: string;
  desde: string;
  hasta: string;
}): string {
  const { numeroPaja, desde, hasta } = filtros;
  const desdeTexto = desde ? formatearFecha(desde) : null;
  const hastaTexto = hasta ? formatearFecha(hasta) : null;

  if (numeroPaja && desdeTexto && hastaTexto) {
    return `No hay registros de la paja ${numeroPaja} entre el ${desdeTexto} y el ${hastaTexto}. Amplíe el rango de fechas o revise el número de paja.`;
  }
  if (numeroPaja && (desdeTexto || hastaTexto)) {
    return `No hay registros de la paja ${numeroPaja} en el rango de fechas elegido. Amplíe el rango de fechas o revise el número de paja.`;
  }
  if (numeroPaja) {
    return `No hay registros de la paja ${numeroPaja}. Revise el número de paja.`;
  }
  if (desdeTexto && hastaTexto) {
    return `No hay registros entre el ${desdeTexto} y el ${hastaTexto}. Amplíe el rango de fechas.`;
  }
  return "No hay registros que cumplan estos filtros. Revíselos o quítelos.";
}

function FilaBitacora({ fila }: { readonly fila: RegistroBitacoraFila }) {
  const elementoLegible = fila.tipo_documento ?? fila.elemento_afectado;

  return (
    <>
      <tr className="border-b border-[var(--color-border-soft)]">
        <td className="py-2">{formatearFechaHora(fila.fecha_hora)}</td>
        <td className="py-2">{textoCuenta(fila.cuenta)}</td>
        <td className="py-2">{ETIQUETAS_ACCION_BITACORA[fila.accion]}</td>
        <td className="py-2">{elementoLegible}</td>
        <td className="py-2">
          {fila.numero_paja ? (
            <Link
              href={`/sigeda/expedientes/${fila.numero_paja}`}
              className="text-[var(--color-primary)] underline"
            >
              {fila.numero_paja}
            </Link>
          ) : (
            "—"
          )}
        </td>
        <td className="py-2">
          {fila.modificaciones.length > 0 ? (
            <details>
              <summary className="cursor-pointer select-none text-[var(--color-primary)] underline">
                Ver cambios ({fila.modificaciones.length})
              </summary>
            </details>
          ) : (
            "—"
          )}
        </td>
      </tr>
      {fila.modificaciones.length > 0 ? (
        <tr className="border-b border-[var(--color-border-soft)]">
          <td colSpan={6} className="bg-[var(--color-surface-muted)] p-0">
            <table className="w-full border-collapse text-left">
              <caption className="sr-only">
                Cambios del registro {fila.id_registro_bitacora}
              </caption>
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="px-4 py-2">Campo</th>
                  <th className="px-4 py-2">Valor anterior</th>
                  <th className="px-4 py-2">Valor nuevo</th>
                </tr>
              </thead>
              <tbody>
                {fila.modificaciones.map((modificacion) => (
                  <tr key={modificacion.campo} className="border-b border-[var(--color-border-soft)]">
                    <td className="px-4 py-2 font-mono text-sm">{modificacion.campo}</td>
                    <td className="px-4 py-2">{modificacion.valor_anterior ?? "—"}</td>
                    <td className="px-4 py-2">{modificacion.valor_nuevo ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </td>
        </tr>
      ) : null}
    </>
  );
}

/**
 * PAN-11 "Bitácora" (RF-15). Es de solo lectura: ningún registro se
 * edita ni se borra (RNF-11), así que esta pantalla no ofrece ninguna
 * acción sobre las filas aparte de "Ver cambios" y el enlace a la paja.
 */
export default function BitacoraPage() {
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [datos, setDatos] = useState<RespuestaBitacora | null>(null);
  const [cargando, setCargando] = useState(true);
  const [actualizando, setActualizando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const primeraCargaHecha = useRef(false);

  const [filtroUsuario, setFiltroUsuario] = useState("");
  const [filtroDesde, setFiltroDesde] = useState("");
  const [filtroHasta, setFiltroHasta] = useState("");
  const [filtroPaja, setFiltroPaja] = useState("");
  const [filtroAccion, setFiltroAccion] = useState("");
  const [offset, setOffset] = useState(0);

  const cargar = useCallback(async () => {
    if (!sesion) return;

    if (primeraCargaHecha.current) {
      setActualizando(true);
    } else {
      setCargando(true);
    }
    setError(null);

    try {
      const respuesta = await obtenerBitacora(sesion.token, {
        usuario: filtroUsuario
          ? (filtroUsuario as "secretaria" | "administracion")
          : undefined,
        desde: filtroDesde || undefined,
        hasta: filtroHasta || undefined,
        numero_paja: filtroPaja || undefined,
        accion: filtroAccion ? (filtroAccion as AccionBitacora) : undefined,
        limit: LIMITE_PAGINA,
        offset,
      });
      setDatos(respuesta);
      primeraCargaHecha.current = true;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible consultar la bitácora.",
      );
    } finally {
      setCargando(false);
      setActualizando(false);
    }
  }, [sesion, filtroUsuario, filtroDesde, filtroHasta, filtroPaja, filtroAccion, offset]);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    cargar();
  }, [cargandoSesion, sesion, router, cargar]);

  // Cualquier cambio de filtro vuelve a la primera página.
  useEffect(() => {
    setOffset(0);
  }, [filtroUsuario, filtroDesde, filtroHasta, filtroPaja, filtroAccion]);

  if (cargandoSesion || cargando) {
    return <p className="p-6">Cargando…</p>;
  }

  if (error && !datos) {
    return (
      <main className="mx-auto flex max-w-6xl flex-col gap-4 p-6">
        <h1>Bitácora</h1>
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {error}
        </div>
        <Button onClick={() => cargar()}>Reintentar</Button>
      </main>
    );
  }

  if (!datos) return null;

  const { total, resultados } = datos;
  const desde1 = total === 0 ? 0 : offset + 1;
  const hastaN = Math.min(offset + LIMITE_PAGINA, total);

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <nav aria-label="Ruta">
        <Link href="/sigeda/buscar" className="text-[var(--color-primary)]">
          Buscar expediente
        </Link>
        {" › "}
        <span>Bitácora</span>
      </nav>

      <div className="flex flex-col gap-1">
        <h1>Bitácora</h1>
        <p>
          Todo cambio queda a nombre de quien lo hizo, con el valor anterior y
          el nuevo. No se edita ni se borra (RF-15, RNF-11).
        </p>
      </div>

      {error ? (
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {error}
        </div>
      ) : null}

      <div className="grid grid-cols-1 items-end gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="filtro-cuenta">Cuenta</label>
          <Select
            id="filtro-cuenta"
            value={filtroUsuario}
            onChange={(e) => setFiltroUsuario(e.target.value)}
          >
            <option value="">Todas</option>
            <option value="secretaria">Secretaría</option>
            <option value="administracion">Administración</option>
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="filtro-desde">Desde</label>
          <FechaInput id="filtro-desde" valorIso={filtroDesde} onChangeIso={setFiltroDesde} />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="filtro-hasta">Hasta</label>
          <FechaInput id="filtro-hasta" valorIso={filtroHasta} onChangeIso={setFiltroHasta} />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="filtro-paja">Número de paja</label>
          <Input
            id="filtro-paja"
            value={filtroPaja}
            onChange={(e) => setFiltroPaja(e.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="filtro-accion">Acción</label>
          <Select
            id="filtro-accion"
            value={filtroAccion}
            onChange={(e) => setFiltroAccion(e.target.value)}
          >
            <option value="">Todas</option>
            {Object.entries(ETIQUETAS_ACCION_BITACORA).map(([valor, etiqueta]) => (
              <option key={valor} value={valor}>
                {etiqueta}
              </option>
            ))}
          </Select>
        </div>
      </div>

      {actualizando ? (
        <p role="status" className="sr-only">
          Actualizando registros…
        </p>
      ) : null}

      {resultados.length === 0 ? (
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]"
        >
          {mensajeSinResultados({
            numeroPaja: filtroPaja,
            desde: filtroDesde,
            hasta: filtroHasta,
          })}
        </div>
      ) : (
        <>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2">Fecha y hora</th>
                <th className="py-2">Cuenta</th>
                <th className="py-2">Acción</th>
                <th className="py-2">Elemento afectado</th>
                <th className="py-2">Paja</th>
                <th className="py-2">Cambios</th>
              </tr>
            </thead>
            <tbody>
              {resultados.map((fila) => (
                <FilaBitacora key={fila.id_registro_bitacora} fila={fila} />
              ))}
            </tbody>
          </table>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-[var(--color-text-muted)]">
              Mostrando {desde1}–{hastaN} de {total}
            </p>
            <div className="flex gap-3">
              <Button
                variant="secondary"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - LIMITE_PAGINA))}
              >
                Anterior
              </Button>
              <Button
                variant="secondary"
                disabled={offset + LIMITE_PAGINA >= total}
                onClick={() => setOffset(offset + LIMITE_PAGINA)}
              >
                Siguiente
              </Button>
            </div>
          </div>
        </>
      )}
    </main>
  );
}
