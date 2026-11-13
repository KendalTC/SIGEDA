"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useSigedaAuth } from "./auth-context";

const RUTA_LOGIN = "/sigeda/login";

/**
 * RF-20: "cambio obligatorio al entrar" con una contraseña temporal.
 * El login ya deja la sesión activa (en memoria y en localStorage)
 * antes de que PAN-01 termine "Cree su contraseña" — sin esta guardia,
 * alguien podría navegar a cualquier otra ruta (o recargar la página)
 * y seguir usando la contraseña temporal indefinidamente, sin cambiarla
 * nunca. Mientras `es_contrasena_temporal` siga en `true`, cualquier
 * ruta que no sea el login redirige de vuelta.
 */
export function GuardiaContrasenaTemporal() {
  const { sesion, cargando } = useSigedaAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (cargando) return;

    if (sesion?.cuenta.es_contrasena_temporal && pathname !== RUTA_LOGIN) {
      router.replace(RUTA_LOGIN);
    }
  }, [cargando, sesion, pathname, router]);

  return null;
}
