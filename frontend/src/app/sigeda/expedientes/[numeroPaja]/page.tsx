"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { FechaInput } from "@/components/forms/fecha-input";
import {
  anularDocumento,
  darDeBajaAbonado,
  descargarVersion,
  editarDatosDocumento,
  listarTiposDocumento,
  obtenerExpediente,
  reactivarAbonado,
} from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import { hoyComoFechaIso } from "@/features/sigeda/validacion-archivo";
import type {
  Completitud,
  DocumentoExpediente,
  Expediente,
  TipoDocumentoCatalogo,
} from "@/features/sigeda/types";

function formatearFecha(fechaIso: string): string {
  // `fecha_anulacion` llega con hora y huso (marca de tiempo del
  // servidor); las demás fechas de este expediente son solo yyyy-mm-dd.
  // Los primeros 10 caracteres cubren ambos casos.
  const [anio, mes, dia] = fechaIso.slice(0, 10).split("-");
  return `${dia}/${mes}/${anio}`;
}

function textoFaltantesBanner(faltantes: string[]): string {
  return faltantes.length === 1
    ? "falta 1 documento obligatorio"
    : `faltan ${faltantes.length} documentos obligatorios`;
}

function EstadoBadge({ estado }: { readonly estado: "ACTIVO" | "DE_BAJA" }) {
  if (estado === "DE_BAJA") {
    return (
      <span className="inline-flex items-center rounded-full border-2 border-[var(--color-border-strong)] px-3 py-0.5 text-sm font-semibold">
        De baja
      </span>
    );
  }

  return (
    <span className="inline-flex items-center rounded-full border border-[var(--color-border)] px-3 py-0.5 text-sm">
      Activo
    </span>
  );
}

function CompletitudBadge({ completitud }: { readonly completitud: Completitud }) {
  if (completitud.completo) {
    return (
      <span className="inline-flex items-center rounded-full border border-[var(--color-success)] bg-[var(--color-success-soft)] px-3 py-0.5 text-sm text-[var(--color-success)]">
        ✓ Completo
      </span>
    );
  }

  return (
    <span className="inline-flex items-center rounded-full border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-3 py-0.5 text-sm font-semibold text-[var(--color-danger)]">
      Incompleto · faltan {completitud.faltantes.length}
    </span>
  );
}

