"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { obtenerRespaldos } from "./api";
import { useSigedaAuth } from "./auth-context";
import { CLASE_ENLACE_NAV, CLASE_ICONO_NAV } from "./nav-estilos";
import { calcularResumen, formatearFechaHora } from "./respaldos-estado";

/**
 * Insignia global de respaldo (RF-16, ficha PAN-08): visible en
 * cualquier pantalla autenticada; es un enlace a PAN-08, con el mismo
 * estilo que "Mi cuenta"/"Cerrar sesión" (decisión del 23/11/2026,
 * pedido de Kendal — antes era una insignia verde/ámbar/roja, pero el
 * texto ya dice la causa por sí solo: "Sin respaldos", "...falló",
 * "...pendiente"). Si la consulta falla (p. ej. mientras el backend
 * de respaldos todavía se está construyendo), no muestra nada en vez
 * de tumbar el resto de la barra con un error permanente.
 */
export function InsigniaRespaldo() {
  const { sesion } = useSigedaAuth();
  const [texto, setTexto] = useState<string | null>(null);

  useEffect(() => {
    if (!sesion) {
      setTexto(null);
      return;
    }

    let cancelado = false;

    obtenerRespaldos(sesion.token)
      .then((respuesta) => {
        if (cancelado) return;

        const { estadoGlobal, ultimoCompleto, ultimoIntento } = calcularResumen(
          respuesta.respaldos,
          respuesta.resumen,
        );

        if (estadoGlobal === "sin_respaldos") {
          setTexto("Sin respaldos ✕");
          return;
        }

        if (estadoGlobal === "completo" && ultimoCompleto) {
          setTexto(`Último respaldo: ${formatearFechaHora(ultimoCompleto.fecha_hora)} ✓`);
          return;
        }

        if (estadoGlobal === "fallido") {
          setTexto(
            ultimoCompleto
              ? `Último respaldo: ${formatearFechaHora(ultimoCompleto.fecha_hora)} · el intento de hoy falló ⚠`
              : "El último intento de respaldo falló ⚠",
          );
          return;
        }

        setTexto(
          ultimoCompleto
            ? `Último respaldo: ${formatearFechaHora(ultimoCompleto.fecha_hora)} · un intento quedó pendiente ⚠`
            : ultimoIntento
              ? `Respaldo de ${formatearFechaHora(ultimoIntento.fecha_hora)} pendiente ⚠`
              : null,
        );
      })
      .catch(() => {
        if (!cancelado) setTexto(null);
      });

    return () => {
      cancelado = true;
    };
  }, [sesion]);

  if (!sesion || sesion.cuenta.es_contrasena_temporal || !texto) {
    return null;
  }

  return (
    <Link href="/sigeda/respaldos" className={`${CLASE_ENLACE_NAV} px-3 py-2 text-[13.5px]`}>
      <svg
        width="17"
        height="17"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className={CLASE_ICONO_NAV}
      >
        <ellipse cx="12" cy="5.5" rx="8" ry="2.6" />
        <path d="M4 5.5v5.8c0 1.4 3.6 2.6 8 2.6s8-1.2 8-2.6V5.5" />
        <path d="M4 11.3v5.8c0 1.4 3.6 2.6 8 2.6s8-1.2 8-2.6v-5.8" />
      </svg>
      {texto}
    </Link>
  );
}
