"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  descargarVersion,
  exportarDocumentos,
  obtenerExpediente,
} from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import { formatearFecha } from "@/features/sigeda/respaldos-estado";
import type { DocumentoExpediente, Expediente } from "@/features/sigeda/types";

type Destino = "CARPETA" | "IMPRIMIR";

/**
 * PAN-12 "Exportar documentos" (RF-18, RN-10). Solo lista los
 * documentos VIGENTES del expediente (ver nota del prompt de este
 * incremento: se mantiene simple, sin repetir el filtro "Mostrar
 * anulados" de PAN-04 acá).
 */
export default function ExportarDocumentosPage() {
  const { numeroPaja } = useParams<{ numeroPaja: string }>();
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [expediente, setExpediente] = useState<Expediente | null>(null);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [elegidos, setElegidos] = useState<Set<number>>(new Set());
  const [destino, setDestino] = useState<Destino>("CARPETA");

  const [exportando, setExportando] = useState(false);
  const [mensajeExito, setMensajeExito] = useState<string | null>(null);
  const [errorExportar, setErrorExportar] = useState<string | null>(null);

  const [imprimiendo, setImprimiendo] = useState(false);
  const [mensajeImprimir, setMensajeImprimir] = useState<string | null>(null);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    (async () => {
      setCargando(true);
      setError(null);

      try {
        const datos = await obtenerExpediente(sesion.token, numeroPaja);
        setExpediente(datos);
        setElegidos(
          new Set(
            datos.documentos
              .filter((d) => d.estado === "VIGENTE" && d.version_vigente)
              .map((d) => d.id_documento),
          ),
        );
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "No fue posible cargar el expediente.",
        );
      } finally {
        setCargando(false);
      }
    })();
  }, [cargandoSesion, sesion, numeroPaja, router]);

  function alternar(idDocumento: number) {
    setElegidos((actual) => {
      const nuevo = new Set(actual);
      if (nuevo.has(idDocumento)) {
        nuevo.delete(idDocumento);
      } else {
        nuevo.add(idDocumento);
      }
      return nuevo;
    });
  }

  if (cargandoSesion || cargando) {
    return <p className="p-6">Cargando…</p>;
  }

  if (error && !expediente) {
    return (
      <main className="p-6">
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {error}
        </div>
      </main>
    );
  }

  if (!expediente) return null;

  const vigentes: DocumentoExpediente[] = expediente.documentos.filter(
    (d) => d.estado === "VIGENTE" && d.version_vigente,
  );
  const cantidadElegidos = elegidos.size;
  const fechaHoy = new Date();
  const fechaHoyTexto = `${fechaHoy.getFullYear()}${String(fechaHoy.getMonth() + 1).padStart(2, "0")}${String(fechaHoy.getDate()).padStart(2, "0")}`;
  const numeroPajaExpediente = expediente.abonado.numero_paja;
  const rutaEjemplo = `C:\\Exportaciones\\${numeroPajaExpediente}_${fechaHoyTexto}`;

  async function manejarExportarCarpeta() {
    if (!sesion || cantidadElegidos === 0) return;

    setExportando(true);
    setErrorExportar(null);
    setMensajeExito(null);

    try {
      const respuesta = await exportarDocumentos(
        sesion.token,
        numeroPajaExpediente,
        Array.from(elegidos),
      );
      setMensajeExito(respuesta.detail);
    } catch (err) {
      setErrorExportar(
        err instanceof Error ? err.message : "No fue posible exportar los documentos.",
      );
    } finally {
      setExportando(false);
    }
  }

  async function manejarImprimir() {
    if (!sesion || cantidadElegidos === 0) return;

    setImprimiendo(true);
    setErrorExportar(null);
    setMensajeImprimir(null);

    let abiertas = 0;

    try {
      for (const documento of vigentes) {
        if (!elegidos.has(documento.id_documento) || !documento.version_vigente) {
          continue;
        }

        const blob = await descargarVersion(
          sesion.token,
          documento.id_documento,
          documento.version_vigente.numero_version,
        );
        const url = URL.createObjectURL(blob);
        window.open(url, "_blank");
        abiertas += 1;
      }

      setMensajeImprimir(
        abiertas === 1
          ? "Se abrió 1 pestaña para imprimir. Use Ctrl+P del navegador en cada una."
          : `Se abrieron ${abiertas} pestañas para imprimir. Use Ctrl+P del navegador en cada una.`,
      );
    } catch (err) {
      setErrorExportar(
        err instanceof Error ? err.message : "No fue posible abrir los documentos para imprimir.",
      );
    } finally {
      setImprimiendo(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <nav aria-label="Ruta">
        <Link href="/sigeda/buscar" className="text-[var(--color-primary)]">
          Buscar expediente
        </Link>
        {" › "}
        <Link
          href={`/sigeda/expedientes/${expediente.abonado.numero_paja}`}
          className="text-[var(--color-primary)]"
        >
          Expediente {expediente.abonado.numero_paja}
        </Link>
        {" › "}
        <span>Exportar documentos</span>
      </nav>

      <div className="flex flex-col gap-1">
        <h1>Exportar documentos · paja {expediente.abonado.numero_paja}</h1>
        <p>Solo se exportan los documentos vigentes del expediente.</p>
      </div>

      {mensajeExito ? (
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
        >
          {mensajeExito}
        </div>
      ) : null}

      {mensajeImprimir ? (
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
        >
          {mensajeImprimir}
        </div>
      ) : null}

      {errorExportar ? (
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {errorExportar}
        </div>
      ) : null}

      <div className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]">
        Los datos de las personas solo se entregan a quien tenga facultad
        legal (RN-10).
      </div>

      <section aria-labelledby="documentos-exportar-titulo">
        <h2 id="documentos-exportar-titulo">Documentos vigentes ({vigentes.length})</h2>

        {vigentes.length === 0 ? (
          <p>Este expediente no tiene documentos vigentes para exportar.</p>
        ) : (
          <table className="mt-3 w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2">
                  <span className="sr-only">Elegir</span>
                </th>
                <th className="py-2">Tipo</th>
                <th className="py-2">Nombre identificador</th>
                <th className="py-2">Fecha</th>
              </tr>
            </thead>
            <tbody>
              {vigentes.map((documento) => (
                <tr
                  key={documento.id_documento}
                  className="border-b border-[var(--color-border-soft)]"
                >
                  <td className="py-2">
                    <label className="sr-only" htmlFor={`elegir-${documento.id_documento}`}>
                      Elegir {documento.tipo_documento}
                    </label>
                    <input
                      id={`elegir-${documento.id_documento}`}
                      type="checkbox"
                      checked={elegidos.has(documento.id_documento)}
                      onChange={() => alternar(documento.id_documento)}
                    />
                  </td>
                  <td className="py-2">{documento.tipo_documento}</td>
                  <td className="py-2">{documento.nombre_identificador ?? "—"}</td>
                  <td className="py-2">
                    {documento.version_vigente
                      ? formatearFecha(documento.version_vigente.fecha_documento)
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section aria-labelledby="destino-titulo">
        <h2 id="destino-titulo">Destino</h2>

        <fieldset className="mt-3 flex flex-col gap-3">
          <legend className="sr-only">Destino de la exportación</legend>

          <label className="flex items-start gap-2">
            <input
              type="radio"
              name="destino"
              checked={destino === "CARPETA"}
              onChange={() => setDestino("CARPETA")}
              className="mt-1"
            />
            <span className="flex flex-col gap-1.5">
              Copiar a una carpeta
              {destino === "CARPETA" ? (
                <>
                  <span
                    aria-label="Carpeta de destino"
                    className="inline-flex h-12 w-full max-w-md items-center rounded-[var(--radius-md)] border border-border bg-surface-muted px-4 text-[15px] text-foreground"
                  >
                    {rutaEjemplo}
                  </span>
                  <span className="flex items-center gap-2">
                    <Button type="button" variant="secondary" disabled>
                      Elegir…
                    </Button>
                    <span className="text-sm text-[var(--color-text-muted)]">
                      En el sistema real, «Elegir…» abre el selector de
                      carpetas de Windows.
                    </span>
                  </span>
                </>
              ) : null}
            </span>
          </label>

          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="destino"
              checked={destino === "IMPRIMIR"}
              onChange={() => setDestino("IMPRIMIR")}
            />
            Imprimir
          </label>
        </fieldset>
      </section>

      <div className="flex justify-end gap-3">
        <Button
          variant="secondary"
          onClick={() => router.push(`/sigeda/expedientes/${expediente.abonado.numero_paja}`)}
        >
          Volver al expediente
        </Button>
        {destino === "CARPETA" ? (
          <Button
            disabled={cantidadElegidos === 0}
            isLoading={exportando}
            loadingText="Exportando…"
            onClick={manejarExportarCarpeta}
          >
            Exportar {cantidadElegidos} documento{cantidadElegidos === 1 ? "" : "s"}
          </Button>
        ) : (
          <Button
            disabled={cantidadElegidos === 0}
            isLoading={imprimiendo}
            loadingText="Abriendo…"
            onClick={manejarImprimir}
          >
            Imprimir {cantidadElegidos} documento{cantidadElegidos === 1 ? "" : "s"}
          </Button>
        )}
      </div>
    </main>
  );
}
