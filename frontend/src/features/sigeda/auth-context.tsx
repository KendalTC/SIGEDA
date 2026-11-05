"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

import { sigedaLogin, sigedaLogout } from "./api";
import type { Cuenta } from "./types";

const STORAGE_KEY = "sigeda_sesion";

type Sesion = { token: string; cuenta: Cuenta };

type SigedaAuthContextValue = {
  sesion: Sesion | null;
  cargando: boolean;
  iniciarSesion: (usuario: string, contrasena: string) => Promise<void>;
  cerrarSesion: () => Promise<void>;
};

const SigedaAuthContext = createContext<SigedaAuthContextValue | null>(null);

function leerSesionGuardada(): Sesion | null {
  try {
    const bruto = window.localStorage.getItem(STORAGE_KEY);
    return bruto ? (JSON.parse(bruto) as Sesion) : null;
  } catch {
    return null;
  }
}

export function SigedaAuthProvider({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [sesion, setSesion] = useState<Sesion | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    setSesion(leerSesionGuardada());
    setCargando(false);
  }, []);

  const iniciarSesion = async (usuario: string, contrasena: string) => {
    const respuesta = await sigedaLogin(usuario, contrasena);
    const nuevaSesion: Sesion = { token: respuesta.token, cuenta: respuesta.cuenta };

    setSesion(nuevaSesion);

    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nuevaSesion));
    } catch {
      // Almacenamiento no disponible (ej. navegación privada): la
      // sesión sigue viva en memoria para esta pestaña.
    }
  };

  const cerrarSesion = async () => {
    if (sesion) {
      try {
        await sigedaLogout(sesion.token);
      } catch {
        // Si falla la llamada igual se limpia la sesión local.
      }
    }

    setSesion(null);

    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // Sin almacenamiento disponible: nada que limpiar.
    }
  };

  return (
    <SigedaAuthContext.Provider
      value={{ sesion, cargando, iniciarSesion, cerrarSesion }}
    >
      {children}
    </SigedaAuthContext.Provider>
  );
}

export function useSigedaAuth(): SigedaAuthContextValue {
  const context = useContext(SigedaAuthContext);

  if (!context) {
    throw new Error("useSigedaAuth debe usarse dentro de SigedaAuthProvider.");
  }

  return context;
}
