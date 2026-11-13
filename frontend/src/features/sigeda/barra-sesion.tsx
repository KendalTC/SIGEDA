"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useSigedaAuth } from "./auth-context";
import { InsigniaRespaldo } from "./insignia-respaldo";
import { perfilDisplay } from "./types";

/**
 * Barra superior mínima (decisión 3 del plan de hoy): todavía no
 * existe el menú lateral completo de PAN-02 (Incremento 2b), pero
 * "Mi cuenta" y "Cerrar sesión" (RF-20, RNF-09) tienen que ser
 * alcanzables desde cualquier pantalla ya hoy.
 */
export function BarraSesion() {
  const router = useRouter();
  const { sesion, cerrarSesion } = useSigedaAuth();
  const [saliendo, setSaliendo] = useState(false);

  // RF-20: con una contraseña temporal pendiente de cambiar, no se
  // ofrece ninguna salida hacia el resto de la aplicación — PAN-01 ya
  // la obliga a terminar "Cree su contraseña" primero (ver
  // GuardiaContrasenaTemporal).
  if (!sesion || sesion.cuenta.es_contrasena_temporal) {
    return null;
  }

  async function manejarCerrarSesion() {
    setSaliendo(true);

    try {
      await cerrarSesion();
    } finally {
      router.push("/sigeda/login");
    }
  }

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--color-border)] bg-surface px-6 py-3">
      <div className="flex flex-wrap items-center gap-4">
        <span>
          {perfilDisplay(sesion.cuenta.perfil)} (usuario{" "}
          {sesion.cuenta.usuario})
        </span>
        <Link
          href="/sigeda/buscar"
          className="text-[var(--color-primary)] underline"
        >
          Buscar expediente
        </Link>
        <Link
          href="/sigeda/cuenta"
          className="text-[var(--color-primary)] underline"
        >
          Mi cuenta
        </Link>
        <Link
          href="/sigeda/respaldos"
          className="text-[var(--color-primary)] underline"
        >
          Respaldos
        </Link>
      </div>

      <div className="flex flex-wrap items-center gap-4">
        <InsigniaRespaldo />
        <span className="text-sm text-[var(--color-text-muted)]">
          Se cierra tras 15 min sin uso
        </span>
        <button
          type="button"
          onClick={manejarCerrarSesion}
          disabled={saliendo}
          className="text-sm font-semibold text-[var(--color-primary)] underline disabled:cursor-not-allowed disabled:opacity-55"
        >
          Cerrar sesión
        </button>
      </div>
    </header>
  );
}
