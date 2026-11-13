"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { buscarPersonas } from "./api";
import type { PersonaBusqueda } from "./types";

type BuscadorPersonaProps = {
  readonly token: string;
  readonly id: string;
  readonly etiqueta: string;
  readonly placeholder?: string;
  readonly ayuda?: string;
  /** Elegida una fila, se limpia la búsqueda (el llamador decide qué
   * hacer con la persona: llenar el titular, agregarla al expediente,
   * etc.). */
  readonly onElegir: (persona: PersonaBusqueda) => void;
};

/**
 * Buscador compartido de personas ya registradas (RF-02/RF-21, D-04,
 * D-06): busca por nombre o identificación con el mismo endpoint
 * (`GET /abonados/personas/buscar/`) y muestra sus vínculos vigentes
 * para que la usuaria no duplique a alguien que ya tiene expediente.
 */
export function BuscadorPersona({
  token,
  id,
  etiqueta,
  placeholder,
  ayuda,
  onElegir,
}: BuscadorPersonaProps) {
  const [texto, setTexto] = useState("");
  const [resultados, setResultados] = useState<PersonaBusqueda[]>([]);
  const [buscando, setBuscando] = useState(false);
  const [buscado, setBuscado] = useState(false);

  useEffect(() => {
    const consulta = texto.trim();
    const esCorta = consulta.length < 2;

    // Las consultas demasiado cortas se limpian en el siguiente tick (no
    // sincrónicamente en el cuerpo del efecto) y las demás esperan un
    // respiro antes de consultar, para no mandar una petición por tecla.
    const identificador = window.setTimeout(
      async () => {
        if (esCorta) {
          setResultados([]);
          setBuscado(false);
          setBuscando(false);
          return;
        }

        setBuscando(true);
        try {
          const datos = await buscarPersonas(token, consulta);
          setResultados(datos);
        } catch {
          setResultados([]);
        } finally {
          setBuscando(false);
          setBuscado(true);
        }
      },
      esCorta ? 0 : 350,
    );

    return () => window.clearTimeout(identificador);
  }, [texto, token]);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-col gap-1.5">
        <label htmlFor={id}>{etiqueta}</label>
        <Input
          id={id}
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder={placeholder ?? "Escriba el nombre o la cédula"}
          autoComplete="off"
        />
        {ayuda ? (
          <p className="text-sm text-[var(--color-text-muted)]">{ayuda}</p>
        ) : null}
      </div>

      {buscando ? (
        <p role="status" className="text-sm text-[var(--color-text-muted)]">
          Buscando…
        </p>
      ) : null}

      {!buscando && buscado && resultados.length === 0 ? (
        <p role="status" className="text-sm text-[var(--color-text-muted)]">
          No se encontraron personas registradas con ese dato.
        </p>
      ) : null}

      {resultados.length > 0 ? (
        <table className="w-full border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--color-border)]">
              <th className="py-1.5">Persona</th>
              <th className="py-1.5">Identificación</th>
              <th className="py-1.5">Vínculos actuales</th>
              <th className="py-1.5" />
            </tr>
          </thead>
          <tbody>
            {resultados.map((persona) => (
              <tr
                key={persona.id_persona}
                className="border-b border-[var(--color-border-soft)]"
              >
                <td className="py-1.5">{persona.nombre}</td>
                <td className="py-1.5">{persona.identificacion ?? "—"}</td>
                <td className="py-1.5">
                  {persona.vinculos_actuales.length > 0
                    ? persona.vinculos_actuales.join(", ")
                    : "Sin vínculos vigentes"}
                </td>
                <td className="py-1.5">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => {
                      onElegir(persona);
                      setTexto("");
                      setResultados([]);
                      setBuscado(false);
                    }}
                  >
                    Elegir
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