export default function ExpedientePage() {
  const { numeroPaja } = useParams<{ numeroPaja: string }>();
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [expediente, setExpediente] = useState<Expediente | null>(null);
  const [tipos, setTipos] = useState<TipoDocumentoCatalogo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [mensajeAccion, setMensajeAccion] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const [actualizando, setActualizando] = useState(false);
  const primeraCargaHecha = useRef(false);
  const [urlVisor, setUrlVisor] = useState<string | null>(null);
  const [nombreVisor, setNombreVisor] = useState<string | null>(null);

  // Filtros en vivo (RF-11), mismo patrón que el select de sector en
  // PAN-03: cada cambio dispara de nuevo la consulta, sin botón aparte.
  const [filtroTipo, setFiltroTipo] = useState("");
  const [filtroNombreInput, setFiltroNombreInput] = useState("");
  const [filtroNombre, setFiltroNombre] = useState("");
  const [filtroFechaDesde, setFiltroFechaDesde] = useState("");
  const [filtroFechaHasta, setFiltroFechaHasta] = useState("");
  const [mostrarAnulados, setMostrarAnulados] = useState(false);

  // El nombre identificador se escribe letra a letra: se espera un
  // respiro antes de volver a consultar para no mandar una petición por
  // cada tecla.
  useEffect(() => {
    const identificador = window.setTimeout(() => {
      setFiltroNombre(filtroNombreInput);
    }, 400);

    return () => window.clearTimeout(identificador);
  }, [filtroNombreInput]);

  const cargar = useCallback(async () => {
    if (!sesion) return;

    if (primeraCargaHecha.current) {
      setActualizando(true);
    } else {
      setCargando(true);
    }

    setError(null);

    try {
      const datos = await obtenerExpediente(sesion.token, numeroPaja, {
        id_tipo_documento: filtroTipo ? Number(filtroTipo) : undefined,
        nombre_identificador: filtroNombre || undefined,
        fecha_desde: filtroFechaDesde || undefined,
        fecha_hasta: filtroFechaHasta || undefined,
        mostrar_anulados: mostrarAnulados,
      });
      setExpediente(datos);
      primeraCargaHecha.current = true;
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible cargar el expediente.",
      );
    } finally {
      setCargando(false);
      setActualizando(false);
    }
  }, [
    sesion,
    numeroPaja,
    filtroTipo,
    filtroNombre,
    filtroFechaDesde,
    filtroFechaHasta,
    mostrarAnulados,
  ]);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    cargar();
  }, [cargandoSesion, sesion, router, cargar]);

  useEffect(() => {
    if (!sesion) return;

    listarTiposDocumento(sesion.token)
      .then(setTipos)
      .catch(() => setTipos([]));
  }, [sesion]);

  async function verDocumento(idDocumento: number, numeroVersion: number, nombre: string) {
    if (!sesion) return;

    try {
      const blob = await descargarVersion(sesion.token, idDocumento, numeroVersion);
      setUrlVisor(URL.createObjectURL(blob));
      setNombreVisor(nombre);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible abrir el documento.",
      );
    }
  }

  // --- D-01 Anular documento ---------------------------------------
  const dialogAnularRef = useRef<HTMLDialogElement>(null);
  const [documentoAnular, setDocumentoAnular] = useState<DocumentoExpediente | null>(
    null,
  );
  const [motivoAnular, setMotivoAnular] = useState("");
  const [errorAnular, setErrorAnular] = useState<string | null>(null);
  const [enviandoAnular, setEnviandoAnular] = useState(false);

  function abrirAnular(documento: DocumentoExpediente) {
    setMensajeAccion(null);
    setDocumentoAnular(documento);
    setMotivoAnular("");
    setErrorAnular(null);
    dialogAnularRef.current?.showModal();
  }

  async function confirmarAnular(evento: FormEvent) {
    evento.preventDefault();
    if (!sesion || !documentoAnular) return;

    if (!motivoAnular.trim()) {
      setErrorAnular("Escriba el motivo de la anulación.");
      return;
    }

    setEnviandoAnular(true);
    setErrorAnular(null);

    try {
      await anularDocumento(sesion.token, documentoAnular.id_documento, motivoAnular.trim());
      dialogAnularRef.current?.close();
      setMensajeAccion("Documento anulado.");
      await cargar();
    } catch (err) {
      setErrorAnular(
        err instanceof Error ? err.message : "No fue posible anular el documento.",
      );
    } finally {
      setEnviandoAnular(false);
    }
  }

  // --- D-02 Editar datos del documento -------------------------------
  const dialogEditarRef = useRef<HTMLDialogElement>(null);
  const [documentoEditar, setDocumentoEditar] = useState<DocumentoExpediente | null>(
    null,
  );
  const [tipoEditar, setTipoEditar] = useState<number | "">("");
  const [nombreEditar, setNombreEditar] = useState("");
  const [errorEditarTipo, setErrorEditarTipo] = useState<string | null>(null);
  const [errorEditar, setErrorEditar] = useState<string | null>(null);
  const [enviandoEditar, setEnviandoEditar] = useState(false);

  function abrirEditar(documento: DocumentoExpediente) {
    setMensajeAccion(null);
    setDocumentoEditar(documento);
    const tipoActual = tipos.find((t) => t.nombre === documento.tipo_documento);
    setTipoEditar(tipoActual?.id_tipo_documento ?? "");
    setNombreEditar(documento.nombre_identificador ?? "");
    setErrorEditarTipo(null);
    setErrorEditar(null);
    dialogEditarRef.current?.showModal();
  }

  async function confirmarEditar(evento: FormEvent) {
    evento.preventDefault();
    if (!sesion || !documentoEditar) return;

    if (!tipoEditar) {
      setErrorEditarTipo("Elija el tipo de documento.");
      return;
    }

    setEnviandoEditar(true);
    setErrorEditar(null);
    setErrorEditarTipo(null);

    try {
      await editarDatosDocumento(sesion.token, documentoEditar.id_documento, {
        id_tipo_documento: Number(tipoEditar),
        nombre_identificador: nombreEditar.trim() || null,
      });
      dialogEditarRef.current?.close();
      setMensajeAccion("Datos del documento guardados.");
      await cargar();
    } catch (err) {
      setErrorEditar(
        err instanceof Error ? err.message : "No fue posible guardar los datos.",
      );
    } finally {
      setEnviandoEditar(false);
    }
  }

  // --- D-03 Dar de baja / reactivar el abonado -----------------------
  const dialogBajaRef = useRef<HTMLDialogElement>(null);
  const [fechaBaja, setFechaBaja] = useState("");
  const [errorBaja, setErrorBaja] = useState<string | null>(null);
  const [enviandoBaja, setEnviandoBaja] = useState(false);

  function abrirBaja() {
    setMensajeAccion(null);
    setFechaBaja(hoyComoFechaIso());
    setErrorBaja(null);
    dialogBajaRef.current?.showModal();
  }

  async function confirmarBaja(evento: FormEvent) {
    evento.preventDefault();
    if (!sesion || !expediente) return;

    const esActivo = expediente.abonado.estado === "ACTIVO";

    if (esActivo && !fechaBaja) {
      setErrorBaja("Escriba la fecha de la baja.");
      return;
    }

    setEnviandoBaja(true);
    setErrorBaja(null);

    try {
      if (esActivo) {
        await darDeBajaAbonado(sesion.token, numeroPaja, fechaBaja);
        setMensajeAccion("Abonado dado de baja.");
      } else {
        await reactivarAbonado(sesion.token, numeroPaja);
        setMensajeAccion("Abonado reactivado.");
      }

      dialogBajaRef.current?.close();
      await cargar();
    } catch (err) {
      setErrorBaja(
        err instanceof Error ? err.message : "No fue posible completar la acción.",
      );
    } finally {
      setEnviandoBaja(false);
    }
  }

  if (cargandoSesion || cargando) {
    return <p className="p-6">Cargando…</p>;
  }

  if (error && !expediente) {
    return (
      <main className="p-6">
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {error}
        </div>
      </main>
    );
  }

  if (!expediente) return null;

  const {
    abonado,
    personas_vigentes: personasVigentes,
    documentos,
    historial_titulares: historialTitulares,
  } = expediente;

  const hayFiltrosActivos = Boolean(
    filtroTipo || filtroNombre || filtroFechaDesde || filtroFechaHasta,
  );
  const esActivo = abonado.estado === "ACTIVO";
  const notaIncrementoId = "nota-incremento-2c";

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <nav aria-label="Ruta">
        <Link href="/sigeda/buscar" className="text-[var(--color-primary)]">
          Buscar expediente
        </Link>
        {" › "}
        <span>Expediente {abonado.numero_paja}</span>
      </nav>

      <div className="flex flex-col gap-1">
        <h1>Expediente · paja {abonado.numero_paja}</h1>
        <p>
          Titular vigente:{" "}
          <strong>{abonado.titular_vigente?.nombre ?? "Sin titular"}</strong>
          {" · "}
          {abonado.sector ?? "Sin sector"}
          {" · "}
          {abonado.tipo_abonado === "PERSONA_FISICA"
            ? "Persona física"
            : abonado.tipo_abonado === "PERSONA_JURIDICA"
              ? "Persona jurídica"
              : "Pendiente"}
          {" "}
          <EstadoBadge estado={abonado.estado} />{" "}
          <CompletitudBadge completitud={abonado.completitud} />
        </p>
      </div>

      {mensajeAccion ? (
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
        >
          {mensajeAccion}
        </div>
      ) : null}

      {error ? (
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {error}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button
          onClick={() => router.push(`/sigeda/expedientes/${abonado.numero_paja}/cargar`)}
        >
          Cargar documento
        </Button>
        <Button variant="secondary" disabled aria-describedby={notaIncrementoId}>
          Modificar abonado
        </Button>
        {esActivo ? (
          <Button variant="danger" onClick={abrirBaja}>
            Dar de baja
          </Button>
        ) : (
          <Button onClick={abrirBaja}>Reactivar</Button>
        )}
        <Button variant="secondary" disabled aria-describedby={notaIncrementoId}>
          Exportar
        </Button>
      </div>
      <p id={notaIncrementoId} className="text-sm text-[var(--color-text-muted)]">
        Cambiar titular, modificar abonado, agregar o quitar personas y exportar
        estarán disponibles en un próximo incremento.
      </p>

      <div className="grid gap-6 md:grid-cols-2">
        <section
          aria-labelledby="datos-abonado-titulo"
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4"
        >
          <h2 id="datos-abonado-titulo" className="mt-0">
            Datos del abonado
          </h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            <dt className="text-[var(--color-text-muted)]">Número de paja</dt>
            <dd>{abonado.numero_paja}</dd>
            <dt className="text-[var(--color-text-muted)]">Sector</dt>
            <dd>{abonado.sector ?? "—"}</dd>
            <dt className="text-[var(--color-text-muted)]">Tipo de abonado</dt>
            <dd>
              {abonado.tipo_abonado === "PERSONA_FISICA"
                ? "Persona física"
                : abonado.tipo_abonado === "PERSONA_JURIDICA"
                  ? "Persona jurídica"
                  : "Pendiente"}
            </dd>
            <dt className="text-[var(--color-text-muted)]">Estado</dt>
            <dd>{esActivo ? "Activo" : "De baja"}</dd>
          </dl>
        </section>

        <section
          aria-labelledby="personas-titulo"
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4"
        >
          <h2 id="personas-titulo" className="mt-0">
            Personas del expediente
          </h2>
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2">Persona</th>
                <th className="py-2">Identificación</th>
                <th className="py-2">Rol</th>
                <th className="py-2">Desde</th>
              </tr>
            </thead>
            <tbody>
              {personasVigentes.map((vinculo) => (
                <tr
                  key={`${vinculo.persona.id_persona}-${vinculo.fecha_inicio}`}
                  className="border-b border-[var(--color-border-soft)]"
                >
                  <td className="py-2">
                    {vinculo.rol === "TITULAR" ? (
                      <strong>{vinculo.persona.nombre}</strong>
                    ) : (
                      vinculo.persona.nombre
                    )}
                  </td>
                  <td className="py-2">{vinculo.persona.identificacion ?? "—"}</td>
                  <td className="py-2">
                    {vinculo.rol === "TITULAR"
                      ? "Titular"
                      : vinculo.rol === "COTITULAR"
                        ? "Cotitular"
                        : "Persona apoderada"}
                  </td>
                  <td className="py-2">{formatearFecha(vinculo.fecha_inicio)}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {historialTitulares.length > 0 ? (
            <details className="mt-3">
              <summary className="cursor-pointer select-none font-semibold">
                Historial de titulares ({historialTitulares.length} anterior
                {historialTitulares.length === 1 ? "" : "es"})
              </summary>
              <ul className="mt-2 flex flex-col gap-1 text-sm text-[var(--color-text-muted)]">
                {historialTitulares.map((titular, indice) => (
                  <li key={`${titular.persona.nombre}-${titular.fecha_inicio}-${indice}`}>
                    {titular.persona.nombre} · {titular.persona.identificacion ?? "—"} ·
                    titular del {formatearFecha(titular.fecha_inicio)} al{" "}
                    {formatearFecha(titular.fecha_fin)}
                  </li>
                ))}
              </ul>
            </details>
          ) : null}

          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="secondary" disabled aria-describedby={notaIncrementoId}>
              Agregar o quitar personas
            </Button>
            <Button variant="secondary" disabled aria-describedby={notaIncrementoId}>
              Cambiar titular…
            </Button>
          </div>
        </section>
      </div>

      <section aria-labelledby="documentos-titulo">
        <h2 id="documentos-titulo">
          Documentos ({documentos.length}) · ordenados por prioridad del tipo
        </h2>

        <div className="mb-4 grid grid-cols-1 items-end gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="filtro-tipo">Tipo</label>
            <Select
              id="filtro-tipo"
              value={filtroTipo}
              onChange={(e) => setFiltroTipo(e.target.value)}
            >
              <option value="">Todos</option>
              {tipos.map((tipo) => (
                <option key={tipo.id_tipo_documento} value={tipo.id_tipo_documento}>
                  {tipo.nombre}
                </option>
              ))}
            </Select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="filtro-nombre">Nombre identificador</label>
            <Input
              id="filtro-nombre"
              value={filtroNombreInput}
              onChange={(e) => setFiltroNombreInput(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="filtro-desde">Fecha del documento desde</label>
            <FechaInput
              id="filtro-desde"
              valorIso={filtroFechaDesde}
              onChangeIso={setFiltroFechaDesde}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="filtro-hasta">Fecha del documento hasta</label>
            <FechaInput
              id="filtro-hasta"
              valorIso={filtroFechaHasta}
              onChangeIso={setFiltroFechaHasta}
            />
          </div>

          <label className="flex items-center gap-2 pb-2.5">
            <input
              type="checkbox"
              checked={mostrarAnulados}
              onChange={(e) => setMostrarAnulados(e.target.checked)}
            />
            Mostrar anulados
          </label>
        </div>

        {actualizando ? (
          <p role="status" className="sr-only">
            Actualizando documentos…
          </p>
        ) : null}

        {documentos.length === 0 && !hayFiltrosActivos ? (
          <div
            role="status"
            className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-muted)] px-4 py-3"
          >
            Este expediente todavía no tiene documentos digitalizados. Mientras
            tanto se consulta en papel.{" "}
            <Link
              href={`/sigeda/expedientes/${abonado.numero_paja}/cargar`}
              className="text-[var(--color-primary)] underline"
            >
              Cargar el primer documento
            </Link>
          </div>
        ) : documentos.length === 0 && hayFiltrosActivos ? (
          <div
            role="status"
            className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]"
          >
            No hay documentos que cumplan estos filtros. Revise el tipo, el
            nombre identificador o las fechas.
          </div>
        ) : abonado.completitud.completo ? (
          <div
            role="status"
            className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
          >
            <p className="font-semibold">Expediente completo.</p>
            <p>Tiene todos los documentos obligatorios.</p>
          </div>
        ) : (
          <div
            role="status"
            className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]"
          >
            <p className="font-semibold">
              Expediente incompleto: {textoFaltantesBanner(abonado.completitud.faltantes)}.
            </p>
            <ul className="mt-1 list-disc pl-5">
              {abonado.completitud.faltantes.map((faltante) => (
                <li key={faltante}>{faltante}</li>
              ))}
            </ul>
          </div>
        )}

        {documentos.length > 0 ? (
          <table className="mt-4 w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2">Prior.</th>
                <th className="py-2">Tipo</th>
                <th className="py-2">Nombre identificador</th>
                <th className="py-2">Aportado por</th>
                <th className="py-2">Fecha del documento</th>
                <th className="py-2">Versión</th>
                <th className="py-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {documentos.map((documento) => {
                const anulado = documento.estado === "ANULADO";

                return (
                  <tr
                    key={documento.id_documento}
                    className={[
                      "border-b border-[var(--color-border-soft)]",
                      anulado ? "text-[var(--color-text-muted)]" : "",
                    ].join(" ")}
                  >
                    <td className="py-2">{documento.prioridad}</td>
                    <td className="py-2 font-semibold">
                      {documento.tipo_documento}
                      {anulado ? (
                        <>
                          {" "}
                          <span className="inline-flex items-center rounded-full border-2 border-[var(--color-border-strong)] px-2 py-0.5 text-xs font-semibold">
                            Anulado
                          </span>
                          <div className="text-sm font-normal text-[var(--color-text-muted)]">
                            Motivo: {documento.motivo_anulacion}
                            {documento.fecha_anulacion
                              ? ` · ${formatearFecha(documento.fecha_anulacion)}`
                              : ""}
                          </div>
                        </>
                      ) : null}
                    </td>
                    <td className="py-2">{documento.nombre_identificador ?? "—"}</td>
                    <td className="py-2">
                      {documento.persona ?? "—"}
                      {documento.aportante_titular_anterior ? (
                        <div>
                          <span className="inline-flex items-center rounded-full border border-dashed border-[var(--color-border-strong)] px-2 py-0.5 text-xs text-[var(--color-text-muted)]">
                            titular anterior
                          </span>
                        </div>
                      ) : null}
                    </td>
                    <td className="py-2">
                      {documento.version_vigente
                        ? formatearFecha(documento.version_vigente.fecha_documento)
                        : "—"}
                    </td>
                    <td className="py-2">
                      v{documento.version_vigente?.numero_version ?? "—"}
                      {documento.numero_versiones > 1 ? (
                        <>
                          {" · "}
                          <Link
                            href={`/sigeda/expedientes/${abonado.numero_paja}/documentos/${documento.id_documento}/versiones`}
                            className="text-[var(--color-primary)]"
                          >
                            ver versiones
                          </Link>
                        </>
                      ) : null}
                    </td>
                    <td className="py-2">
                      <div className="flex flex-wrap gap-x-3 gap-y-1">
                        {documento.version_vigente ? (
                          <button
                            type="button"
                            className="text-[var(--color-primary)] underline"
                            onClick={() =>
                              verDocumento(
                                documento.id_documento,
                                documento.version_vigente!.numero_version,
                                documento.version_vigente!.nombre_original,
                              )
                            }
                          >
                            Ver
                          </button>
                        ) : null}
                        {!anulado ? (
                          <>
                            <button
                              type="button"
                              className="text-[var(--color-primary)] underline"
                              onClick={() =>
                                router.push(
                                  `/sigeda/expedientes/${abonado.numero_paja}/cargar?nuevaVersionDe=${documento.id_documento}`,
                                )
                              }
                            >
                              Nueva versión
                            </button>
                            <button
                              type="button"
                              className="text-[var(--color-primary)] underline"
                              onClick={() => abrirEditar(documento)}
                            >
                              Editar datos
                            </button>
                            <button
                              type="button"
                              className="text-[var(--color-danger)] underline"
                              onClick={() => abrirAnular(documento)}
                            >
                              Anular
                            </button>
                          </>
                        ) : null}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : null}
      </section>

      {urlVisor ? (
        <section aria-labelledby="visor-titulo">
          <h2 id="visor-titulo">Vista del documento · {nombreVisor}</h2>
          <iframe
            title={`Documento ${nombreVisor}`}
            src={urlVisor}
            className="h-[600px] w-full rounded-[var(--radius-md)] border border-[var(--color-border)]"
          />
        </section>
      ) : null}

      {/* D-01 Anular documento (RF-19) */}
      <dialog
        ref={dialogAnularRef}
        aria-labelledby="d01-titulo"
        className="m-auto w-[min(520px,calc(100vw-32px))] rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-background p-6 text-foreground shadow-[var(--shadow-lg)] backdrop:bg-[rgb(15_23_42_/_45%)]"
      >
        <form onSubmit={confirmarAnular} className="flex flex-col gap-4">
          <h2 id="d01-titulo">Anular documento</h2>
          {documentoAnular ? (
            <p>
              <strong>
                {documentoAnular.tipo_documento} · {documentoAnular.persona ?? "—"} ·{" "}
                {documentoAnular.version_vigente
                  ? formatearFecha(documentoAnular.version_vigente.fecha_documento)
                  : "—"}
              </strong>
            </p>
          ) : null}
          <p>
            El documento no se borra: deja de verse en el expediente y no cuenta
            para la completitud. Se puede ver con «Mostrar anulados».
          </p>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="motivo-anulacion">Motivo de la anulación (obligatorio)</label>
            <Textarea
              id="motivo-anulacion"
              rows={3}
              value={motivoAnular}
              hasError={Boolean(errorAnular)}
              onChange={(e) => {
                setMotivoAnular(e.target.value);
                setErrorAnular(null);
              }}
            />
            {errorAnular ? (
              <p className="text-sm text-[var(--color-danger)]">⚠ {errorAnular}</p>
            ) : null}
          </div>
          <p className="text-sm text-[var(--color-text-muted)]">
            El motivo y la fecha de hoy ({formatearFecha(hoyComoFechaIso())}) quedan
            en la bitácora.
          </p>
          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => dialogAnularRef.current?.close()}
            >
              Cancelar
            </Button>
            <Button type="submit" variant="danger" isLoading={enviandoAnular}>
              Anular documento
            </Button>
          </div>
        </form>
      </dialog>

      {/* D-02 Editar datos del documento (RF-22) */}
      <dialog
        ref={dialogEditarRef}
        aria-labelledby="d02-titulo"
        className="m-auto w-[min(520px,calc(100vw-32px))] rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-background p-6 text-foreground shadow-[var(--shadow-lg)] backdrop:bg-[rgb(15_23_42_/_45%)]"
      >
        <form onSubmit={confirmarEditar} className="flex flex-col gap-4">
          <h2 id="d02-titulo">Editar datos del documento</h2>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="tipo-editar">Tipo de documento (obligatorio)</label>
            <Select
              id="tipo-editar"
              value={tipoEditar}
              hasError={Boolean(errorEditarTipo)}
              onChange={(e) => {
                setTipoEditar(e.target.value ? Number(e.target.value) : "");
                setErrorEditarTipo(null);
              }}
            >
              <option value="">Elija el tipo…</option>
              {tipos.map((tipo) => (
                <option key={tipo.id_tipo_documento} value={tipo.id_tipo_documento}>
                  {tipo.nombre}
                </option>
              ))}
            </Select>
            {errorEditarTipo ? (
              <p className="text-sm text-[var(--color-danger)]">⚠ {errorEditarTipo}</p>
            ) : null}
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="nombre-editar">Nombre identificador (opcional)</label>
            <Input
              id="nombre-editar"
              value={nombreEditar}
              onChange={(e) => setNombreEditar(e.target.value)}
            />
          </div>
          {errorEditar ? (
            <p role="alert" className="text-sm text-[var(--color-danger)]">
              ⚠ {errorEditar}
            </p>
          ) : null}
          <p className="text-sm text-[var(--color-text-muted)]">
            El archivo, la fecha del documento y las versiones anteriores no
            cambian. El valor anterior y el nuevo quedan en la bitácora.
          </p>
          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => dialogEditarRef.current?.close()}
            >
              Cancelar
            </Button>
            <Button type="submit" isLoading={enviandoEditar}>
              Guardar
            </Button>
          </div>
        </form>
      </dialog>

      {/* D-03 Dar de baja / reactivar el abonado (RF-17) */}
      <dialog
        ref={dialogBajaRef}
        aria-labelledby="d03-titulo"
        className="m-auto w-[min(520px,calc(100vw-32px))] rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-background p-6 text-foreground shadow-[var(--shadow-lg)] backdrop:bg-[rgb(15_23_42_/_45%)]"
      >
        <form onSubmit={confirmarBaja} className="flex flex-col gap-4">
          {esActivo ? (
            <>
              <h2 id="d03-titulo">Dar de baja el abonado {abonado.numero_paja}</h2>
              <p>
                El expediente y sus documentos se conservan y se pueden
                consultar. El abonado deja de contar en el avance de
                completitud. Puede reactivarlo después.
              </p>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="fecha-baja">Fecha de la baja (obligatorio)</label>
                <FechaInput
                  id="fecha-baja"
                  valorIso={fechaBaja}
                  onChangeIso={(iso) => {
                    setFechaBaja(iso);
                    setErrorBaja(null);
                  }}
                  hasError={Boolean(errorBaja)}
                />
                {errorBaja ? (
                  <p className="text-sm text-[var(--color-danger)]">⚠ {errorBaja}</p>
                ) : null}
              </div>
            </>
          ) : (
            <>
              <h2 id="d03-titulo">Reactivar el abonado {abonado.numero_paja}</h2>
              <p>
                El abonado vuelve a contar en el avance de completitud. El
                expediente y sus documentos no cambian.
              </p>
              {errorBaja ? (
                <p role="alert" className="text-sm text-[var(--color-danger)]">
                  ⚠ {errorBaja}
                </p>
              ) : null}
            </>
          )}
          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => dialogBajaRef.current?.close()}
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              variant={esActivo ? "danger" : "primary"}
              isLoading={enviandoBaja}
            >
              {esActivo ? "Dar de baja" : "Reactivar"}
            </Button>
          </div>
        </form>
      </dialog>
    </main>
  );
}
