"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { obtenerRespaldos } from "./api";
import { useSigedaAuth } from "./auth-context";
import { calcularResumen, formatearFechaHora } from "./respaldos-estado";

type Tono = "ok" | "warn" | "err";

const ESTILOS_TONO: Record<Tono, string> = {
  ok: "border-[var(--color-success)] bg-[var(--color-success-soft)] text-[var(--color-success)]",
  warn: "border-[var(--color-warning)] bg-[var(--color-warning-soft)] text-[var(--color-warning)]",
  err: "border-[var(--color-danger)] bg-[var(--color-danger-soft)] text-[var(--color-danger)]",
};

/**
 * Insignia global de respaldo (RF-16, ficha PAN-08): verde/ámbar/rojo
 * con texto en los tres casos (nunca solo color, guía de estilo de
 * SIGEDA), visible en cualquier pantalla autenticada; es un enlace a
 * PAN-08. Si la consulta falla (p. ej. mientras el backend de
 * respaldos todavía se está construyendo), no muestra nada en vez de
 * tumbar el resto de la barra con un error permanente.
 */
export function InsigniaRespaldo() {
  const { sesion } = useSigedaAuth();
  const [texto, setTexto] = useState<string | null>(null);
  const [tono, setTono] = useState<Tono>("ok");

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
          setTono("err");
          setTexto("Sin respaldos ✕");
          return;
        }

        if (estadoGlobal === "completo" && ultimoCompleto) {
          setTono("ok");
          setTexto(`Último respaldo: ${formatearFechaHora(ultimoCompleto.fecha_hora)} ✓`);
          return;
        }

        setTono("warn");

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
    <Link
      href="/sigeda/respaldos"
      className={[
        "inline-flex items-center rounded-full border px-3 py-1 text-sm font-semibold",
        ESTILOS_TONO[tono],
      ].join(" ")}
    >
      {texto}
    </Link>
  );
}
