"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { obtenerMiCuenta } from "./api";
import { useSigedaAuth } from "./auth-context";

const MINUTOS_AVISO = 14;
const MINUTOS_CIERRE = 15;
const MS_AVISO = MINUTOS_AVISO * 60 * 1000;
const MS_CIERRE = MINUTOS_CIERRE * 60 * 1000;
const EVENTOS_ACTIVIDAD = [
  "mousemove",
  "keydown",
  "mousedown",
  "touchstart",
  "scroll",
] as const;

/**
 * RNF-09 del lado del cliente: cierre de sesión a los 15 minutos de
 * inactividad, con el aviso D-08 a los 14. No renderiza nada si no
 * hay sesión. El reloj se recalcula cada segundo a partir de la marca
 * de "última actividad" (no decrementa un contador aparte) para no
 * desincronizarse si la pestaña estuvo en segundo plano.
 */
export function IdleWatcher() {
  const router = useRouter();
  const { sesion, cerrarSesion } = useSigedaAuth();

  const dialogRef = useRef<HTMLDialogElement>(null);
  const ultimaActividadRef = useRef(0);
  const avisoAbiertoRef = useRef(false);
  const [segundosRestantes, setSegundosRestantes] = useState(60);

  useEffect(() => {
    if (!sesion) return;

    ultimaActividadRef.current = Date.now();
    avisoAbiertoRef.current = false;

    function marcarActividad() {
      if (!avisoAbiertoRef.current) {
        ultimaActividadRef.current = Date.now();
      }
    }

    for (const evento of EVENTOS_ACTIVIDAD) {
      window.addEventListener(evento, marcarActividad, { passive: true });
    }

    const intervalo = window.setInterval(() => {
      const transcurrido = Date.now() - ultimaActividadRef.current;

      if (transcurrido >= MS_CIERRE) {
        avisoAbiertoRef.current = false;
        dialogRef.current?.close();
        cerrarSesion().finally(() => router.push("/sigeda/login"));
        return;
      }

      if (transcurrido >= MS_AVISO) {
        if (!avisoAbiertoRef.current) {
          avisoAbiertoRef.current = true;
          dialogRef.current?.showModal();
        }

        setSegundosRestantes(
          Math.max(0, Math.ceil((MS_CIERRE - transcurrido) / 1000)),
        );
      }
    }, 1000);

    return () => {
      for (const evento of EVENTOS_ACTIVIDAD) {
        window.removeEventListener(evento, marcarActividad);
      }
      window.clearInterval(intervalo);
    };
  }, [sesion, cerrarSesion, router]);

  async function manejarSeguirTrabajando() {
    avisoAbiertoRef.current = false;
    ultimaActividadRef.current = Date.now();
    dialogRef.current?.close();

    if (sesion) {
      try {
        await obtenerMiCuenta(sesion.token);
      } catch {
        // Si falla el "ping" la marca local ya se refrescó; el
        // vigilante sigue funcionando con el reloj del cliente.
      }
    }
  }

  async function manejarCerrarSesionDesdeAviso() {
    avisoAbiertoRef.current = false;
    dialogRef.current?.close();

    try {
      await cerrarSesion();
    } finally {
      router.push("/sigeda/login");
    }
  }

  if (!sesion) {
    return null;
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="d08-titulo"
      aria-describedby="d08-texto"
      onCancel={(evento) => evento.preventDefault()}
      className="m-auto w-[min(420px,calc(100vw-32px))] rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-background p-6 text-foreground shadow-[var(--shadow-lg)] backdrop:bg-[rgb(15_23_42_/_45%)]"
    >
      <div className="flex flex-col gap-4">
        <h2 id="d08-titulo">Su sesión se va a cerrar</h2>
        <p id="d08-texto">
          Lleva casi 15 minutos sin usar SIGEDA. Por seguridad, la sesión se
          cerrará en {segundosRestantes} segundos. Lo que no haya guardado se
          perderá.
        </p>
        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={manejarCerrarSesionDesdeAviso}
          >
            Cerrar sesión
          </Button>
          <Button type="button" onClick={manejarSeguirTrabajando}>
            Seguir trabajando
          </Button>
        </div>
      </div>
    </dialog>
  );
}
