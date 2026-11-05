"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";

import { descargarVersion } from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";

type Version = {
  numero_version: number;
  nombre_original: string;
  formato: string;
  tamano_bytes: number;
  fecha_documento: string;
  fecha_carga: string;
  hash_sha256: string;
};

function formatearFecha(fechaIso: string): string {
  return fechaIso.split("-").reverse().join("/");
}

export default function VersionesDocumentoPage({
  params,
}: {
  params: Promise<{ numeroPaja: string; idDocumento: string }>;
}) {
  const { numeroPaja, idDocumento } = use(params);
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();
  const [tipoDocumento, setTipoDocumento] = useState("");
  const [versiones, setVersiones] = useState<Version[]>([]);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    fetch(`/api/sigeda/documentos/${idDocumento}/versiones/`, {
      headers: { Authorization: `Bearer ${sesion.token}` },
    })
      .then((respuesta) => respuesta.json())
      .then((datos) => {
        setTipoDocumento(datos.tipo_documento);
        setVersiones(datos.versiones);
      })
      .finally(() => setCargando(false));
  }, [cargandoSesion, sesion, idDocumento, router]);

  async function ver(numeroVersion: number) {
    if (!sesion) return;
    const blob = await descargarVersion(sesion.token, Number(idDocumento), numeroVersion);
    window.open(URL.createObjectURL(blob), "_blank");
  }

  if (cargandoSesion || cargando) {
    return <p className="p-6">Cargando…</p>;
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
      <nav aria-label="Ruta">
        <Link
          href={`/sigeda/expedientes/${numeroPaja}`}
          className="text-[var(--color-primary)]"
        >
          Expediente {numeroPaja}
        </Link>
        {" › "}
        <span>Versiones</span>
      </nav>

      <h1>Versiones · {tipoDocumento}</h1>
      <p>
        Expediente {numeroPaja} · Ninguna versión se borra ni se sobrescribe.
      </p>

      <table className="w-full border-collapse text-left">
        <thead>
          <tr className="border-b border-[var(--color-border)]">
            <th className="py-2">Versión</th>
            <th className="py-2">Fecha del documento</th>
            <th className="py-2">Cargada el</th>
            <th className="py-2">Archivo</th>
            <th className="py-2">
              <span className="sr-only">Acciones</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {versiones.map((version, indice) => (
            <tr
              key={version.numero_version}
              className="border-b border-[var(--color-border-soft)]"
            >
              <td className="py-2 font-semibold">
                v{version.numero_version}
                {indice === 0 ? " · vigente" : ""}
              </td>
              <td className="py-2">{formatearFecha(version.fecha_documento)}</td>
              <td className="py-2">
                {new Date(version.fecha_carga).toLocaleString("es-CR")}
              </td>
              <td className="py-2">
                {version.nombre_original} ·{" "}
                {(version.tamano_bytes / (1024 * 1024)).toFixed(1).replace(".", ",")} MB
              </td>
              <td className="py-2">
                <button
                  type="button"
                  className="text-[var(--color-primary)] underline"
                  onClick={() => ver(version.numero_version)}
                >
                  Ver
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
