/**
 * Clases compartidas entre la barra lateral y la insignia de respaldo
 * (que vive dentro de ella), para que todos los enlaces del menú se
 * vean exactamente igual sin repetir la cadena de clases en dos
 * archivos.
 */
export const CLASE_ENLACE_NAV =
  "group flex items-center gap-3 rounded-xl px-3.5 py-2 text-sm font-medium text-[#AFCBDC] transition-[background-color,color,transform] duration-200 ease-out hover:translate-x-[3px] hover:bg-white/10 hover:text-[#EAF4FA] active:translate-x-[3px] active:scale-[0.97]";

export const CLASE_ENLACE_NAV_ACTIVO = "bg-white/[0.18] font-semibold text-white hover:bg-white/[0.22]";

export const CLASE_ICONO_NAV = "shrink-0 opacity-80 transition-opacity group-hover:opacity-100";
