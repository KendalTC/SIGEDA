"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import {
  listarSectores,
  obtenerCompletitud,
  obtenerDetalleCompletitud,
} from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import { formatearFecha } from "@/features/sigeda/respaldos-estado";
import type {
  AbonadoIncompleto,
  DetalleCompletitud,
  RespuestaCompletitud,
  SectorCatalogo,
} from "@/features/sigeda/types";

type FiltroEstado = "todos" | "completo" | "incompleto" | "tipo_pendiente";

function textoTipoAbonado(tipo: AbonadoIncompleto["tipo_abonado"]): string {
  if (tipo === "PERSONA_FISICA") return "Persona física";
  if (tipo === "PERSONA_JURIDICA") return "Persona jurídica";
  return "Pendiente";
}

/** El backend agrega el motivo al nombre del documento/grupo
 * ("Copia de cédula (titular)", "... del cotitular Ana"); para armar
 * las opciones del filtro "Documento que falta" se necesita el nombre
 * base, porque `documento_faltante` se compara con `startswith` en el
 * servidor (`servicio_completitud.listar_incompletos`). */
function nombreBaseFaltante(faltante: string): string {
  const indiceTitular = faltante.indexOf(" (titular)");
  if (indiceTitular !== -1) return faltante.slice(0, indiceTitular);

  const indiceCotitular = faltante.indexOf(" del cotitular ");
  if (indiceCotitular !== -1) return faltante.slice(0, indiceCotitular);

  return faltante;
}

/**
 * PAN-07 "Completitud" (RF-14). El panel por fila solo existe para los
 * `incompletos` (cada uno trae sus `faltantes`); los `tipo_pendiente`
 * van en su propia tabla porque ni siquiera tienen tipo de abonado
 * asignado todavía y su acción es otra ("Asignar tipo", no "Cargar").
 */
