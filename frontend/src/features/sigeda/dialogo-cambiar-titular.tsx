"use client";

import {
  forwardRef,
  useImperativeHandle,
  useRef,
  useState,
  type FormEvent,
} from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { FechaInput } from "@/components/forms/fecha-input";
import { ApiError } from "@/lib/api/errors";
import { cambiarTitular, esPersonaExistente } from "./api";
import { BuscadorPersona } from "./buscador-persona";
import {
  AYUDA_FORMATOS_IDENTIFICACION,
  OPCIONES_TIPO_IDENTIFICACION,
} from "./identificacion";
import { hoyComoFechaIso } from "./validacion-archivo";
import type {
  PersonaBusqueda,
  PersonaExistenteConflicto,
  TipoIdentificacion,
} from "./types";

export type DialogoCambiarTitularHandle = {
  abrir: () => void;
};

type DialogoCambiarTitularProps = {
  readonly token: string;
  readonly numeroPaja: string;
  readonly titularActualNombre: string;
  /** Se llama tras el cambio con éxito, para que el llamador cierre su
   * propio estado y vuelva a cargar los datos. */
  readonly onCambiado: () => void;
};

/**
 * D-04 Cambiar titular (RF-13). Compartido entre PAN-04 (hallazgo H-02:
 * se abre directo, sin pasar por "Modificar abonado") y PAN-06
 * "Modificar abonado y personas". Si la persona elegida ya es
 * cotitular vigente, el backend cierra ese vínculo automáticamente al
 * abrir el de titular (decisión del 13/11/2026, no hay nada que avisar
 * acá: la base lo exige para no romper el titular único).
 */
export const DialogoCambiarTitular = forwardRef<
  DialogoCambiarTitularHandle,
  DialogoCambiarTitularProps
