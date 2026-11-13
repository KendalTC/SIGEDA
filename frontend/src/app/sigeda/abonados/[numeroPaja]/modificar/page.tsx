"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { ApiError } from "@/lib/api/errors";
import {
  esPersonaExistente,
  listarSectores,
  modificarAbonado,
  obtenerExpediente,
  quitarPersonaAsociada,
  cambiarRolPersonaAsociada,
} from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import {
  DialogoAgregarPersona,
  type DialogoAgregarPersonaHandle,
} from "@/features/sigeda/dialogo-agregar-persona";
import {
  DialogoCambiarTitular,
  type DialogoCambiarTitularHandle,
} from "@/features/sigeda/dialogo-cambiar-titular";
import {
  AYUDA_FORMATOS_IDENTIFICACION,
  OPCIONES_TIPO_IDENTIFICACION,
} from "@/features/sigeda/identificacion";
import type {
  Expediente,
  PersonaExistenteConflicto,
  RolAsociado,
  SectorCatalogo,
  TipoIdentificacion,
} from "@/features/sigeda/types";

type TipoAbonado = "PERSONA_FISICA" | "PERSONA_JURIDICA";

function formatearFecha(fechaIso: string): string {
  const [anio, mes, dia] = fechaIso.slice(0, 10).split("-");
  return `${dia}/${mes}/${anio}`;
}

