"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { obtenerCuarentena } from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import { formatearFechaHora, formatearTamano } from "@/features/sigeda/respaldos-estado";
import type { ArchivoCuarentena } from "@/features/sigeda/types";

/**
 * Sub-pantalla de PAN-08: archivos en cuarentena (RNF-03): archivos
 * físicos en el almacén cifrado sin registro en `version_documento`
 * (p. ej. tras un corte de luz durante una carga). Se apartan, no se
 * borran. Textos literales del Prototipos v1.1.
 */
export default function CuarentenaPage() {
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [archivos, setArchivos] = useState<ArchivoCuarentena[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    obtenerCuarentena(sesion.token)
      .then(setArchivos)
      .catch((err) =>
        setError(
          err instanceof Error
            ? err.message
            : "No fue posible consultar los archivos en cuarentena.",
        ),
      )
      .finally(() => setCargando(false));
  }, [cargandoSesion, sesion, router]);

  if (cargandoSesion || cargando) {
    return <p className="p-6">Cargando…</p>;
  }

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <nav aria-label="Ruta">
        <Link href="/sigeda/respaldos" className="text-[var(--color-primary)]">
          Respaldos
        </Link>
        {" › "}
        <span>Archivos en cuarentena</span>
      </nav>

      <div className="flex flex-col gap-1">
        <h1>Archivos en cuarentena</h1>
        <p>
          Archivos que estaban en la carpeta de documentos pero no tienen
          registro en la base (por ejemplo, tras un corte de luz durante una
          carga). Se apartan, no se borran.
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

      {archivos && archivos.length === 0 ? (
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
        >
          No hay archivos en cuarentena.
        </div>
      ) : null}

      {archivos && archivos.length > 0 ? (
        <>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2">Archivo</th>
                <th className="py-2">Tamaño</th>
                <th className="py-2">Detectado el</th>
                <th className="py-2">Motivo</th>
              </tr>
            </thead>
            <tbody>
              {archivos.map((archivo) => (
                <tr
                  key={archivo.nombre_archivo}
                  className="border-b border-[var(--color-border-soft)]"
                >
                  <td className="py-2">{archivo.nombre_archivo}</td>
                  <td className="py-2">{formatearTamano(archivo.tamano_bytes)}</td>
                  <td className="py-2">{formatearFechaHora(archivo.fecha_deteccion)}</td>
                  <td className="py-2">{archivo.motivo}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-sm text-[var(--color-text-muted)]">
            Si alguno corresponde a un documento real, vuelva a cargarlo desde
            el expediente. Cada detección quedó en la bitácora.
          </p>
        </>
      ) : null}

      <div>
        <Button variant="secondary" onClick={() => router.push("/sigeda/respaldos")}>
          Volver a respaldos
        </Button>
      </div>
    </main>
  );
}
