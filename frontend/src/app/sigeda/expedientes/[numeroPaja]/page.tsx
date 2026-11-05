"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { descargarVersion, obtenerExpediente } from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import type { Expediente } from "@/features/sigeda/types";

function formatearFecha(fechaIso: string): string {
  const [anio, mes, dia] = fechaIso.split("-");
  return `${dia}/${mes}/${anio}`;
}

export default function ExpedientePage() {
  const { numeroPaja } = useParams<{ numeroPaja: string }>();
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [expediente, setExpediente] = useState<Expediente | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const [urlVisor, setUrlVisor] = useState<string | null>(null);
  const [nombreVisor, setNombreVisor] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!sesion) return;

    setCargando(true);
    setError(null);

    try {
      const datos = await obtenerExpediente(sesion.token, numeroPaja);
      setExpediente(datos);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible cargar el expediente.",
      );
    } finally {
      setCargando(false);
    }
  }, [sesion, numeroPaja]);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    cargar();
  }, [cargandoSesion, sesion, router, cargar]);

  async function verDocumento(idDocumento: number, numeroVersion: number, nombre: string) {
    if (!sesion) return;

    try {
      const blob = await descargarVersion(sesion.token, idDocumento, numeroVersion);
      setUrlVisor(URL.createObjectURL(blob));
      setNombreVisor(nombre);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible abrir el documento.",
      );
    }
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

  const { abonado, personas_vigentes: personasVigentes, documentos } = expediente;

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <nav aria-label="Ruta">
        <Link href="/sigeda/login" className="text-[var(--color-primary)]">
          Buscar expediente
        </Link>
        {" › "}
        <span>Expediente {abonado.numero_paja}</span>
      </nav>

      <h1>Expediente · paja {abonado.numero_paja}</h1>

      <p>
        Titular vigente:{" "}
        <strong>{abonado.titular_vigente?.nombre ?? "Sin titular"}</strong>
        {" · "}
        {abonado.sector ?? "Sin sector"}
        {" · "}
        {abonado.tipo_abonado === "PERSONA_FISICA" ? "Persona física" : abonado.tipo_abonado}
        {" · "}
        {abonado.estado === "ACTIVO" ? "Activo" : "De baja"}
      </p>

      <div>
        <Button
          onClick={() => router.push(`/sigeda/expedientes/${abonado.numero_paja}/cargar`)}
        >
          Cargar documento
        </Button>
      </div>

      {error ? (
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {error}
        </div>
      ) : null}

      <section aria-labelledby="personas-titulo">
        <h2 id="personas-titulo">Personas del expediente</h2>
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-[var(--color-border)]">
              <th className="py-2">Persona</th>
              <th className="py-2">Identificación</th>
              <th className="py-2">Rol</th>
              <th className="py-2">Desde</th>
            </tr>
          </thead>
          <tbody>
            {personasVigentes.map((vinculo) => (
              <tr
                key={`${vinculo.persona.id_persona}-${vinculo.fecha_inicio}`}
                className="border-b border-[var(--color-border-soft)]"
              >
                <td className="py-2">{vinculo.persona.nombre}</td>
                <td className="py-2">{vinculo.persona.identificacion ?? "—"}</td>
                <td className="py-2">
                  {vinculo.rol === "TITULAR"
                    ? "Titular"
                    : vinculo.rol === "COTITULAR"
                      ? "Cotitular"
                      : "Persona apoderada"}
                </td>
                <td className="py-2">{formatearFecha(vinculo.fecha_inicio)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section aria-labelledby="documentos-titulo">
        <h2 id="documentos-titulo">
          Documentos ({documentos.length}) · ordenados por prioridad
        </h2>

        {documentos.length === 0 ? (
          <p>Todavía no hay documentos cargados en este expediente.</p>
        ) : (
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2">Prior.</th>
                <th className="py-2">Tipo</th>
                <th className="py-2">Nombre identificador</th>
                <th className="py-2">Aportado por</th>
                <th className="py-2">Fecha del documento</th>
                <th className="py-2">Versión</th>
                <th className="py-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {documentos.map((documento) => (
                <tr
                  key={documento.id_documento}
                  className="border-b border-[var(--color-border-soft)]"
                >
                  <td className="py-2">{documento.prioridad}</td>
                  <td className="py-2 font-semibold">{documento.tipo_documento}</td>
                  <td className="py-2">{documento.nombre_identificador ?? "—"}</td>
                  <td className="py-2">{documento.persona ?? "—"}</td>
                  <td className="py-2">
                    {documento.version_vigente
                      ? formatearFecha(documento.version_vigente.fecha_documento)
                      : "—"}
                  </td>
                  <td className="py-2">
                    v{documento.version_vigente?.numero_version ?? "—"}
                    {documento.numero_versiones > 1 ? (
                      <>
                        {" · "}
                        <Link
                          href={`/sigeda/expedientes/${abonado.numero_paja}/documentos/${documento.id_documento}/versiones`}
                          className="text-[var(--color-primary)]"
                        >
                          ver versiones
                        </Link>
                      </>
                    ) : null}
                  </td>
                  <td className="py-2">
                    {documento.version_vigente ? (
                      <button
                        type="button"
                        className="text-[var(--color-primary)] underline"
                        onClick={() =>
                          verDocumento(
                            documento.id_documento,
                            documento.version_vigente!.numero_version,
                            documento.version_vigente!.nombre_original,
                          )
                        }
                      >
                        Ver
                      </button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {urlVisor ? (
        <section aria-labelledby="visor-titulo">
          <h2 id="visor-titulo">Vista del documento · {nombreVisor}</h2>
          <iframe
            title={`Documento ${nombreVisor}`}
            src={urlVisor}
            className="h-[600px] w-full rounded-[var(--radius-md)] border border-[var(--color-border)]"
          />
        </section>
      ) : null}
    </main>
  );
}