export default function ModificarAbonadoPage() {
  const { numeroPaja } = useParams<{ numeroPaja: string }>();
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [expediente, setExpediente] = useState<Expediente | null>(null);
  const [sectores, setSectores] = useState<SectorCatalogo[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [idSector, setIdSector] = useState("");
  // RF-04/RF-21 (ficha PAN-06 "importado"): un abonado recién importado
  // de SADA no trae tipo, así que el radio arranca sin marcar — "" es
  // "todavía sin elegir", nunca un tercer tipo de abonado real.
  const [tipoAbonado, setTipoAbonado] = useState<TipoAbonado | "">(
    "PERSONA_FISICA",
  );
  // RF-04 (ficha PAN-06 "importado"): completa la identificación del
  // titular cuando todavía no la tiene (abonado creado por importación
  // de SADA). Ambos campos son opcionales, pero van juntos o ninguno.
  const [tipoIdentificacionTitular, setTipoIdentificacionTitular] = useState<
    TipoIdentificacion | ""
  >("");
  const [identificacionTitular, setIdentificacionTitular] = useState("");

  const [guardando, setGuardando] = useState(false);
  const [errorSector, setErrorSector] = useState<string | null>(null);
  const [errorIdentificacionTitular, setErrorIdentificacionTitular] =
    useState<string | null>(null);
  const [conflictoIdentificacionTitular, setConflictoIdentificacionTitular] =
    useState<PersonaExistenteConflicto | null>(null);
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [erroresPersona, setErroresPersona] = useState<Record<number, string>>(
    {},
  );

  const dialogoCambiarTitularRef = useRef<DialogoCambiarTitularHandle>(null);
  const dialogoAgregarPersonaRef = useRef<DialogoAgregarPersonaHandle>(null);

  const cargar = useCallback(async () => {
    if (!sesion) return;

    try {
      const [datosExpediente, catalogoSectores] = await Promise.all([
        obtenerExpediente(sesion.token, numeroPaja),
        listarSectores(sesion.token),
      ]);

      setExpediente(datosExpediente);
      setSectores(catalogoSectores);

      const sectorActual = catalogoSectores.find(
        (s) => s.nombre === datosExpediente.abonado.sector,
      );
      setIdSector(sectorActual ? String(sectorActual.id_sector) : "");

      const { tipo_abonado: tipoAbonadoActual } = datosExpediente.abonado;
      setTipoAbonado(
        tipoAbonadoActual === "PENDIENTE"
          ? ""
          : tipoAbonadoActual === "PERSONA_JURIDICA"
            ? "PERSONA_JURIDICA"
            : "PERSONA_FISICA",
      );
      setTipoIdentificacionTitular("");
      setIdentificacionTitular("");
    } catch (err) {
      setErrorCarga(
        err instanceof Error ? err.message : "No fue posible cargar el abonado.",
      );
    } finally {
      setCargando(false);
    }
  }, [sesion, numeroPaja]);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    cargar();
  }, [cargandoSesion, sesion, router, cargar]);

  async function guardar() {
    if (!sesion || !expediente) return;

    // Condición exacta que usa el backend para decidir si procesa
    // `tipo_identificacion_titular`/`identificacion_titular` (más
    // precisa que `es_importado_pendiente`, que además exige que el
    // tipo de abonado siga en PENDIENTE).
    const titularSinIdentificacion =
      expediente.abonado.titular_vigente !== null &&
      expediente.abonado.titular_vigente.identificacion === null;

    setErrorSector(null);
    setErrorIdentificacionTitular(null);
    setConflictoIdentificacionTitular(null);
    setErrorGeneral(null);
    setMensaje(null);

    if (tipoAbonado === "") {
      setErrorGeneral("Elija el tipo de abonado antes de guardar.");
      return;
    }

    const tipoIdVacio = tipoIdentificacionTitular === "";
    const numeroIdVacio = identificacionTitular.trim() === "";

    if (titularSinIdentificacion && tipoIdVacio !== numeroIdVacio) {
      setErrorIdentificacionTitular(
        "El tipo y el número de identificación del titular se deben completar juntos.",
      );
      return;
    }

    setGuardando(true);

    try {
      await modificarAbonado(sesion.token, numeroPaja, {
        id_sector: Number(idSector),
        tipo_abonado: tipoAbonado,
        ...(titularSinIdentificacion && !tipoIdVacio && !numeroIdVacio
          ? {
              tipo_identificacion_titular:
                tipoIdentificacionTitular as TipoIdentificacion,
              identificacion_titular: identificacionTitular.trim(),
            }
          : {}),
      });

      setMensaje("Cambios guardados.");
      await cargar();
    } catch (err) {
      if (
        err instanceof ApiError &&
        err.status === 409 &&
        esPersonaExistente(err.payload)
      ) {
        setConflictoIdentificacionTitular(err.payload.persona_existente);
        return;
      }

      if (err instanceof ApiError && err.status === 400) {
        setErrorSector(err.fieldErrors.id_sector?.[0] ?? null);

        // Los errores de identificación del titular vienen en "detail"
        // (sin clave de campo propia): si no hay error de sector, es la
        // explicación más probable mientras el mini-formulario esté
        // visible. Este mensaje en particular ya trae su propio "⚠ "
        // puesto por el backend (a diferencia del resto); se quita acá
        // para no duplicar el ícono, igual que ya se hace con
        // numero_paja en el alta (RF-02).
        if (!err.fieldErrors.id_sector && titularSinIdentificacion) {
          setErrorIdentificacionTitular(err.message.replace(/^⚠\s*/, ""));
        }

        setErrorGeneral(err.message);
        return;
      }

      setErrorGeneral(
        err instanceof Error ? err.message : "No fue posible guardar los cambios.",
      );
    } finally {
      setGuardando(false);
    }
  }

  async function quitarPersona(idPersona: number) {
    if (!sesion) return;

    setErroresPersona((actual) => ({ ...actual, [idPersona]: "" }));

    try {
      await quitarPersonaAsociada(sesion.token, numeroPaja, idPersona);
      setMensaje("Persona quitada del expediente.");
      await cargar();
    } catch (err) {
      setErroresPersona((actual) => ({
        ...actual,
        [idPersona]:
          err instanceof Error ? err.message : "No fue posible quitar la persona.",
      }));
    }
  }

  async function cambiarRol(idPersona: number, rol: RolAsociado) {
    if (!sesion) return;

    try {
      await cambiarRolPersonaAsociada(sesion.token, numeroPaja, idPersona, rol);
      setMensaje("Rol actualizado.");
      await cargar();
    } catch (err) {
      setErroresPersona((actual) => ({
        ...actual,
        [idPersona]:
          err instanceof Error ? err.message : "No fue posible cambiar el rol.",
      }));
    }
  }

  if (cargandoSesion || cargando) {
    return <p className="p-6">Cargando…</p>;
  }

  if (errorCarga || !expediente) {
    return (
      <main className="p-6">
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {errorCarga ?? "No fue posible cargar el abonado."}
        </div>
      </main>
    );
  }

  const { abonado, personas_vigentes: personasVigentes, historial_titulares: historialTitulares } =
    expediente;
  const vinculoTitular = personasVigentes.find((v) => v.rol === "TITULAR");
  const personasAsociadas = personasVigentes.filter((v) => v.rol !== "TITULAR");
  const esActivo = abonado.estado === "ACTIVO";
  // Misma condición que usa `ModificarAbonadoView` en el backend para
  // decidir si completa la identificación del titular: no depende de
  // `es_importado_pendiente` (que exige además tipo_abonado PENDIENTE),
  // para que el mini-formulario siga disponible aunque ya se haya
  // elegido el tipo de abonado en un guardado anterior.
  const titularSinIdentificacion =
    abonado.titular_vigente !== null && abonado.titular_vigente.identificacion === null;

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <nav aria-label="Ruta">
        <Link
          href={`/sigeda/expedientes/${numeroPaja}`}
          className="text-[var(--color-primary)]"
        >
          Expediente {numeroPaja}
        </Link>
        {" › "}
        <span>Modificar</span>
      </nav>

      <h1>Modificar abonado y personas</h1>

      {abonado.es_importado_pendiente ? (
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]"
        >
          <p className="font-semibold">
            Abonado importado de SADA el{" "}
            {formatearFecha(abonado.fecha_importacion ?? vinculoTitular?.fecha_inicio ?? "")}
            : faltan el tipo de abonado, el sector y la identificación del
            titular.
          </p>
          <p>
            Mientras el tipo esté pendiente, el panel de completitud lo
            muestra aparte. Complete los datos y guarde.
          </p>
        </div>
      ) : null}

      {mensaje ? (
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
        >
          {mensaje}
        </div>
      ) : null}

      {errorGeneral ? (
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {errorGeneral}
        </div>
      ) : null}

      <fieldset className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4">
        <legend className="px-1 text-lg font-semibold">Datos del abonado</legend>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="numero-paja">Número de paja (obligatorio)</label>
            <Input id="numero-paja" value={abonado.numero_paja} disabled />
            <p className="text-sm text-[var(--color-text-muted)]">
              El número de paja no se puede cambiar.
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
            <p className="text-sm text-[var(--color-text-muted)]">
              Estado: <strong>{esActivo ? "Activo" : "De baja"}</strong>. Para dar
              de baja o reactivar use el botón del expediente.
            </p>
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
            {tipoAbonado === "" ? (
              <p className="text-sm font-semibold text-[var(--color-danger)]">
                ⚠ Tipo pendiente: elija uno para que se pueda calcular la
                completitud.
              </p>
            ) : (
              <p className="text-sm text-[var(--color-text-muted)]">
                Define qué documentos son obligatorios.
              </p>
            )}
          </div>
        </div>
      </fieldset>

      <section
        aria-labelledby="titular-vigente-titulo"
        className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="titular-vigente-titulo" className="mt-0">
            Titular vigente
          </h2>
          <Button
            type="button"
            variant="secondary"
            onClick={() => dialogoCambiarTitularRef.current?.abrir()}
          >
            Cambiar titular…
          </Button>
        </div>

        <p>
          <strong>{abonado.titular_vigente?.nombre ?? "Sin titular"}</strong>
          {abonado.titular_vigente?.identificacion
            ? ` · ${abonado.titular_vigente.identificacion}`
            : titularSinIdentificacion
              ? " · sin identificación"
              : ""}
          {vinculoTitular
            ? ` · titular desde ${formatearFecha(vinculoTitular.fecha_inicio)}`
            : ""}
        </p>

        {titularSinIdentificacion ? (
          <div className="mt-3 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-muted)] p-3">
            <p className="font-medium">Completar identificación del titular</p>

            {conflictoIdentificacionTitular ? (
              <div className="mt-2 rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]">
                <p className="font-semibold">
                  Ya existe una persona con esa identificación:{" "}
                  {conflictoIdentificacionTitular.nombre}
                  {conflictoIdentificacionTitular.numero_paja_titular
                    ? `, titular de la paja ${conflictoIdentificacionTitular.numero_paja_titular}`
                    : ""}
                  .
                </p>
                <p>Revise el número.</p>
              </div>
            ) : null}

            <div className="mt-2 grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="tipo-identificacion-titular">
                  Tipo de identificación (opcional)
                </label>
                <Select
                  id="tipo-identificacion-titular"
                  value={tipoIdentificacionTitular}
                  hasError={Boolean(errorIdentificacionTitular)}
                  onChange={(e) => {
                    setTipoIdentificacionTitular(
                      e.target.value as TipoIdentificacion | "",
                    );
                    setErrorIdentificacionTitular(null);
                    setConflictoIdentificacionTitular(null);
                  }}
                >
                  <option value="">Sin identificación todavía</option>
                  {OPCIONES_TIPO_IDENTIFICACION.map((opcion) => (
                    <option key={opcion.valor} value={opcion.valor}>
                      {opcion.etiqueta}
                    </option>
                  ))}
                </Select>
              </div>

              <div className="flex flex-col gap-1.5">
                <label htmlFor="identificacion-titular">
                  Número de identificación (opcional)
                </label>
                <Input
                  id="identificacion-titular"
                  value={identificacionTitular}
                  placeholder="1-0000-0000"
                  hasError={Boolean(errorIdentificacionTitular)}
                  onChange={(e) => {
                    setIdentificacionTitular(e.target.value);
                    setErrorIdentificacionTitular(null);
                    setConflictoIdentificacionTitular(null);
                  }}
                />
              </div>
            </div>

            {errorIdentificacionTitular ? (
              <p className="mt-1 text-sm text-[var(--color-danger)]">
                ⚠ {errorIdentificacionTitular}
              </p>
            ) : (
              <p className="mt-1 text-sm text-[var(--color-text-muted)]">
                {AYUDA_FORMATOS_IDENTIFICACION}
              </p>
            )}
          </div>
        ) : null}

        {historialTitulares.length > 0 ? (
          <details className="mt-3">
            <summary className="cursor-pointer select-none font-semibold">
              Historial de titulares ({historialTitulares.length} anterior
              {historialTitulares.length === 1 ? "" : "es"})
            </summary>
            <table className="mt-2 w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="py-1.5">Titular</th>
                  <th className="py-1.5">Identificación</th>
                  <th className="py-1.5">Desde</th>
                  <th className="py-1.5">Hasta</th>
                </tr>
              </thead>
              <tbody>
                {historialTitulares.map((titular, indice) => (
                  <tr
                    key={`${titular.persona.nombre}-${titular.fecha_inicio}-${indice}`}
                    className="border-b border-[var(--color-border-soft)]"
                  >
                    <td className="py-1.5">{titular.persona.nombre}</td>
                    <td className="py-1.5">{titular.persona.identificacion ?? "—"}</td>
                    <td className="py-1.5">{formatearFecha(titular.fecha_inicio)}</td>
                    <td className="py-1.5">{formatearFecha(titular.fecha_fin)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        ) : null}
      </section>

      <section
        aria-labelledby="personas-asociadas-titulo"
        className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4"
      >
        <h2 id="personas-asociadas-titulo" className="mt-0">
          Personas asociadas (cotitulares y persona apoderada)
        </h2>

        {personasAsociadas.length === 0 ? (
          <p>Aún no hay personas asociadas.</p>
        ) : (
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2">Persona</th>
                <th className="py-2">Identificación</th>
                <th className="py-2">Rol</th>
                <th className="py-2">Desde</th>
                <th className="py-2">Hasta</th>
                <th className="py-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {personasAsociadas.map((vinculo) => (
                <tr
                  key={vinculo.persona.id_persona}
                  className="border-b border-[var(--color-border-soft)]"
                >
                  <td className="py-2">{vinculo.persona.nombre}</td>
                  <td className="py-2">{vinculo.persona.identificacion ?? "—"}</td>
                  <td className="py-2">
                    <label className="sr-only" htmlFor={`rol-${vinculo.persona.id_persona}`}>
                      Rol de {vinculo.persona.nombre}
                    </label>
                    <Select
                      id={`rol-${vinculo.persona.id_persona}`}
                      value={vinculo.rol}
                      onChange={(e) =>
                        cambiarRol(
                          vinculo.persona.id_persona,
                          e.target.value as RolAsociado,
                        )
                      }
                    >
                      <option value="COTITULAR">Cotitular</option>
                      <option value="APODERADA">Persona apoderada</option>
                    </Select>
                  </td>
                  <td className="py-2">{formatearFecha(vinculo.fecha_inicio)}</td>
                  <td className="py-2">—</td>
                  <td className="py-2">
                    <button
                      type="button"
                      className="text-[var(--color-danger)] underline"
                      onClick={() => quitarPersona(vinculo.persona.id_persona)}
                    >
                      Quitar del expediente
                    </button>
                    {erroresPersona[vinculo.persona.id_persona] ? (
                      <p className="text-sm text-[var(--color-danger)]">
                        ⚠ {erroresPersona[vinculo.persona.id_persona]}
                      </p>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        <div className="mt-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => dialogoAgregarPersonaRef.current?.abrir()}
          >
            + Agregar persona
          </Button>
        </div>
        <p className="mt-2 text-sm text-[var(--color-text-muted)]">
          Quitar una persona cierra su vínculo con la fecha de hoy; sus
          documentos se quedan en el expediente.
        </p>
      </section>

      <div className="flex gap-3">
        <Button
          type="button"
          variant="secondary"
          onClick={() => router.push(`/sigeda/expedientes/${numeroPaja}`)}
        >
          Cancelar
        </Button>
        <Button onClick={guardar} isLoading={guardando} loadingText="Guardando…">
          Guardar
        </Button>
      </div>

      <DialogoCambiarTitular
        ref={dialogoCambiarTitularRef}
        token={sesion!.token}
        numeroPaja={numeroPaja}
        titularActualNombre={abonado.titular_vigente?.nombre ?? "Sin titular"}
        onCambiado={() => {
          setMensaje("Titular cambiado.");
          cargar();
        }}
      />

      <DialogoAgregarPersona
        ref={dialogoAgregarPersonaRef}
        token={sesion!.token}
        numeroPaja={numeroPaja}
        onAgregada={() => {
          setMensaje("Persona agregada al expediente.");
          cargar();
        }}
      />
    </main>
  );
}
