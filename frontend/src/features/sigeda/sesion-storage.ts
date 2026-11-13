/**
 * Único lugar que conoce la clave de `localStorage` de la sesión de
 * SIGEDA. Separado de `auth-context.tsx` para que `api.ts` también
 * pueda limpiar la sesión guardada (caso: el servidor ya expiró el
 * token por inactividad, RNF-09) sin crear un import circular entre
 * ambos módulos.
 */

import type { Cuenta } from "./types";

export const SIGEDA_STORAGE_KEY = "sigeda_sesion";

export type SesionGuardada = { token: string; cuenta: Cuenta };

export function leerSesionGuardada(): SesionGuardada | null {
  try {
    const bruto = window.localStorage.getItem(SIGEDA_STORAGE_KEY);
    return bruto ? (JSON.parse(bruto) as SesionGuardada) : null;
  } catch {
    return null;
  }
}

export function guardarSesionLocal(sesion: SesionGuardada): void {
  try {
    window.localStorage.setItem(SIGEDA_STORAGE_KEY, JSON.stringify(sesion));
  } catch {
    // Almacenamiento no disponible (ej. navegación privada): la sesión
    // sigue viva en memoria para esta pestaña.
  }
}

export function borrarSesionLocal(): void {
  try {
    window.localStorage.removeItem(SIGEDA_STORAGE_KEY);
  } catch {
    // Sin almacenamiento disponible: nada que limpiar.
  }
}
