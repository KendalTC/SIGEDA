"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ApiError } from "@/lib/api/errors";
import { esPersonaExistente, listarSectores, registrarAbonado } from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import { BuscadorPersona } from "@/features/sigeda/buscador-persona";
import {
  AYUDA_FORMATOS_IDENTIFICACION,
  OPCIONES_TIPO_IDENTIFICACION,
} from "@/features/sigeda/identificacion";
import type {
  PersonaBusqueda,
  PersonaExistenteConflicto,
  SectorCatalogo,
  TipoIdentificacion,
} from "@/features/sigeda/types";

type TipoAbonado = "PERSONA_FISICA" | "PERSONA_JURIDICA";

const ESTADO_INICIAL = {
  numeroPaja: "",
  idSector: "",
  tipoAbonado: "PERSONA_FISICA" as TipoAbonado,
  nombreTitular: "",
  tipoIdentificacionTitular: "CEDULA_FISICA" as TipoIdentificacion,
  identificacionTitular: "",
};

export default function NuevoAbonadoPage() {
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [sectores, setSectores] = useState<SectorCatalogo[]>([]);

  const [numeroPaja, setNumeroPaja] = useState(ESTADO_INICIAL.numeroPaja);
  const [idSector, setIdSector] = useState(ESTADO_INICIAL.idSector);
  const [tipoAbonado, setTipoAbonado] = useState<TipoAbonado>(
    ESTADO_INICIAL.tipoAbonado,
  );

  const [personaElegida, setPersonaElegida] = useState<PersonaBusqueda | null>(
    null,
  );
  const [mostrarBuscadorTitular, setMostrarBuscadorTitular] = useState(false);
  const [nombreTitular, setNombreTitular] = useState(ESTADO_INICIAL.nombreTitular);
  const [tipoIdentificacionTitular, setTipoIdentificacionTitular] =
    useState<TipoIdentificacion>(ESTADO_INICIAL.tipoIdentificacionTitular);
  const [identificacionTitular, setIdentificacionTitular] = useState(
    ESTADO_INICIAL.identificacionTitular,
  );

  const [estado, setEstado] = useState<"formulario" | "guardando" | "exito">(
    "formulario",
  );
  const [numeroPajaRegistrado, setNumeroPajaRegistrado] = useState("");

  const [errorPaja, setErrorPaja] = useState<string | null>(null);
  const [errorSector, setErrorSector] = useState<string | null>(null);
  const [errorTitular, setErrorTitular] = useState<string | null>(null);
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [conflicto, setConflicto] = useState<PersonaExistenteConflicto | null>(
    null,
  );

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    listarSectores(sesion.token)
      .then(setSectores)
      .catch(() => setSectores([]));
  }, [cargandoSesion, sesion, router]);

  function limpiarErrores() {
    setErrorPaja(null);
    setErrorSector(null);
    setErrorTitular(null);
    setErrorGeneral(null);
    setConflicto(null);
  }

  function reiniciarFormulario() {
    setNumeroPaja(ESTADO_INICIAL.numeroPaja);
    setIdSector(ESTADO_INICIAL.idSector);
    setTipoAbonado(ESTADO_INICIAL.tipoAbonado);
    setPersonaElegida(null);
    setMostrarBuscadorTitular(false);
    setNombreTitular(ESTADO_INICIAL.nombreTitular);
    setTipoIdentificacionTitular(ESTADO_INICIAL.tipoIdentificacionTitular);
    setIdentificacionTitular(ESTADO_INICIAL.identificacionTitular);
    limpiarErrores();
    setEstado("formulario");
  }

  function elegirPersonaExistente(persona: PersonaBusqueda) {
    setPersonaElegida(persona);
    setNombreTitular(persona.nombre);
    if (persona.tipo_identificacion) {
      setTipoIdentificacionTitular(persona.tipo_identificacion as TipoIdentificacion);
    }
    setIdentificacionTitular(persona.identificacion ?? "");
    setMostrarBuscadorTitular(false);
    limpiarErrores();
  }

  async function enviar(idPersonaForzado?: number) {
    if (!sesion) return;

    setEstado("guardando");
    limpiarErrores();

    try {
      const respuesta = await registrarAbonado(sesion.token, {
        numero_paja: numeroPaja.trim(),
        id_sector: Number(idSector),
        tipo_abonado: tipoAbonado,
        titular: idPersonaForzado
          ? { id_persona: idPersonaForzado }
          : personaElegida
            ? { id_persona: personaElegida.id_persona }
            : {
                nombre: nombreTitular.trim(),
                tipo_identificacion: tipoIdentificacionTitular,
                identificacion: identificacionTitular.trim(),
              },
      });

      setNumeroPajaRegistrado(respuesta.numero_paja ?? numeroPaja.trim());
      setEstado("exito");
    } catch (err) {
      setEstado("formulario");

      if (
        err instanceof ApiError &&
        err.status === 409 &&
        esPersonaExistente(err.payload)
      ) {
        setConflicto(err.payload.persona_existente);
        return;
      }

      if (err instanceof ApiError && err.status === 400) {
        const fe = err.fieldErrors;
        // El backend ya antepone "⚠ " a los mensajes de numero_paja; se
        // quita acá para que la interfaz siga siendo la única que decide
        // cómo se ve el ícono de advertencia (igual que en el resto de
        // las pantallas, donde el texto del mensaje nunca lo trae).
        const paja = fe.numero_paja?.[0]?.replace(/^⚠\s*/, "") ?? null;
        const sector = fe.id_sector?.[0] ?? null;
        const titular =
          fe.titular?.[0] ??
          fe.identificacion?.[0] ??
          fe.nombre?.[0] ??
          fe.tipo_identificacion?.[0] ??
          null;

        setErrorPaja(paja);
        setErrorSector(sector);
        setErrorTitular(titular);

        const cantidad = [paja, sector, titular].filter(Boolean).length;

        if (cantidad === 0) {
          setErrorGeneral(err.message);
        }

        return;
      }

      setErrorGeneral(
        err instanceof Error ? err.message : "No fue posible registrar el abonado.",
      );
    }
  }

  async function manejarEnvio(evento: FormEvent) {
    evento.preventDefault();
    await enviar();
  }

  const cantidadErrores = [errorPaja, errorSector, errorTitular].filter(
    Boolean,
  ).length;

  if (cargandoSesion) {
    return <p className="p-6">Cargando…</p>;
  }

  if (estado === "exito") {
    return (
      <main className="mx-auto max-w-5xl p-8">
        <h1>Registrar abonado</h1>
        <div className="mt-4 rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]">
          <p className="font-semibold">
            Abonado {numeroPajaRegistrado} registrado con su titular vigente.
          </p>
          <p>
            Quedó en la bitácora a nombre de la cuenta {sesion?.cuenta.usuario}.
            Ahora puede cargar sus documentos.
          </p>
        </div>
        <div className="mt-6 flex flex-wrap gap-3">
          <Button
            onClick={() =>
              router.push(`/sigeda/expedientes/${numeroPajaRegistrado}/cargar`)
            }
          >
            Cargar documentos
          </Button>
          <Button
            variant="secondary"
            onClick={() => router.push(`/sigeda/expedientes/${numeroPajaRegistrado}`)}
          >
            Ver expediente
          </Button>
          <Button variant="secondary" onClick={reiniciarFormulario}>
            Registrar otro
          </Button>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 p-8">
      <nav aria-label="Ruta">
        <Link href="/sigeda/buscar" className="text-[var(--color-primary)]">
          Buscar expediente
        </Link>
        {" › "}
        <span>Nuevo abonado</span>
      </nav>

      <h1>Registrar abonado</h1>

      {cantidadErrores > 0 ? (
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          <p className="font-semibold">
            No se pudo guardar: hay {cantidadErrores} dato
            {cantidadErrores === 1 ? "" : "s"} por corregir.
          </p>
          <p>Están marcados abajo con ⚠.</p>
        </div>
      ) : errorGeneral ? (
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          <p className="font-semibold">No se pudo guardar: {errorGeneral}</p>
        </div>
      ) : null}

      {conflicto ? (
        <div className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]">
          <p className="font-semibold">
            Ya existe una persona con la{" "}
            {tipoIdentificacionTitular === "CEDULA_FISICA"
              ? "cédula física"
              : tipoIdentificacionTitular === "CEDULA_JURIDICA"
                ? "cédula jurídica"
                : tipoIdentificacionTitular === "DIMEX"
                  ? "DIMEX"
                  : "identificación"}{" "}
            {identificacionTitular}: {conflicto.nombre}
            {conflicto.numero_paja_titular
              ? `, titular de la paja ${conflicto.numero_paja_titular}`
              : ""}
            .
          </p>
          <p>Si es la misma persona, use sus datos registrados para no duplicarla.</p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="secondary"
              isLoading={estado === "guardando"}
              onClick={() => enviar(conflicto.id_persona)}
            >
              Usar esa persona
            </Button>
            <button
              type="button"
              className="text-[var(--color-primary)] underline"
              onClick={() => setConflicto(null)}
            >
              Revisar el número
            </button>
          </div>
        </div>
      ) : null}

      <form onSubmit={manejarEnvio} className="flex flex-col gap-6" noValidate>
        <fieldset className="rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] p-6">
          <legend className="px-1 text-lg font-semibold">Datos del abonado</legend>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="numero-paja">Número de paja (obligatorio)</label>
              <Input
                id="numero-paja"
                value={numeroPaja}
                hasError={Boolean(errorPaja)}
                onChange={(e) => {
                  setNumeroPaja(e.target.value);
                  setErrorPaja(null);
                }}
              />
              {errorPaja ? (
                <p className="text-sm text-[var(--color-danger)]">⚠ {errorPaja}</p>
              ) : null}
              <p className="text-sm text-[var(--color-text-muted)]">
                Solo números; puede empezar con cero. No se repite y no se puede
                cambiar después.
              </p>
            </div>

            <div className="flex flex-col gap-1.5">
              <label htmlFor="sector">Sector (obligatorio)</label>
              <Select
                id="sector"
                value={idSector}
                hasError={Boolean(errorSector)}
                onChange={(e) => {
                  setIdSector(e.target.value);
                  setErrorSector(null);
                }}
              >
                <option value="">Elija el sector…</option>
                {sectores.map((sector) => (
                  <option key={sector.id_sector} value={sector.id_sector}>
                    {sector.nombre}
                  </option>
                ))}
              </Select>
              {errorSector ? (
                <p className="text-sm text-[var(--color-danger)]">⚠ {errorSector}</p>
              ) : null}
            </div>

            <div className="flex flex-col gap-1.5">
              <span className="font-medium">Tipo de abonado (obligatorio)</span>
              <div className="flex items-center gap-4 py-2.5">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="tipo-abonado"
                    checked={tipoAbonado === "PERSONA_FISICA"}
                    onChange={() => setTipoAbonado("PERSONA_FISICA")}
                  />
                  Persona física
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="tipo-abonado"
                    checked={tipoAbonado === "PERSONA_JURIDICA"}
                    onChange={() => setTipoAbonado("PERSONA_JURIDICA")}
                  />
                  Persona jurídica
                </label>
              </div>
              <p className="text-sm text-[var(--color-text-muted)]">
                Define qué documentos son obligatorios.
              </p>
            </div>
          </div>
        </fieldset>

        <fieldset className="rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] p-6">
          <legend className="px-1 text-lg font-semibold">Titular vigente</legend>

          <div className="flex flex-col gap-4">
            <div className="flex items-end gap-3">
              <div className="flex flex-1 flex-col gap-1.5">
                <label htmlFor="nombre-titular">
                  Nombre completo o razón social (obligatorio)
                </label>
                <Input
                  id="nombre-titular"
                  value={nombreTitular}
                  disabled={Boolean(personaElegida)}
                  hasError={Boolean(errorTitular)}
                  onChange={(e) => {
                    setNombreTitular(e.target.value);
                    setErrorTitular(null);
                  }}
                />
              </div>
              <Button
                type="button"
                variant="secondary"
                onClick={() => setMostrarBuscadorTitular((actual) => !actual)}
              >
                Buscar persona ya registrada
              </Button>
            </div>

            {personaElegida ? (
              <p className="text-sm text-[var(--color-text-muted)]">
                Datos tomados de una persona ya registrada.{" "}
                <button
                  type="button"
                  className="text-[var(--color-primary)] underline"
                  onClick={() => {
                    setPersonaElegida(null);
                    setNombreTitular(ESTADO_INICIAL.nombreTitular);
                    setIdentificacionTitular(ESTADO_INICIAL.identificacionTitular);
                  }}
                >
                  Escribir otros datos
                </button>
              </p>
            ) : null}

            {mostrarBuscadorTitular ? (
              <BuscadorPersona
                token={sesion!.token}
                id="buscador-titular"
                etiqueta="Buscar persona ya registrada"
                onElegir={elegirPersonaExistente}
              />
            ) : null}

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="tipo-identificacion-titular">
                  Tipo de identificación (obligatorio)
                </label>
                <Select
                  id="tipo-identificacion-titular"
                  value={tipoIdentificacionTitular}
                  disabled={Boolean(personaElegida)}
                  onChange={(e) => {
                    setTipoIdentificacionTitular(
                      e.target.value as TipoIdentificacion,
                    );
                    setErrorTitular(null);
                  }}
                >
                  {OPCIONES_TIPO_IDENTIFICACION.map((opcion) => (
                    <option key={opcion.valor} value={opcion.valor}>
                      {opcion.etiqueta}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="identificacion-titular">
                  Número de identificación (obligatorio)
                </label>
                <Input
                  id="identificacion-titular"
                  value={identificacionTitular}
                  disabled={Boolean(personaElegida)}
                  placeholder="1-0000-0000"
                  hasError={Boolean(errorTitular)}
                  onChange={(e) => {
                    setIdentificacionTitular(e.target.value);
                    setErrorTitular(null);
                  }}
                />
                {errorTitular ? (
                  <p className="text-sm text-[var(--color-danger)]">
                    ⚠ {errorTitular}
                  </p>
                ) : null}
                <p className="text-sm text-[var(--color-text-muted)]">
                  {AYUDA_FORMATOS_IDENTIFICACION}
                </p>
              </div>
            </div>
          </div>
        </fieldset>

        <fieldset className="rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] p-6">
          <legend className="px-1 text-lg font-semibold">
            Personas asociadas (cotitulares y persona apoderada)
          </legend>
          <p>Aún no hay personas asociadas.</p>
          <div className="mt-3">
            <Button
              type="button"
              variant="secondary"
              disabled
              aria-describedby="nota-personas-alta"
            >
              + Agregar persona
            </Button>
          </div>
          <p className="mt-2 text-sm text-[var(--color-text-muted)]">
            Quitar una persona cierra su vínculo con la fecha de hoy; sus
            documentos se quedan en el expediente.
          </p>
          <p id="nota-personas-alta" className="mt-1 text-sm text-[var(--color-text-muted)]">
            Para agregar personas asociadas, primero registre el abonado.
          </p>
        </fieldset>

        <div className="flex gap-3">
          <Button type="button" variant="secondary" onClick={() => router.push("/sigeda/buscar")}>
            Cancelar
          </Button>
          <Button type="submit" isLoading={estado === "guardando"} loadingText="Guardando…">
            Guardar
          </Button>
        </div>
      </form>
    </main>
  );
}
