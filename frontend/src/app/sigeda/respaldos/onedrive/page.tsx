"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { obtenerRespaldos } from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import type { ResumenRespaldos } from "@/features/sigeda/types";

const NOTA_SOLO_LECTURA_ID = "onedrive-nota-solo-lectura";

/**
 * Sub-pantalla de PAN-08: "Configurar copia en OneDrive". Decisión 4
 * del plan de hoy: en este entorno de desarrollo la carpeta de OneDrive
 * es una variable de entorno del backend (`SIGEDA_BACKUP_ONEDRIVE_DIR`),
 * no un selector real de carpetas de Windows — por eso la ruta se
 * muestra tal cual la manda el backend, de solo lectura.
 *
 * SUPUESTO/decisión de alcance: el contrato de hoy no define un
 * endpoint para GUARDAR esta configuración (solo para leerla, dentro de
 * `GET /api/sigeda/respaldos/`); "Guardar configuración" queda
 * deshabilitado con una nota, en vez de fabricar un guardado que no
 * pasa a ningún lado (CLAUDE.md, regla 1).
 */
export default function ConfigurarOneDrivePage() {
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [resumen, setResumen] = useState<ResumenRespaldos | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    obtenerRespaldos(sesion.token)
      .then((respuesta) => setResumen(respuesta.resumen ?? {}))
      .catch((err) =>
        setError(
          err instanceof Error
            ? err.message
            : "No fue posible consultar la configuración.",
        ),
      )
      .finally(() => setCargando(false));
  }, [cargandoSesion, sesion, router]);

  if (cargandoSesion || cargando) {
    return <p className="p-6">Cargando…</p>;
  }

  const rutaOneDrive = resumen?.onedrive_ruta ?? null;
  const configurado = Boolean(resumen?.onedrive_configurado);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-8">
      <nav aria-label="Ruta">
        <Link href="/sigeda/respaldos" className="text-[var(--color-primary)]">
          Respaldos
        </Link>
        {" › "}
        <span>OneDrive</span>
      </nav>

      <div className="flex flex-col gap-1">
        <h1>Configurar copia en OneDrive</h1>
        <p>
          Copia adicional del respaldo cifrado en la carpeta de OneDrive de
          esta computadora. Solo si la ASADA confirma que su licencia de
          Microsoft incluye OneDrive (S-10).
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

      <div className="flex flex-col gap-1.5">
        <span id="onedrive-ruta-etiqueta">Carpeta de OneDrive sincronizada</span>
        <div
          aria-labelledby="onedrive-ruta-etiqueta"
          className="h-12 w-full rounded-[var(--radius-md)] border border-border bg-surface-muted px-4 text-[15px] leading-[48px] text-foreground"
        >
          {rutaOneDrive ?? "No configurada"}
        </div>
        <p className="text-sm text-[var(--color-text-muted)]">
          En el sistema real, «Elegir…» abre el selector de carpetas de
          Windows.
        </p>
      </div>

      <label className="flex items-start gap-2">
        <input type="checkbox" checked={configurado} disabled className="mt-1" />
        <span>
          Copiar cada respaldo también a OneDrive y verificar su huella
          SHA-256
        </span>
      </label>
      <p className="text-sm text-[var(--color-text-muted)]">
        El respaldo queda «completo» si al menos una copia se verifica (disco
        externo u OneDrive). Los archivos van cifrados: sin la clave no se
        pueden abrir.
      </p>

      <p id={NOTA_SOLO_LECTURA_ID} className="text-sm text-[var(--color-text-muted)]">
        Esta pantalla es de solo lectura: la carpeta y la copia a OneDrive se
        configuran por variable de entorno, no desde aquí.
      </p>

      <div className="flex justify-end gap-3">
        <Button variant="secondary" onClick={() => router.push("/sigeda/respaldos")}>
          Cancelar
        </Button>
        <Button disabled aria-describedby={NOTA_SOLO_LECTURA_ID}>
          Guardar configuración
        </Button>
      </div>
    </main>
  );
}