>(function DialogoCambiarTitular(
  { token, numeroPaja, titularActualNombre, onCambiado },
  ref,
) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  const [personaElegida, setPersonaElegida] = useState<PersonaBusqueda | null>(
    null,
  );
  const [mostrarPersonaNueva, setMostrarPersonaNueva] = useState(false);
  const [nombre, setNombre] = useState("");
  const [tipoIdentificacion, setTipoIdentificacion] =
    useState<TipoIdentificacion>("CEDULA_FISICA");
  const [identificacion, setIdentificacion] = useState("");
  const [fechaCambio, setFechaCambio] = useState(hoyComoFechaIso());
  const [errorPersona, setErrorPersona] = useState<string | null>(null);
  const [errorFecha, setErrorFecha] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflicto, setConflicto] =
    useState<PersonaExistenteConflicto | null>(null);
  const [enviando, setEnviando] = useState(false);

  function limpiar() {
    setPersonaElegida(null);
    setMostrarPersonaNueva(false);
    setNombre("");
    setTipoIdentificacion("CEDULA_FISICA");
    setIdentificacion("");
    setFechaCambio(hoyComoFechaIso());
    setErrorPersona(null);
    setErrorFecha(null);
    setError(null);
    setConflicto(null);
    setEnviando(false);
  }

  useImperativeHandle(ref, () => ({
    abrir() {
      limpiar();
      dialogRef.current?.showModal();
    },
  }));

  function elegirPersonaExistente(persona: PersonaBusqueda) {
    setPersonaElegida(persona);
    setMostrarPersonaNueva(false);
    setConflicto(null);
    setErrorPersona(null);
    setError(null);
  }

  async function enviar(idPersonaForzado?: number) {
    setEnviando(true);
    setError(null);

    try {
      await cambiarTitular(token, numeroPaja, {
        persona: idPersonaForzado
          ? { id_persona: idPersonaForzado }
          : personaElegida
            ? { id_persona: personaElegida.id_persona }
            : {
                nombre: nombre.trim(),
                tipo_identificacion: tipoIdentificacion,
                identificacion: identificacion.trim(),
              },
        fecha_cambio: fechaCambio,
      });

      dialogRef.current?.close();
      onCambiado();
    } catch (err) {
      if (
        err instanceof ApiError &&
        err.status === 409 &&
        esPersonaExistente(err.payload)
      ) {
        setConflicto(err.payload.persona_existente);
        return;
      }

      setError(
        err instanceof Error ? err.message : "No fue posible cambiar el titular.",
      );
    } finally {
      setEnviando(false);
    }
  }

  async function manejarEnvio(evento: FormEvent) {
    evento.preventDefault();
    setErrorPersona(null);
    setErrorFecha(null);

    if (!personaElegida && !(mostrarPersonaNueva && nombre.trim() && identificacion.trim())) {
      setErrorPersona(
        "Busque a la persona que será el nuevo titular o agregue una persona nueva.",
      );
      return;
    }

    if (!fechaCambio) {
      setErrorFecha("Escriba la fecha del cambio.");
      return;
    }

    await enviar();
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="d04-titulo"
      className="m-auto w-[min(640px,calc(100vw-32px))] rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-background p-6 text-foreground shadow-[var(--shadow-lg)] backdrop:bg-[rgb(15_23_42_/_45%)]"
    >
      <form onSubmit={manejarEnvio} className="flex flex-col gap-4">
        <h2 id="d04-titulo">Cambiar titular · paja {numeroPaja}</h2>
        <p>
          Titular actual: <strong>{titularActualNombre}</strong>
        </p>

        <BuscadorPersona
          token={token}
          id="d04-buscar-persona"
          etiqueta="Nuevo titular (obligatorio)"
          ayuda="Busque una persona registrada o agregue una nueva."
          onElegir={elegirPersonaExistente}
        />

        {personaElegida ? (
          <p className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]">
            Nuevo titular elegido: <strong>{personaElegida.nombre}</strong> ·{" "}
            {personaElegida.identificacion ?? "—"}.{" "}
            <button
              type="button"
              className="underline"
              onClick={() => setPersonaElegida(null)}
            >
              Buscar otra
            </button>
          </p>
        ) : mostrarPersonaNueva ? (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="d04-nombre">Nombre completo (obligatorio)</label>
                <Input
                  id="d04-nombre"
                  value={nombre}
                  onChange={(e) => {
                    setNombre(e.target.value);
                    setErrorPersona(null);
                  }}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="d04-tipo-identificacion">
                  Tipo de identificación (obligatorio)
                </label>
                <Select
                  id="d04-tipo-identificacion"
                  value={tipoIdentificacion}
                  onChange={(e) =>
                    setTipoIdentificacion(e.target.value as TipoIdentificacion)
                  }
                >
                  {OPCIONES_TIPO_IDENTIFICACION.map((opcion) => (
                    <option key={opcion.valor} value={opcion.valor}>
                      {opcion.etiqueta}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex flex-col gap-1.5 sm:col-span-2">
                <label htmlFor="d04-identificacion">Número (obligatorio)</label>
                <Input
                  id="d04-identificacion"
                  value={identificacion}
                  placeholder="1-0000-0000"
                  onChange={(e) => {
                    setIdentificacion(e.target.value);
                    setErrorPersona(null);
                  }}
                />
                <p className="text-sm text-[var(--color-text-muted)]">
                  {AYUDA_FORMATOS_IDENTIFICACION}
                </p>
              </div>
            </div>
            <button
              type="button"
              className="self-start text-[var(--color-primary)] underline"
              onClick={() => setMostrarPersonaNueva(false)}
            >
              Buscar en vez de agregar una persona nueva
            </button>
          </div>
        ) : (
          <button
            type="button"
            className="self-start text-[var(--color-primary)] underline"
            onClick={() => setMostrarPersonaNueva(true)}
          >
            ¿No aparece? Agregar una persona nueva
          </button>
        )}

        {errorPersona ? (
          <p className="text-sm text-[var(--color-danger)]">⚠ {errorPersona}</p>
        ) : null}

        <div className="flex flex-col gap-1.5">
          <label htmlFor="d04-fecha-cambio">Fecha del cambio (obligatorio)</label>
          <FechaInput
            id="d04-fecha-cambio"
            valorIso={fechaCambio}
            hasError={Boolean(errorFecha)}
            onChangeIso={(iso) => {
              setFechaCambio(iso);
              setErrorFecha(null);
            }}
          />
          {errorFecha ? (
            <p className="text-sm text-[var(--color-danger)]">⚠ {errorFecha}</p>
          ) : null}
        </div>

        <div className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]">
          <p className="font-semibold">
            {titularActualNombre} dejará de verse como titular en búsquedas y
            pantallas.
          </p>
          <p>
            Queda en el historial de titulares con la fecha del cambio como
            fecha fin. Sus documentos se conservan. El tipo de abonado no
            cambia.
          </p>
        </div>

        {conflicto ? (
          <div className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]">
            <p className="font-semibold">
              Ya existe una persona con esa identificación:{" "}
              {conflicto.nombre}
              {conflicto.numero_paja_titular
                ? `, titular de la paja ${conflicto.numero_paja_titular}`
                : ""}
              .
            </p>
            <p>Si es la misma persona, use sus datos registrados para no duplicarla.</p>
            <div className="mt-2">
              <Button
                type="button"
                variant="secondary"
                isLoading={enviando}
                onClick={() => enviar(conflicto.id_persona)}
              >
                Usar esa persona
              </Button>
            </div>
          </div>
        ) : null}

        {error ? (
          <p role="alert" className="text-sm text-[var(--color-danger)]">
            ⚠ {error}
          </p>
        ) : null}

        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => dialogRef.current?.close()}
          >
            Cancelar
          </Button>
          <Button type="submit" isLoading={enviando}>
            Confirmar cambio de titular
          </Button>
        </div>
      </form>
    </dialog>
  );
});
