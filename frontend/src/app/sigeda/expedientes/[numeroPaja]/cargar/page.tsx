"use client";

import { useRouter } from "next/navigation";
import { use, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  cargarDocumentos,
  esErrorDeCarga,
  listarTiposDocumento,
  obtenerExpediente,
} from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import type {
  CargaDocumentosExito,
  DocumentoExpediente,
  Expediente,
  TipoDocumentoCatalogo,
} from "@/features/sigeda/types";
import {
  hoyComoFechaIso,
  validarArchivoEnNavegador,
} from "@/features/sigeda/validacion-archivo";

type FilaArchivo = {
  id: string;
  archivo: File;
  tipoDocumentoId: number | "";
  personaId: number | "";
  nombreIdentificador: string;
  fechaDocumento: string;
  errorArchivo: string | null;
  erroresServidor: Record<string, string>;
};

function nuevaFila(archivo: File, personaPorDefecto: number | ""): FilaArchivo {
  return {
    id: `${archivo.name}-${archivo.size}-${Math.random().toString(36).slice(2)}`,
    archivo,
    tipoDocumentoId: "",
    personaId: personaPorDefecto,
    nombreIdentificador: "",
    fechaDocumento: hoyComoFechaIso(),
    errorArchivo: null,
    erroresServidor: {},
  };
}

