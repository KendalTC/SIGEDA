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
import { agregarPersonaAsociada, esPersonaExistente } from "./api";
import { BuscadorPersona } from "./buscador-persona";
import {
  AYUDA_FORMATOS_IDENTIFICACION,
  OPCIONES_TIPO_IDENTIFICACION,
} from "./identificacion";
import { hoyComoFechaIso } from "./validacion-archivo";
import type {
  PersonaBusqueda,
  PersonaExistenteConflicto,
  RolAsociado,
  TipoIdentificacion,
} from "./types";

export type DialogoAgregarPersonaHandle = {
  abrir: () => void;
};

type DialogoAgregarPersonaProps = {
  readonly token: string;
  readonly numeroPaja: string;
  /** Se llama tras agregar la persona con éxito, para que el llamador
   * cierre su propio estado y vuelva a cargar los datos. */
  readonly onAgregada: () => void;
};

/**
 * D-06 Agregar persona asociada (RF-03). Compartido entre PAN-04 (el
 * expediente) y PAN-06 "Modificar abonado y personas": se monta una vez
 * en cada pantalla y se abre con `ref.current.abrir()`.
 */
export const DialogoAgregarPersona = forwardRef<
  DialogoAgregarPersonaHandle,
  DialogoAgregarPersonaProps
>(function DialogoAgregarPersona({ token, numeroPaja, onAgregada }, ref) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  const [personaElegida, setPersonaElegida] = useState<PersonaBusqueda | null>(
    null,
  );
  const [nombre, setNombre] = useState("");
  const [tipoIdentificacion, setTipoIdentificacion] =
    useState<TipoIdentificacion>("CEDULA_FISICA");
  const [identificacion, setIdentificacion] = useState("");
  const [rol, setRol] = useState<RolAsociado>("COTITULAR");
  const [fechaInicio, setFechaInicio] = useState(hoyComoFechaIso());
  const [errorNombre, setErrorNombre] = useState<string | null>(null);
  const [errorFecha, setErrorFecha] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflicto, setConflicto] =
    useState<PersonaExistenteConflicto | null>(null);
  const [enviando, setEnviando] = useState(false);

  function limpiar() {
    setPersonaElegida(null);
    setNombre("");
    setTipoIdentificacion("CEDULA_FISICA");
    setIdentificacion("");
    setRol("COTITULAR");
    setFechaInicio(hoyComoFechaIso());
    setErrorNombre(null);
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
    setConflicto(null);
    setErrorNombre(null);
    setError(null);
  }

  async function enviar(idPersonaForzado?: number) {
    setEnviando(true);
    setError(null);

    try {
      await agregarPersonaAsociada(token, numeroPaja, {
        persona: idPersonaForzado
          ? { id_persona: idPersonaForzado }
          : personaElegida
            ? { id_persona: personaElegida.id_persona }
            : {
                nombre: nombre.trim(),
                tipo_identificacion: tipoIdentificacion,
                identificacion: identificacion.trim(),
              },
        rol,
        fecha_inicio: fechaInicio,
      });

      dialogRef.current?.close();
      onAgregada();
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
        err instanceof Error ? err.message : "No fue posible agregar la persona.",
      );
    } finally {
      setEnviando(false);
    }
  }

  async function manejarEnvio(evento: FormEvent) {
    evento.preventDefault();
    setErrorNombre(null);
    setErrorFecha(null);

    if (!personaElegida && !nombre.trim()) {
      setErrorNombre(
        "Busque una persona ya registrada o escriba el nombre completo de la nueva.",
      );
      return;
    }

    if (!personaElegida && !identificacion.trim()) {
      setErrorNombre("Escriba el número de identificación.");
      return;
    }

    if (!fechaInicio) {
      setErrorFecha("Escriba la fecha desde la que vale el vínculo.");
      return;
    }

    await enviar();
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="d06-titulo"
      className="m-auto w-[min(640px,calc(100vw-32px))] rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-background p-6 text-foreground shadow-[var(--shadow-lg)] backdrop:bg-[rgb(15_23_42_/_45%)]"
    >
      <form onSubmit={manejarEnvio} className="flex flex-col gap-4">
        <h2 id="d06-titulo">Agregar persona asociada</h2>
        <p>Busque primero si la persona ya está registrada, para no duplicarla.</p>

        <BuscadorPersona
          token={token}
          id="d06-buscar-persona"
          etiqueta="Buscar por cédula o nombre (opcional)"
          onElegir={elegirPersonaExistente}
        />

        {personaElegida ? (
          <p className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]">
            Persona elegida: <strong>{personaElegida.nombre}</strong> ·{" "}
            {personaElegida.identificacion ?? "—"}.{" "}
            <button
              type="button"
              className="underline"
              onClick={() => setPersonaElegida(null)}
            >
              Buscar otra
            </button>
          </p>
        ) : (
          <div className="flex flex-col gap-3">
            <p className="font-semibold">¿No aparece? Registre una persona nueva:</p>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="d06-nombre">Nombre completo (obligatorio)</label>
                <Input
                  id="d06-nombre"
                  value={nombre}
                  hasError={Boolean(errorNombre)}
                  onChange={(e) => {
                    setNombre(e.target.value);
                    setErrorNombre(null);
                  }}
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="d06-tipo-identificacion">
                  Tipo de identificación (obligatorio)
                </label>
                <Select
                  id="d06-tipo-identificacion"
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
                <label htmlFor="d06-identificacion">Número (obligatorio)</label>
                <Input
                  id="d06-identificacion"
                  value={identificacion}
                  placeholder="1-0000-0000"
                  hasError={Boolean(errorNombre)}
                  onChange={(e) => {
                    setIdentificacion(e.target.value);
                    setErrorNombre(null);
                  }}
                />
                <p className="text-sm text-[var(--color-text-muted)]">
                  {AYUDA_FORMATOS_IDENTIFICACION}
                </p>
              </div>
            </div>
            {errorNombre ? (
              <p className="text-sm text-[var(--color-danger)]">⚠ {errorNombre}</p>
            ) : null}
          </div>
        )}

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="d06-rol">Rol (obligatorio)</label>
            <Select
              id="d06-rol"
              value={rol}
              onChange={(e) => setRol(e.target.value as RolAsociado)}
            >
              <option value="COTITULAR">Cotitular</option>
              <option value="APODERADA">Persona apoderada</option>
            </Select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="d06-desde">Desde (obligatorio)</label>
            <FechaInput
              id="d06-desde"
              valorIso={fechaInicio}
              hasError={Boolean(errorFecha)}
              onChangeIso={(iso) => {
                setFechaInicio(iso);
                setErrorFecha(null);
              }}
            />
            {errorFecha ? (
              <p className="text-sm text-[var(--color-danger)]">⚠ {errorFecha}</p>
            ) : null}
          </div>
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
            Agregar al expediente
          </Button>
        </div>
      </form>
    </dialog>
  );
});
