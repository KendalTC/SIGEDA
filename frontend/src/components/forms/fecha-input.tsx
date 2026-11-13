"use client";

import { useEffect, useState } from "react";

import { Input } from "@/components/ui/input";

type FechaInputProps = {
  id: string;
  valorIso: string;
  onChangeIso: (iso: string) => void;
  hasError?: boolean;
};

function isoATexto(iso: string): string {
  const [anio, mes, dia] = iso.split("-");
  if (!anio || !mes || !dia) return "";
  return `${dia}/${mes}/${anio}`;
}

function textoAIso(texto: string): string | null {
  const coincide = texto.match(/^(\d{2})\/(\d{2})\/(\d{4})$/);
  if (!coincide) return null;
  const [, dia, mes, anio] = coincide;
  return `${anio}-${mes}-${dia}`;
}

function aplicarMascara(entrada: string): string {
  const soloDigitos = entrada.replace(/\D/g, "").slice(0, 8);
  const dia = soloDigitos.slice(0, 2);
  const mes = soloDigitos.slice(2, 4);
  const anio = soloDigitos.slice(4, 8);

  return [dia, mes, anio].filter(Boolean).join("/");
}

/**
 * Campo de fecha dd/mm/aaaa (guía de estilo de SIGEDA): el valor que
 * entra y sale siempre es ISO (yyyy-mm-dd), para no tocar el contrato
 * con el backend; solo cambia cómo se ve y se escribe. Reemplaza al
 * <input type="date"> nativo, que mostraba mm/dd/aaaa según el idioma
 * del navegador (hallazgo de la sección 7 del Prototipos v1.1).
 */
export function FechaInput({
  id,
  valorIso,
  onChangeIso,
  hasError,
}: FechaInputProps) {
  const [texto, setTexto] = useState(() => isoATexto(valorIso));

  useEffect(() => {
    setTexto(isoATexto(valorIso));
  }, [valorIso]);

  return (
    <Input
      id={id}
      inputMode="numeric"
      placeholder="dd/mm/aaaa"
      value={texto}
      hasError={hasError}
      onChange={(e) => {
        const nuevoTexto = aplicarMascara(e.target.value);
        setTexto(nuevoTexto);

        if (nuevoTexto === "") {
          // Campo vaciado a propósito (filtros opcionales, p. ej. PAN-04):
          // se avisa con "" en vez de dejar el iso anterior vigente por
          // detrás de un campo que la usuaria ve vacío.
          onChangeIso("");
          return;
        }

        const iso = textoAIso(nuevoTexto);
        if (iso) {
          onChangeIso(iso);
        }
      }}
    />
  );
}