export default function CargarDocumentoPage({
  params,
}: {
  params: Promise<{ numeroPaja: string }>;
}) {
  const { numeroPaja } = use(params);
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [expediente, setExpediente] = useState<Expediente | null>(null);
  const [tipos, setTipos] = useState<TipoDocumentoCatalogo[]>([]);
  const [modo, setModo] = useState<"nuevo" | "nueva_version">("nuevo");
  const [documentoSeleccionado, setDocumentoSeleccionado] =
    useState<DocumentoExpediente | null>(null);
  const [filas, setFilas] = useState<FilaArchivo[]>([]);
  const [estado, setEstado] = useState<
    "cargando_datos" | "listo" | "guardando" | "exito" | "error_lote"
  >("cargando_datos");
  const [mensajeLote, setMensajeLote] = useState<string | null>(null);
  const [resultado, setResultado] = useState<CargaDocumentosExito | null>(null);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    (async () => {
      try {
        const [datosExpediente, catalogoTipos] = await Promise.all([
          obtenerExpediente(sesion.token, numeroPaja),
          listarTiposDocumento(sesion.token),
        ]);
        setExpediente(datosExpediente);
        setTipos(catalogoTipos);
        setEstado("listo");
      } catch {
        setMensajeLote("No fue posible cargar los datos del expediente.");
        setEstado("error_lote");
      }
    })();
  }, [cargandoSesion, sesion, numeroPaja, router]);

  const personaTitularId = expediente?.abonado.titular_vigente?.id_persona ?? "";

  async function agregarArchivos(archivos: FileList | null) {
    if (!archivos || archivos.length === 0) return;

    const filasNuevas = await Promise.all(
      Array.from(archivos).map(async (archivo) => {
        const fila = nuevaFila(archivo, personaTitularId || "");
        fila.errorArchivo = await validarArchivoEnNavegador(archivo);
        return fila;
      }),
    );

    setFilas((actual) => [...actual, ...filasNuevas]);
  }

  function quitarFila(id: string) {
    setFilas((actual) => actual.filter((fila) => fila.id !== id));
  }

  function actualizarFila(id: string, cambios: Partial<FilaArchivo>) {
    setFilas((actual) =>
      actual.map((fila) => (fila.id === id ? { ...fila, ...cambios } : fila)),
    );
  }

  const documentosVigentes =
    expediente?.documentos.filter((documento) => documento.version_vigente) ?? [];

  async function guardar() {
    if (!sesion || filas.length === 0) return;

    if (modo === "nueva_version" && !documentoSeleccionado) {
      setMensajeLote("Elija de qué documento es la nueva versión.");
      setEstado("error_lote");
      return;
    }

    const conErrorLocal = filas.filter((fila) => fila.errorArchivo);

    if (conErrorLocal.length > 0) {
      setMensajeLote(
        `Hay ${conErrorLocal.length} archivo(s) con problemas. No se guardó ninguno todavía.`,
      );
      setEstado("error_lote");
      return;
    }

    setEstado("guardando");
    setMensajeLote(null);

    try {
      const respuesta = await cargarDocumentos({
        token: sesion.token,
        numeroPaja,
        archivos: filas.map((fila) => fila.archivo),
        metadatos: filas.map((fila) => ({
          es_nueva_version: modo === "nueva_version",
          id_documento:
            modo === "nueva_version" ? documentoSeleccionado!.id_documento : undefined,
          id_tipo_documento:
            modo === "nuevo" && fila.tipoDocumentoId !== ""
              ? Number(fila.tipoDocumentoId)
              : undefined,
          id_persona: fila.personaId !== "" ? Number(fila.personaId) : null,
          nombre_identificador: fila.nombreIdentificador || undefined,
          fecha_documento: fila.fechaDocumento,
        })),
      });

      setResultado(respuesta);
      setEstado("exito");
    } catch (error) {
      const payload = (error as { payload?: unknown })?.payload;

      if (esErrorDeCarga(payload)) {
        setMensajeLote(payload.detail);
        setFilas((actual) =>
          actual.map((fila, indice) => {
            const errorFila = payload.errores.find((e) => e.indice === indice);
            return errorFila
              ? { ...fila, erroresServidor: errorFila.errores }
              : { ...fila, erroresServidor: {} };
          }),
        );
      } else {
        setMensajeLote(
          error instanceof Error ? error.message : "No fue posible guardar.",
        );
      }

      setEstado("error_lote");
    }
  }

  if (cargandoSesion || estado === "cargando_datos") {
    return <p className="p-6">Cargando…</p>;
  }

  if (estado === "exito" && resultado) {
    return (
      <main className="mx-auto max-w-3xl p-6">
        <h1>Cargar documento</h1>
        <div className="mt-4 rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]">
          <p className="font-semibold">{resultado.detail}</p>
          <ul className="mt-2 list-disc pl-5">
            {resultado.documentos.map((documento) => (
              <li key={`${documento.id_documento}-${documento.numero_version}`}>
                {documento.tipo_documento}, con fecha del documento{" "}
                {documento.fecha_documento.split("-").reverse().join("/")}. La carga
                quedó en la bitácora a nombre de la cuenta.
              </li>
            ))}
          </ul>
        </div>
        <div className="mt-6 flex gap-3">
          <Button onClick={() => router.push(`/sigeda/expedientes/${numeroPaja}`)}>
            Ver expediente
          </Button>
          <Button variant="secondary" onClick={() => router.refresh()}>
            Cargar otro documento
          </Button>
        </div>
      </main>
    );
  }

  if (!expediente) {
    return (
      <main className="p-6">
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {mensajeLote}
        </div>
      </main>
    );
  }

  const { abonado, personas_vigentes: personasVigentes } = expediente;
  const hayErroresLocales = filas.some((fila) => fila.errorArchivo);

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <nav aria-label="Ruta">
        <button
          type="button"
          className="text-[var(--color-primary)]"
          onClick={() => router.push(`/sigeda/expedientes/${numeroPaja}`)}
        >
          Expediente {numeroPaja}
        </button>
        {" › "}
        <span>Cargar documento</span>
      </nav>

      <h1>Cargar documento</h1>
      <p>
        Expediente {abonado.numero_paja} · {abonado.titular_vigente?.nombre} ·{" "}
        {abonado.tipo_abonado === "PERSONA_FISICA" ? "Persona física" : "Persona jurídica"}{" "}
        · {abonado.sector}
      </p>

      {mensajeLote && estado === "error_lote" ? (
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          <p className="font-semibold">{mensajeLote}</p>
          <p>Corrija lo que se indica en cada archivo (o quítelo) y vuelva a presionar «Guardar documentos».</p>
        </div>
      ) : null}

      <fieldset className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4">
        <legend className="px-1 font-semibold">1. ¿Qué va a cargar?</legend>

        <label className="flex items-center gap-2 py-1">
          <input
            type="radio"
            name="modo"
            checked={modo === "nuevo"}
            onChange={() => setModo("nuevo")}
          />
          Documentos nuevos para este expediente
        </label>

        <label className="flex items-center gap-2 py-1">
          <input
            type="radio"
            name="modo"
            checked={modo === "nueva_version"}
            onChange={() => setModo("nueva_version")}
          />
          Una <strong>nueva versión</strong> de un documento que ya está en el expediente
        </label>

        {modo === "nueva_version" ? (
          <div className="mt-2 pl-6">
            <label htmlFor="documento-existente" className="font-semibold">
              Documento del que es nueva versión (obligatorio)
            </label>
            <select
              id="documento-existente"
              className="mt-1 h-12 w-full max-w-xl rounded-[var(--radius-md)] border border-[var(--color-border)] px-3"
              value={documentoSeleccionado?.id_documento ?? ""}
              onChange={(evento) => {
                const documento = documentosVigentes.find(
                  (d) => d.id_documento === Number(evento.target.value),
                );
                setDocumentoSeleccionado(documento ?? null);
              }}
            >
              <option value="">Elija un documento…</option>
              {documentosVigentes.map((documento) => (
                <option key={documento.id_documento} value={documento.id_documento}>
                  {documento.tipo_documento}
                  {documento.nombre_identificador
                    ? ` · ${documento.nombre_identificador}`
                    : ""}{" "}
                  ·{" "}
                  {documento.version_vigente!.fecha_documento
                    .split("-")
                    .reverse()
                    .join("/")}{" "}
                  (v{documento.version_vigente!.numero_version})
                </option>
              ))}
            </select>
            <p className="mt-1 text-sm text-[var(--color-text-muted)]">
              La versión anterior se conserva con su fecha; la nueva se muestra como
              vigente.
            </p>
          </div>
        ) : null}
      </fieldset>

      <fieldset className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4">
        <legend className="px-1 font-semibold">2. Archivos</legend>

        <label
          className="flex min-h-28 cursor-pointer flex-col items-center justify-center gap-1 rounded-[var(--radius-md)] border-2 border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface-muted)] p-4 text-center"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            e.preventDefault();
            agregarArchivos(e.dataTransfer.files);
          }}
        >
          <span>
            Arrastre aquí los archivos escaneados o{" "}
            <span className="font-semibold text-[var(--color-primary)]">
              Elegir archivos
            </span>
          </span>
          <span className="text-sm text-[var(--color-text-muted)]">
            Solo PDF o PNG · máximo 10 MB por archivo · puede elegir varios a la vez
          </span>
          <input
            type="file"
            accept=".pdf,.png,application/pdf,image/png"
            multiple
            className="sr-only"
            onChange={(e) => {
              agregarArchivos(e.target.files);
              e.target.value = "";
            }}
          />
        </label>
      </fieldset>

      {filas.length === 0 ? (
        <p>Todavía no ha elegido archivos.</p>
      ) : (
        <fieldset className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4">
          <legend className="px-1 font-semibold">3. Datos de cada archivo</legend>
          <p className="mb-3 text-sm text-[var(--color-text-muted)]">
            La fecha del documento se propone con la fecha de hoy. Si digitaliza un
            papel viejo, ponga la fecha que tiene el papel. La fecha y hora de carga se
            guardan solas y no se pueden cambiar.
          </p>

          <div className="flex flex-col gap-4">
            {filas.map((fila) => {
              const errorFormato = fila.errorArchivo ?? fila.erroresServidor.archivo;
              const errorTipo = fila.erroresServidor.tipo_documento;
              const errorFecha = fila.erroresServidor.fecha_documento;

              return (
                <div
                  key={fila.id}
                  className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-3"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-semibold">{fila.archivo.name}</p>
                      <p className="text-sm text-[var(--color-text-muted)]">
                        {(fila.archivo.size / (1024 * 1024)).toFixed(1).replace(".", ",")}{" "}
                        MB
                      </p>
                    </div>
                    <button
                      type="button"
                      className="text-[var(--color-primary)] underline"
                      onClick={() => quitarFila(fila.id)}
                    >
                      Quitar
                    </button>
                  </div>

                  {errorFormato ? (
                    <p className="mt-1 text-[var(--color-danger)]">⚠ {errorFormato}</p>
                  ) : null}

                  <div className="mt-2 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                    {modo === "nuevo" ? (
                      <div>
                        <label
                          htmlFor={`tipo-${fila.id}`}
                          className="text-sm font-medium"
                        >
                          Tipo de documento (oblig.)
                        </label>
                        <select
                          id={`tipo-${fila.id}`}
                          className="mt-1 h-11 w-full rounded-[var(--radius-md)] border border-[var(--color-border)] px-2"
                          value={fila.tipoDocumentoId}
                          onChange={(e) =>
                            actualizarFila(fila.id, {
                              tipoDocumentoId: e.target.value
                                ? Number(e.target.value)
                                : "",
                            })
                          }
                        >
                          <option value="">Elija el tipo…</option>
                          {tipos.map((tipo) => (
                            <option
                              key={tipo.id_tipo_documento}
                              value={tipo.id_tipo_documento}
                            >
                              {tipo.nombre}
                            </option>
                          ))}
                        </select>
                        {errorTipo ? (
                          <p className="text-sm text-[var(--color-danger)]">
                            ⚠ {errorTipo}
                          </p>
                        ) : null}
                      </div>
                    ) : null}

                    <div>
                      <label
                        htmlFor={`persona-${fila.id}`}
                        className="text-sm font-medium"
                      >
                        Persona que lo aporta
                      </label>
                      <select
                        id={`persona-${fila.id}`}
                        className="mt-1 h-11 w-full rounded-[var(--radius-md)] border border-[var(--color-border)] px-2"
                        value={fila.personaId}
                        onChange={(e) =>
                          actualizarFila(fila.id, {
                            personaId: e.target.value ? Number(e.target.value) : "",
                          })
                        }
                      >
                        <option value="">Sin especificar</option>
                        {abonado.titular_vigente ? (
                          <option value={abonado.titular_vigente.id_persona}>
                            {abonado.titular_vigente.nombre} (titular)
                          </option>
                        ) : null}
                        {personasVigentes
                          .filter((v) => v.rol !== "TITULAR")
                          .map((vinculo) => (
                            <option
                              key={vinculo.persona.id_persona}
                              value={vinculo.persona.id_persona}
                            >
                              {vinculo.persona.nombre} (
                              {vinculo.rol === "COTITULAR" ? "cotitular" : "apoderada"})
                            </option>
                          ))}
                      </select>
                    </div>

                    <div>
                      <label
                        htmlFor={`nombre-${fila.id}`}
                        className="text-sm font-medium"
                      >
                        Nombre identificador (opcional)
                      </label>
                      <Input
                        id={`nombre-${fila.id}`}
                        value={fila.nombreIdentificador}
                        onChange={(e) =>
                          actualizarFila(fila.id, {
                            nombreIdentificador: e.target.value,
                          })
                        }
                      />
                    </div>

                    <div>
                      <label
                        htmlFor={`fecha-${fila.id}`}
                        className="text-sm font-medium"
                      >
                        Fecha del documento (oblig.)
                      </label>
                      <Input
                        id={`fecha-${fila.id}`}
                        type="date"
                        value={fila.fechaDocumento}
                        onChange={(e) =>
                          actualizarFila(fila.id, {
                            fechaDocumento: e.target.value,
                          })
                        }
                      />
                      {errorFecha ? (
                        <p className="text-sm text-[var(--color-danger)]">
                          ⚠ {errorFecha}
                        </p>
                      ) : null}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </fieldset>
      )}

      <div className="flex gap-3">
        <Button
          onClick={guardar}
          isLoading={estado === "guardando"}
          loadingText="Guardando…"
          disabled={filas.length === 0 || hayErroresLocales}
        >
          Guardar documentos
        </Button>
        <Button
          variant="secondary"
          onClick={() => router.push(`/sigeda/expedientes/${numeroPaja}`)}
        >
          Cancelar
        </Button>
      </div>
    </main>
  );
}
