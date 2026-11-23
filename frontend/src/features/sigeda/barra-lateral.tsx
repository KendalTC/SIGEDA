"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { useSigedaAuth } from "./auth-context";
import { InsigniaRespaldo } from "./insignia-respaldo";
import { CLASE_ENLACE_NAV, CLASE_ENLACE_NAV_ACTIVO, CLASE_ICONO_NAV } from "./nav-estilos";
import { perfilDisplay } from "./types";

type EnlaceNav = {
  href: string;
  etiqueta: string;
  activaCon?: string[];
  icono: ReactNode;
};

type GrupoNav = {
  titulo: string;
  enlaces: EnlaceNav[];
};

const GRUPOS: GrupoNav[] = [
  {
    titulo: "Expediente",
    enlaces: [
      {
        href: "/sigeda/buscar",
        etiqueta: "Buscar expediente",
        activaCon: ["/sigeda/expedientes", "/sigeda/abonados/nuevo", "/sigeda/abonados/"],
        icono: (
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.3-4.3" />
          </svg>
        ),
      },
      {
        href: "/sigeda/abonados/importar",
        etiqueta: "Importar listado de SADA",
        icono: (
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
            <path d="M17 8l-5-5-5 5" />
            <path d="M12 3v12" />
          </svg>
        ),
      },
    ],
  },
  {
    titulo: "Catálogos",
    enlaces: [
      {
        href: "/sigeda/tipos-documento",
        etiqueta: "Tipos de documento",
        icono: (
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
            <path d="M14 2v6h6" />
            <path d="M9.5 13h5" />
            <path d="M9.5 17h5" />
          </svg>
        ),
      },
      {
        href: "/sigeda/completitud",
        etiqueta: "Completitud",
        icono: (
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="9" />
            <path d="M8.3 12.3l2.3 2.3 5-5.3" />
          </svg>
        ),
      },
    ],
  },
  {
    titulo: "Sistema",
    enlaces: [
      {
        href: "/sigeda/bitacora",
        etiqueta: "Bitácora",
        icono: (
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="9" />
            <path d="M12 7.5v5l3.5 2" />
          </svg>
        ),
      },
      {
        href: "/sigeda/respaldos",
        etiqueta: "Respaldos",
        icono: (
          <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <ellipse cx="12" cy="5.5" rx="8" ry="2.6" />
            <path d="M4 5.5v5.8c0 1.4 3.6 2.6 8 2.6s8-1.2 8-2.6V5.5" />
            <path d="M4 11.3v5.8c0 1.4 3.6 2.6 8 2.6s8-1.2 8-2.6v-5.8" />
          </svg>
        ),
      },
    ],
  },
];


/**
 * Panel lateral de navegación (rediseño del 23/11/2026, aprobado con
 * Kendal sobre prototipos): reemplaza la barra superior de enlaces de
 * texto por un menú agrupado, para que sea más fácil ubicar cada
 * pantalla. Mismo criterio de visibilidad que la barra anterior
 * (RF-20): nada con una contraseña temporal pendiente.
 */
export function BarraLateral() {
  const pathname = usePathname();
  const router = useRouter();
  const { sesion, cerrarSesion } = useSigedaAuth();
  const [saliendo, setSaliendo] = useState(false);

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

  function esActivo(enlace: EnlaceNav): boolean {
    if (pathname === enlace.href || pathname.startsWith(`${enlace.href}/`)) {
      return true;
    }

    return (enlace.activaCon ?? []).some((prefijo) => pathname.startsWith(prefijo));
  }

  return (
    <nav
      aria-label="Navegación principal"
      className="relative flex w-[260px] shrink-0 flex-col overflow-hidden bg-[linear-gradient(185deg,var(--color-primary-active),#06324c)] text-white"
    >
      <span
        className="sigeda-orb"
        style={{
          width: 320,
          height: 320,
          top: -110,
          right: -120,
          opacity: 0.5,
          background: "radial-gradient(circle at 30% 30%, #55AEDC, transparent 70%)",
          animationDuration: "17s",
        }}
      />
      <span
        className="sigeda-orb"
        style={{
          width: 260,
          height: 260,
          bottom: 60,
          left: -100,
          opacity: 0.4,
          background: "radial-gradient(circle at 50% 50%, #7DC6EA, transparent 70%)",
          animationDuration: "21s",
          animationDelay: "-5s",
        }}
      />

      <div className="relative z-10 flex h-full flex-col overflow-y-auto p-3.5">
        <Link
          href="/sigeda/buscar"
          className="sigeda-aparecer mb-3.5 flex items-center gap-2.5 rounded-xl px-2.5 py-1.5"
        >
          <span className="flex size-9 shrink-0 items-center justify-center rounded-[10px] bg-white/10">
            <svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <path d="M14 2v6h6" />
              <path d="M9 13h6" />
              <path d="M9 17h6" />
            </svg>
          </span>
          <span className="flex flex-col leading-tight">
            <span
              className="text-[16.5px] font-semibold tracking-tight"
              style={{ fontFamily: "var(--font-brand)" }}
            >
              SIGEDA
            </span>
            <span className="text-[11px] text-[#8FB3C7]">Bodegas y Pilas</span>
          </span>
        </Link>

        {GRUPOS.map((grupo) => (
          <div key={grupo.titulo} className="flex flex-col gap-0.5">
            <p className="px-3.5 pb-1.5 pt-3.5 text-[11px] font-bold uppercase tracking-[0.1em] text-[#6F93A6] first:pt-0">
              {grupo.titulo}
            </p>
            {grupo.enlaces.map((enlace) => {
              const activo = esActivo(enlace);

              return (
                <Link
                  key={enlace.href}
                  href={enlace.href}
                  aria-current={activo ? "page" : undefined}
                  className={[CLASE_ENLACE_NAV, activo ? CLASE_ENLACE_NAV_ACTIVO : ""].join(" ")}
                >
                  <span className={CLASE_ICONO_NAV} style={{ opacity: activo ? 1 : undefined }}>
                    {enlace.icono}
                  </span>
                  {enlace.etiqueta}
                </Link>
              );
            })}
          </div>
        ))}

        <div className="mt-auto flex flex-col gap-1.5 pt-3">
          <div className="flex items-center gap-2.5 rounded-xl bg-white/[0.06] px-3 py-2">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-white/[0.16] text-[13px] font-bold">
              {perfilDisplay(sesion.cuenta.perfil).charAt(0)}
            </span>
            <span className="flex min-w-0 flex-col leading-tight">
              <span className="truncate text-[13.5px] font-semibold text-white">
                {perfilDisplay(sesion.cuenta.perfil)}
              </span>
              <span className="text-[11.5px] text-[#8FB3C7]">Sesión activa</span>
            </span>
          </div>

          <InsigniaRespaldo />

          <div className="flex flex-col gap-0.5">
            <Link href="/sigeda/cuenta" className={`${CLASE_ENLACE_NAV} px-3 py-2 text-[13.5px]`}>
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={CLASE_ICONO_NAV}>
                <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
              Mi cuenta
            </Link>
            <button
              type="button"
              onClick={manejarCerrarSesion}
              disabled={saliendo}
              className={`${CLASE_ENLACE_NAV} px-3 py-2 text-[13.5px] disabled:cursor-not-allowed disabled:opacity-55`}
            >
              <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={CLASE_ICONO_NAV}>
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                <path d="M16 17l5-5-5-5" />
                <path d="M21 12H9" />
              </svg>
              Cerrar sesión
            </button>
          </div>
        </div>
      </div>
    </nav>
  );
}
