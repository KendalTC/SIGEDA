"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

import { sigedaLogin, sigedaLogout } from "./api";
import {
  borrarSesionLocal,
  guardarSesionLocal,
  leerSesionGuardada,
  type SesionGuardada,
} from "./sesion-storage";

export type Sesion = SesionGuardada;

type SigedaAuthContextValue = {
  sesion: Sesion | null;
  cargando: boolean;
  iniciarSesion: (usuario: string, contrasena: string) => Promise<Sesion>;
  /**
   * Fija la sesión directamente, sin llamar a `/auth/login/`. Lo usa
   * PAN-01 tras terminar el flujo "Cree su contraseña" (RF-20): el
   * token nuevo ya lo dio `cambiar-contrasena/`, no hay que volver a
   * autenticarse.
   */
  establecerSesion: (sesion: Sesion) => void;
  cerrarSesion: () => Promise<void>;
};

const SigedaAuthContext = createContext<SigedaAuthContextValue | null>(null);

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
    guardarSesionLocal(nuevaSesion);

    return nuevaSesion;
  };

  const establecerSesion = (nuevaSesion: Sesion) => {
    setSesion(nuevaSesion);
    guardarSesionLocal(nuevaSesion);
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
    borrarSesionLocal();
  };

  return (
    <SigedaAuthContext.Provider
      value={{ sesion, cargando, iniciarSesion, establecerSesion, cerrarSesion }}
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