export default function CompletitudPage() {
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [datos, setDatos] = useState<RespuestaCompletitud | null>(null);
  const [sectores, setSectores] = useState<SectorCatalogo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [actualizando, setActualizando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const primeraCargaHecha = useRef(false);

  const [filtroEstado, setFiltroEstado] = useState<FiltroEstado>("todos");
  const [filtroSector, setFiltroSector] = useState("");
  const [filtroTipoAbonado, setFiltroTipoAbonado] = useState("");
  const [filtroDocumentoFaltante, setFiltroDocumentoFaltante] = useState("");
  const [mostrarDeBaja, setMostrarDeBaja] = useState(false);

  // Fila expandida (detalle Documento × Titular × Cotitular).
  const [pajaExpandida, setPajaExpandida] = useState<string | null>(null);
  const [detalle, setDetalle] = useState<DetalleCompletitud | null>(null);
  const [cargandoDetalle, setCargandoDetalle] = useState(false);
  const [errorDetalle, setErrorDetalle] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!sesion) return;

    if (primeraCargaHecha.current) {
      setActualizando(true);
    } else {
      setCargando(true);
    }
    setError(null);

    try {
      const respuesta = await obtenerCompletitud(sesion.token, {
        id_sector: filtroSector ? Number(filtroSector) : undefined,
        tipo_abonado: filtroTipoAbonado
          ? (filtroTipoAbonado as AbonadoIncompleto["tipo_abonado"])
          : undefined,
        documento_faltante: filtroDocumentoFaltante || undefined,
        mostrar_de_baja: mostrarDeBaja,
      });
      setDatos(respuesta);
      primeraCargaHecha.current = true;
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No fue posible consultar la completitud de los expedientes.",
      );
    } finally {
      setCargando(false);
      setActualizando(false);
    }
  }, [sesion, filtroSector, filtroTipoAbonado, filtroDocumentoFaltante, mostrarDeBaja]);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    cargar();
  }, [cargandoSesion, sesion, router, cargar]);

  useEffect(() => {
    if (!sesion) return;

    listarSectores(sesion.token)
      .then(setSectores)
      .catch(() => setSectores([]));
  }, [sesion]);

  // Opciones del select "Documento que falta": se construyen con lo
  // que realmente trajo el backend en `faltantes`, no con el catálogo
  // completo de tipos (para no ofrecer un filtro que siempre da vacío).
  const opcionesDocumentoFaltante = useMemo(() => {
    const vistos = new Set<string>();
    for (const incompleto of datos?.incompletos ?? []) {
      for (const faltante of incompleto.faltantes) {
        vistos.add(nombreBaseFaltante(faltante));
      }
    }
    return Array.from(vistos).sort((a, b) => a.localeCompare(b, "es"));
  }, [datos]);

  async function expandirFila(numeroPaja: string) {
    if (pajaExpandida === numeroPaja) {
      setPajaExpandida(null);
      return;
    }

    setPajaExpandida(numeroPaja);
    setDetalle(null);
    setErrorDetalle(null);

    if (!sesion) return;

    setCargandoDetalle(true);

    try {
      const respuesta = await obtenerDetalleCompletitud(sesion.token, numeroPaja);
      setDetalle(respuesta);
    } catch (err) {
      setErrorDetalle(
        err instanceof Error ? err.message : "No fue posible consultar el detalle.",
      );
    } finally {
      setCargandoDetalle(false);
    }
  }

  if (cargandoSesion || cargando) {
    return <p className="p-6">Cargando…</p>;
  }

  if (error && !datos) {
    return (
      <main className="mx-auto flex max-w-5xl flex-col gap-4 p-6">
        <h1>Completitud</h1>
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

  const { tarjetas, incompletos, tipo_pendiente: tipoPendiente } = datos;

  // `mostrarDeBaja` no filtra `incompletos`/`tipo_pendiente` (el
  // backend solo le agrega un conteo aparte, `de_baja`): no cuenta como
  // filtro activo para decidir si mostrar el mensaje de "vacío" o el de
  // "sin resultados".
  const hayFiltrosActivos = Boolean(
    filtroSector || filtroTipoAbonado || filtroDocumentoFaltante,
  );

  const mostrarIncompletos = filtroEstado === "todos" || filtroEstado === "incompleto";
  const mostrarTipoPendiente =
    filtroEstado === "todos" || filtroEstado === "tipo_pendiente";
  const mostrarAvisoCompleto = filtroEstado === "completo";

  const sinNadaQueMostrar =
    tarjetas.incompletos === 0 && tarjetas.tipo_pendiente === 0 && !hayFiltrosActivos;

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 p-6">
      <nav aria-label="Ruta">
        <Link href="/sigeda/buscar" className="text-[var(--color-primary)]">
          Buscar expediente
        </Link>
        {" › "}
        <span>Completitud</span>
      </nav>

      <div className="flex flex-col gap-1">
        <h1>Completitud de los expedientes</h1>
        <p>
          RF-14: solo cuentan los documentos vigentes del titular y de los
          cotitulares vigentes. Las tarjetas y las listas de abajo son
          siempre de abonados activos: los de baja nunca entran a esas
          cuentas, pero puede ver cuántos hay con «Mostrar abonados de
          baja».
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

      <div className="grid gap-4 sm:grid-cols-4">
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] border-l-4 border-l-[var(--color-success)] p-4">
          <p className="text-3xl font-bold">{tarjetas.completos}</p>
          <p className="text-sm text-[var(--color-text-muted)]">Completos</p>
        </div>
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] border-l-4 border-l-[var(--color-danger)] p-4">
          <p className="text-3xl font-bold">{tarjetas.incompletos}</p>
          <p className="text-sm text-[var(--color-text-muted)]">Incompletos</p>
        </div>
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] border-l-4 border-l-[var(--color-warning)] p-4">
          <p className="text-3xl font-bold">{tarjetas.tipo_pendiente}</p>
          <p className="text-sm text-[var(--color-text-muted)]">
            Tipo pendiente (de {tarjetas.total_activos} activos)
          </p>
        </div>
        <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] border-l-4 border-l-[var(--color-border-strong)] p-4">
          <p className="text-3xl font-bold">{tarjetas.total_activos}</p>
          <p className="text-sm text-[var(--color-text-muted)]">
            Total activos (los de baja no cuentan)
          </p>
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between">
          <span>Avance de la digitalización</span>
          <span className="font-semibold">{tarjetas.avance_pct}%</span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={tarjetas.avance_pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Avance de la digitalización"
          className="h-3 w-full overflow-hidden rounded-full bg-[var(--color-surface-muted)]"
        >
          <div
            className="h-full rounded-full bg-[var(--color-primary)]"
            style={{ width: `${Math.min(100, Math.max(0, tarjetas.avance_pct))}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-1 items-end gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="filtro-estado">Estado de completitud</label>
          <Select
            id="filtro-estado"
            value={filtroEstado}
            onChange={(e) => setFiltroEstado(e.target.value as FiltroEstado)}
          >
            <option value="todos">Todos</option>
            <option value="completo">Completos</option>
            <option value="incompleto">Incompletos</option>
            <option value="tipo_pendiente">Tipo pendiente</option>
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="filtro-sector">Sector</label>
          <Select
            id="filtro-sector"
            value={filtroSector}
            onChange={(e) => setFiltroSector(e.target.value)}
          >
            <option value="">Todos</option>
            {sectores.map((sector) => (
              <option key={sector.id_sector} value={sector.id_sector}>
                {sector.nombre}
              </option>
            ))}
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="filtro-tipo-abonado">Tipo de abonado</label>
          <Select
            id="filtro-tipo-abonado"
            value={filtroTipoAbonado}
            onChange={(e) => setFiltroTipoAbonado(e.target.value)}
          >
            <option value="">Todos</option>
            <option value="PERSONA_FISICA">Persona física</option>
            <option value="PERSONA_JURIDICA">Persona jurídica</option>
            <option value="PENDIENTE">Pendiente</option>
          </Select>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="filtro-documento-faltante">Documento que falta</label>
          <Select
            id="filtro-documento-faltante"
            value={filtroDocumentoFaltante}
            onChange={(e) => setFiltroDocumentoFaltante(e.target.value)}
          >
            <option value="">Cualquiera</option>
            {opcionesDocumentoFaltante.map((nombre) => (
              <option key={nombre} value={nombre}>
                {nombre}
              </option>
            ))}
          </Select>
        </div>

        <label className="flex items-center gap-2 pb-2.5">
          <input
            type="checkbox"
            checked={mostrarDeBaja}
            onChange={(e) => setMostrarDeBaja(e.target.checked)}
          />
          Mostrar abonados de baja
        </label>
      </div>

      {mostrarDeBaja && datos.de_baja ? (
        <p
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3"
        >
          Abonados de baja con estos mismos filtros de sector y tipo:{" "}
          <strong>{datos.de_baja.cantidad}</strong>. No cuentan en ninguna
          tarjeta ni aparecen en las tablas de abajo (RF-14).
        </p>
      ) : null}

      {actualizando ? (
        <p role="status" className="sr-only">
          Actualizando…
        </p>
      ) : null}

      {sinNadaQueMostrar ? (
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
        >
          <p className="font-semibold">¡Buena noticia! Todos los expedientes activos están completos.</p>
          <p>No hay documentos obligatorios pendientes ni abonados con tipo pendiente.</p>
        </div>
      ) : null}

      {mostrarAvisoCompleto ? (
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3"
        >
          Los expedientes completos no se listan aquí, solo se cuentan en la
          tarjeta «Completos» (arriba). Para verlos uno por uno, use «Buscar
          expediente».
        </div>
      ) : null}

      {mostrarIncompletos && !mostrarAvisoCompleto ? (
        <section aria-labelledby="incompletos-titulo">
          <h2 id="incompletos-titulo">Incompletos ({incompletos.length})</h2>

          {incompletos.length === 0 ? (
            hayFiltrosActivos || filtroEstado !== "todos" ? (
              <p
                role="status"
                className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]"
              >
                No hay expedientes incompletos que cumplan estos filtros.
                Revise el sector, el tipo de abonado o el documento elegido.
              </p>
            ) : (
              <p>No hay expedientes incompletos.</p>
            )
          ) : (
            <table className="mt-3 w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="py-2">Paja</th>
                  <th className="py-2">Titular</th>
                  <th className="py-2">Sector</th>
                  <th className="py-2">Tipo</th>
                  <th className="py-2">Faltantes</th>
                  <th className="py-2">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {incompletos.map((abonado) => (
                  <Fragment key={abonado.numero_paja}>
                    <tr className="border-b border-[var(--color-border-soft)]">
                      <td className="py-2">
                        <Link
                          href={`/sigeda/expedientes/${abonado.numero_paja}`}
                          className="text-[var(--color-primary)] underline"
                        >
                          {abonado.numero_paja}
                        </Link>
                      </td>
                      <td className="py-2">{abonado.titular_vigente ?? "Sin titular"}</td>
                      <td className="py-2">{abonado.sector ?? "—"}</td>
                      <td className="py-2">{textoTipoAbonado(abonado.tipo_abonado)}</td>
                      <td className="py-2">
                        <div className="flex flex-wrap gap-1.5">
                          {abonado.faltantes.map((faltante) => (
                            <span
                              key={faltante}
                              className="inline-flex items-center rounded-full border border-[var(--color-border-strong)] px-2 py-0.5 text-xs"
                            >
                              {faltante}
                            </span>
                          ))}
                        </div>
                      </td>
                      <td className="py-2">
                        <div className="flex flex-wrap gap-x-3 gap-y-1">
                          <button
                            type="button"
                            className="text-[var(--color-primary)] underline"
                            onClick={() => expandirFila(abonado.numero_paja)}
                          >
                            {pajaExpandida === abonado.numero_paja
                              ? "Ocultar detalle"
                              : "Ver detalle"}
                          </button>
                          <Link
                            href={`/sigeda/expedientes/${abonado.numero_paja}/cargar`}
                            className="text-[var(--color-primary)] underline"
                          >
                            Cargar
                          </Link>
                        </div>
                      </td>
                    </tr>
                    {pajaExpandida === abonado.numero_paja ? (
                      <tr className="border-b border-[var(--color-border-soft)]">
                        <td colSpan={6} className="bg-[var(--color-surface-muted)] p-4">
                          {cargandoDetalle ? (
                            <p>Cargando detalle…</p>
                          ) : errorDetalle ? (
                            <p role="alert" className="text-[var(--color-danger)]">
                              ⚠ {errorDetalle}
                            </p>
                          ) : detalle && detalle.matriz.length > 0 ? (
                            <table className="w-full border-collapse text-left">
                              <caption className="sr-only">
                                Documento obligatorio por persona
                              </caption>
                              <thead>
                                <tr className="border-b border-[var(--color-border)]">
                                  <th className="py-1">Documento obligatorio</th>
                                  {detalle.matriz[0]?.columnas.map((columna) => (
                                    <th key={columna.id_persona} className="py-1">
                                      {columna.nombre} (
                                      {columna.rol === "titular" ? "titular" : "cotitular"})
                                    </th>
                                  ))}
                                </tr>
                              </thead>
                              <tbody>
                                {detalle.matriz.map((fila) => (
                                  <tr
                                    key={fila.nombre}
                                    className="border-b border-[var(--color-border-soft)]"
                                  >
                                    <td className="py-1">
                                      {fila.nombre}
                                      {fila.es_grupo ? (
                                        <span className="ml-2 inline-flex items-center rounded-full border border-dashed border-[var(--color-border-strong)] px-2 py-0.5 text-xs text-[var(--color-text-muted)]">
                                          grupo
                                        </span>
                                      ) : null}
                                    </td>
                                    {fila.columnas.map((columna) => (
                                      <td key={columna.id_persona} className="py-1">
                                        {!columna.aplica ? (
                                          <span className="text-[var(--color-text-muted)]">
                                            No aplica
                                          </span>
                                        ) : columna.tiene_documento ? (
                                          <span className="text-[var(--color-success)]">
                                            ✓ Tiene
                                          </span>
                                        ) : (
                                          <span className="flex items-center gap-2 text-[var(--color-danger)]">
                                            ✗ Falta
                                            <Link
                                              href={`/sigeda/expedientes/${abonado.numero_paja}/cargar`}
                                              className="text-[var(--color-primary)] underline"
                                            >
                                              Cargar
                                            </Link>
                                          </span>
                                        )}
                                      </td>
                                    ))}
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          ) : detalle ? (
                            <p>Este expediente no tiene documentos obligatorios que exigirle.</p>
                          ) : null}
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ) : null}

      {mostrarTipoPendiente && !mostrarAvisoCompleto ? (
        <section aria-labelledby="tipo-pendiente-titulo">
          <h2 id="tipo-pendiente-titulo">
            Tipo pendiente ({tipoPendiente.length}) · importados de SADA
          </h2>

          {tipoPendiente.length === 0 ? (
            <p>No hay abonados con tipo pendiente.</p>
          ) : (
            <table className="mt-3 w-full border-collapse text-left">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="py-2">Paja</th>
                  <th className="py-2">Titular</th>
                  <th className="py-2">Importado el</th>
                  <th className="py-2">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {tipoPendiente.map((abonado) => (
                  <tr
                    key={abonado.numero_paja}
                    className="border-b border-[var(--color-border-soft)]"
                  >
                    <td className="py-2">
                      <Link
                        href={`/sigeda/expedientes/${abonado.numero_paja}`}
                        className="text-[var(--color-primary)] underline"
                      >
                        {abonado.numero_paja}
                      </Link>
                    </td>
                    <td className="py-2">{abonado.titular_vigente ?? "Sin titular"}</td>
                    <td className="py-2">
                      {abonado.fecha_inicio ? formatearFecha(abonado.fecha_inicio) : "—"}
                    </td>
                    <td className="py-2">
                      <button
                        type="button"
                        className="text-[var(--color-primary)] underline"
                        onClick={() =>
                          router.push(`/sigeda/abonados/${abonado.numero_paja}/modificar`)
                        }
                      >
                        Asignar tipo
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ) : null}
    </main>
  );
}
