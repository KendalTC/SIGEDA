"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
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
import {
  crearGrupoAlternativas,
  crearTipoDocumento,
  editarTipoDocumento,
  listarGruposAlternativas,
  listarTiposDocumentoAdmin,
} from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import type {
  GrupoAlternativas,
  ModoTipoDocumento,
  ObligatoriedadGrupo,
  ObligatoriedadTipoDocumento,
  TipoDocumentoAdmin,
} from "@/features/sigeda/types";

/** Las 4 opciones de obligatoriedad del tipo de documento, más la
 * quinta opción "pertenece a un grupo" que reemplaza a las otras 4
 * (CHECK del Modelo ER v1.1: una cosa u otra, nunca las dos). */
type ModoRadio = ObligatoriedadTipoDocumento | "GRUPO";

function textoObligatoriedad(obligatoriedad: ObligatoriedadTipoDocumento): string {
  switch (obligatoriedad) {
    case "PERSONA_FISICA":
      return "Persona física";
    case "PERSONA_JURIDICA":
      return "Persona jurídica";
    case "AMBAS":
      return "Ambas";
    case "NINGUNA":
      return "Ninguna";
  }
}

function textoObligatoriedadGrupo(obligatoriedad: ObligatoriedadGrupo): string {
  if (obligatoriedad === "AMBAS") return "Ambas";
  return obligatoriedad === "PERSONA_FISICA" ? "Persona física" : "Persona jurídica";
}

const OPCIONES_MODO: Array<{ valor: ModoRadio; etiqueta: string }> = [
  { valor: "AMBAS", etiqueta: "Ambas (persona física y jurídica)" },
  { valor: "PERSONA_FISICA", etiqueta: "Solo persona física" },
  { valor: "PERSONA_JURIDICA", etiqueta: "Solo persona jurídica" },
  { valor: "NINGUNA", etiqueta: "Ninguna (opcional para los dos tipos)" },
  { valor: "GRUPO", etiqueta: "Pertenece a un grupo de alternativas" },
];

/**
 * PAN-10 "Tipos de documento" (RF-09). Un solo formulario sirve para
 * crear y para editar: "Editar" en una fila de la tabla lo rellena con
 * los datos de ese tipo; el botón principal siempre dice "Guardar".
 *
 * El panel de grupos de alternativas vive aparte porque un grupo no se
 * edita acá (solo se crea): la ficha solo describe el diálogo de alta.
 */
export default function TiposDocumentoPage() {
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [tipos, setTipos] = useState<TipoDocumentoAdmin[]>([]);
  const [grupos, setGrupos] = useState<GrupoAlternativas[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mensajeExito, setMensajeExito] = useState<string | null>(null);
  const primeraCargaHecha = useRef(false);

  // --- Formulario "Nuevo/Editar tipo de documento" --------------------
  const [idEditando, setIdEditando] = useState<number | null>(null);
  const [nombre, setNombre] = useState("");
  const [prioridad, setPrioridad] = useState("");
  const [modo, setModo] = useState<ModoRadio>("AMBAS");
  const [idGrupoElegido, setIdGrupoElegido] = useState<number | "">("");
  const [exigidoACotitulares, setExigidoACotitulares] = useState(false);
  const [errorFormulario, setErrorFormulario] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    if (!sesion) return;

    if (!primeraCargaHecha.current) setCargando(true);
    setError(null);

    try {
      const [listaTipos, listaGrupos] = await Promise.all([
        listarTiposDocumentoAdmin(sesion.token),
        listarGruposAlternativas(sesion.token),
      ]);
      setTipos(listaTipos);
      setGrupos(listaGrupos);
      primeraCargaHecha.current = true;
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No fue posible consultar los tipos de documento.",
      );
    } finally {
      setCargando(false);
    }
  }, [sesion]);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    cargar();
  }, [cargandoSesion, sesion, router, cargar]);

  function limpiarFormulario() {
    setIdEditando(null);
    setNombre("");
    setPrioridad("");
    setModo("AMBAS");
    setIdGrupoElegido(grupos[0]?.id_grupo_alternativas ?? "");
    setExigidoACotitulares(false);
    setErrorFormulario(null);
  }

  function abrirEdicion(tipo: TipoDocumentoAdmin) {
    setMensajeExito(null);
    setIdEditando(tipo.id_tipo_documento);
    setNombre(tipo.nombre);
    setPrioridad(String(tipo.prioridad));
    setExigidoACotitulares(tipo.es_exigido_a_cotitulares);
    setErrorFormulario(null);

    if (tipo.grupo_alternativas) {
      setModo("GRUPO");
      setIdGrupoElegido(tipo.grupo_alternativas.id_grupo_alternativas);
    } else {
      setModo(tipo.obligatoriedad ?? "AMBAS");
      setIdGrupoElegido(grupos[0]?.id_grupo_alternativas ?? "");
    }

    document
      .getElementById("form-tipo-documento-titulo")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function manejarEnvio(evento: FormEvent) {
    evento.preventDefault();

    const nombreLimpio = nombre.trim();
    const prioridadNumero = Number(prioridad);

    if (!nombreLimpio) {
      setErrorFormulario("Escriba el nombre del tipo de documento.");
      return;
    }

    if (!prioridad || !Number.isInteger(prioridadNumero) || prioridadNumero <= 0) {
      setErrorFormulario("La prioridad debe ser un número entero mayor que 0.");
      return;
    }

    if (modo === "GRUPO" && !idGrupoElegido) {
      setErrorFormulario("Elija a qué grupo de alternativas pertenece.");
      return;
    }

    if (!sesion) return;

    const modoEnvio: ModoTipoDocumento = modo === "GRUPO" ? "GRUPO" : "OBLIGATORIEDAD";
    const datos = {
      nombre: nombreLimpio,
      prioridad: prioridadNumero,
      modo: modoEnvio,
      ...(modoEnvio === "GRUPO"
        ? { id_grupo_alternativas: Number(idGrupoElegido) }
        : { obligatoriedad: modo as ObligatoriedadTipoDocumento }),
      es_exigido_a_cotitulares: exigidoACotitulares,
    };

    setGuardando(true);
    setErrorFormulario(null);

    try {
      const respuesta = idEditando
        ? await editarTipoDocumento(sesion.token, idEditando, datos)
        : await crearTipoDocumento(sesion.token, datos);

      setMensajeExito(respuesta.detail);
      limpiarFormulario();
      await cargar();
    } catch (err) {
      setErrorFormulario(
        err instanceof Error ? err.message : "No fue posible guardar el tipo de documento.",
      );
    } finally {
      setGuardando(false);
    }
  }

  // --- Diálogo "Nuevo grupo de alternativas" --------------------------
  const dialogGrupoRef = useRef<HTMLDialogElement>(null);
  const [nombreGrupo, setNombreGrupo] = useState("");
  const [obligatoriedadGrupo, setObligatoriedadGrupo] =
    useState<ObligatoriedadGrupo>("AMBAS");
  const [idsElegidos, setIdsElegidos] = useState<number[]>([]);
  const [errorGrupo, setErrorGrupo] = useState<string | null>(null);
  const [guardandoGrupo, setGuardandoGrupo] = useState(false);

  function abrirDialogoGrupo() {
    setNombreGrupo("");
    setObligatoriedadGrupo("AMBAS");
    setIdsElegidos([]);
    setErrorGrupo(null);
    dialogGrupoRef.current?.showModal();
  }

  function alternarTipoElegido(id: number) {
    setIdsElegidos((actual) =>
      actual.includes(id) ? actual.filter((x) => x !== id) : [...actual, id],
    );
    setErrorGrupo(null);
  }

  async function manejarEnvioGrupo(evento: FormEvent) {
    evento.preventDefault();

    const nombreLimpio = nombreGrupo.trim();

    if (!nombreLimpio) {
      setErrorGrupo("Escriba el nombre del grupo.");
      return;
    }

    if (!sesion) return;

    setGuardandoGrupo(true);
    setErrorGrupo(null);

    try {
      const respuesta = await crearGrupoAlternativas(sesion.token, {
        nombre: nombreLimpio,
        obligatoriedad: obligatoriedadGrupo,
        ids_tipos_documento: idsElegidos,
      });

      dialogGrupoRef.current?.close();
      setMensajeExito(respuesta.detail);
      await cargar();
    } catch (err) {
      setErrorGrupo(
        err instanceof Error ? err.message : "No fue posible crear el grupo.",
      );
    } finally {
      setGuardandoGrupo(false);
    }
  }

  if (cargandoSesion || cargando) {
    return <p className="p-6">Cargando…</p>;
  }

  if (error && tipos.length === 0) {
    return (
      <main className="mx-auto flex max-w-7xl flex-col gap-4 p-8">
        <h1>Tipos de documento</h1>
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {error}
        </div>
        <Button onClick={() => cargar()}>Reintentar</Button>
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-7xl flex-col gap-6 p-8">
      <nav aria-label="Ruta">
        <Link href="/sigeda/buscar" className="text-[var(--color-primary)]">
          Buscar expediente
        </Link>
        {" › "}
        <span>Tipos de documento</span>
      </nav>

      <div className="flex flex-col gap-1">
        <h1>Tipos de documento</h1>
        <p>
          Define la prioridad del expediente (RN-05), si cada tipo es
          obligatorio y para quién, o si forma parte de un grupo de
          alternativas.
        </p>
      </div>

      {mensajeExito ? (
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
        >
          {mensajeExito}
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

      <section aria-labelledby="tabla-tipos-titulo">
        <h2 id="tabla-tipos-titulo">Tipos registrados ({tipos.length})</h2>

        {tipos.length === 0 ? (
          <p>Todavía no hay tipos de documento registrados.</p>
        ) : (
          <table className="mt-4 w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2">Nombre</th>
                <th className="py-2">Prioridad</th>
                <th className="py-2">Obligatoriedad</th>
                <th className="py-2">Exigido a cotitulares</th>
                <th className="py-2">Acciones</th>
              </tr>
            </thead>
            <tbody>
              {tipos.map((tipo) => (
                <tr
                  key={tipo.id_tipo_documento}
                  className="border-b border-[var(--color-border-soft)]"
                >
                  <td className="py-2 font-semibold">{tipo.nombre}</td>
                  <td className="py-2">{tipo.prioridad}</td>
                  <td className="py-2">
                    {tipo.grupo_alternativas
                      ? `Grupo: ${tipo.grupo_alternativas.nombre}`
                      : textoObligatoriedad(tipo.obligatoriedad ?? "NINGUNA")}
                  </td>
                  <td className="py-2">{tipo.es_exigido_a_cotitulares ? "Sí" : "No"}</td>
                  <td className="py-2">
                    <button
                      type="button"
                      className="text-[var(--color-primary)] underline"
                      onClick={() => abrirEdicion(tipo)}
                    >
                      Editar
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section aria-labelledby="form-tipo-documento-titulo">
        <h2 id="form-tipo-documento-titulo">
          {idEditando ? `Editar tipo de documento «${nombre}»` : "Nuevo tipo de documento"}
        </h2>

        <form
          onSubmit={manejarEnvio}
          className="mt-3 flex flex-col gap-4 rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] p-6"
        >
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-[2fr_1fr]">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="tipo-nombre">Nombre (obligatorio)</label>
              <Input
                id="tipo-nombre"
                value={nombre}
                onChange={(e) => {
                  setNombre(e.target.value);
                  setErrorFormulario(null);
                }}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="tipo-prioridad">Prioridad (obligatorio)</label>
              <Input
                id="tipo-prioridad"
                type="number"
                min={1}
                step={1}
                value={prioridad}
                onChange={(e) => {
                  setPrioridad(e.target.value);
                  setErrorFormulario(null);
                }}
              />
            </div>
          </div>

          <fieldset className="flex flex-col gap-2">
            <legend className="font-semibold">Obligatoriedad (obligatorio)</legend>
            {OPCIONES_MODO.map((opcion) => (
              <label key={opcion.valor} className="flex items-center gap-2">
                <input
                  type="radio"
                  name="modo-obligatoriedad"
                  checked={modo === opcion.valor}
                  onChange={() => {
                    setModo(opcion.valor);
                    setErrorFormulario(null);
                  }}
                />
                {opcion.etiqueta}
              </label>
            ))}

            {modo === "GRUPO" ? (
              <div className="ml-6 flex flex-col gap-1.5">
                <label htmlFor="tipo-grupo">Grupo de alternativas (obligatorio)</label>
                <Select
                  id="tipo-grupo"
                  value={idGrupoElegido}
                  onChange={(e) => {
                    setIdGrupoElegido(e.target.value ? Number(e.target.value) : "");
                    setErrorFormulario(null);
                  }}
                >
                  {grupos.length === 0 ? (
                    <option value="">No hay grupos creados todavía</option>
                  ) : (
                    <option value="">Elija el grupo…</option>
                  )}
                  {grupos.map((grupo) => (
                    <option
                      key={grupo.id_grupo_alternativas}
                      value={grupo.id_grupo_alternativas}
                    >
                      {grupo.nombre}
                    </option>
                  ))}
                </Select>
              </div>
            ) : null}
          </fieldset>

          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={exigidoACotitulares}
              onChange={(e) => setExigidoACotitulares(e.target.checked)}
            />
            Exigirlo también a cada persona cotitular
          </label>

          {errorFormulario ? (
            <p role="alert" className="text-sm text-[var(--color-danger)]">
              ⚠ {errorFormulario}
            </p>
          ) : null}

          <div className="flex justify-end gap-3">
            {idEditando ? (
              <Button type="button" variant="secondary" onClick={limpiarFormulario}>
                Cancelar edición
              </Button>
            ) : null}
            <Button type="submit" isLoading={guardando}>
              Guardar
            </Button>
          </div>
        </form>
      </section>

      <section aria-labelledby="grupos-titulo">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="grupos-titulo">Grupos de alternativas ({grupos.length})</h2>
          <Button variant="secondary" onClick={abrirDialogoGrupo}>
            + Nuevo grupo
          </Button>
        </div>

        {grupos.length === 0 ? (
          <p className="mt-3">Todavía no hay grupos de alternativas.</p>
        ) : (
          <ul className="mt-3 flex flex-col gap-3">
            {grupos.map((grupo) => (
              <li
                key={grupo.id_grupo_alternativas}
                className="rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] p-6"
              >
                <p className="font-semibold">
                  {grupo.nombre} · {textoObligatoriedadGrupo(grupo.obligatoriedad)}
                </p>
                <p className="text-sm text-[var(--color-text-muted)]">
                  {grupo.tipos_documento.map((t) => t.nombre).join(" · ")}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* "Nuevo grupo de alternativas" */}
      <dialog
        ref={dialogGrupoRef}
        aria-labelledby="dialogo-grupo-titulo"
        className="m-auto w-[min(560px,calc(100vw-32px))] rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-background p-6 text-foreground shadow-[var(--shadow-lg)] backdrop:bg-[rgb(15_23_42_/_45%)]"
      >
        <form onSubmit={manejarEnvioGrupo} className="flex flex-col gap-4">
          <h2 id="dialogo-grupo-titulo">Nuevo grupo de alternativas</h2>
          <p>
            Un grupo necesita al menos 2 tipos de documento: con cualquiera de
            ellos vigente, el expediente cumple.
          </p>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="grupo-nombre">Nombre (obligatorio)</label>
            <Input
              id="grupo-nombre"
              value={nombreGrupo}
              onChange={(e) => {
                setNombreGrupo(e.target.value);
                setErrorGrupo(null);
              }}
            />
          </div>

          <fieldset className="flex flex-col gap-2">
            <legend className="font-semibold">Obligatoriedad (obligatorio)</legend>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="grupo-obligatoriedad"
                checked={obligatoriedadGrupo === "AMBAS"}
                onChange={() => setObligatoriedadGrupo("AMBAS")}
              />
              Ambas (persona física y jurídica)
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="grupo-obligatoriedad"
                checked={obligatoriedadGrupo === "PERSONA_FISICA"}
                onChange={() => setObligatoriedadGrupo("PERSONA_FISICA")}
              />
              Solo persona física
            </label>
            <label className="flex items-center gap-2">
              <input
                type="radio"
                name="grupo-obligatoriedad"
                checked={obligatoriedadGrupo === "PERSONA_JURIDICA"}
                onChange={() => setObligatoriedadGrupo("PERSONA_JURIDICA")}
              />
              Solo persona jurídica
            </label>
          </fieldset>

          <fieldset className="flex flex-col gap-2">
            <legend className="font-semibold">
              Tipos de documento del grupo (mínimo 2)
            </legend>
            {tipos.length === 0 ? (
              <p className="text-sm text-[var(--color-text-muted)]">
                No hay tipos de documento todavía.
              </p>
            ) : (
              tipos.map((tipo) => (
                <label key={tipo.id_tipo_documento} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={idsElegidos.includes(tipo.id_tipo_documento)}
                    onChange={() => alternarTipoElegido(tipo.id_tipo_documento)}
                  />
                  {tipo.nombre}
                </label>
              ))
            )}
          </fieldset>

          {errorGrupo ? (
            <p role="alert" className="text-sm text-[var(--color-danger)]">
              ⚠ {errorGrupo}
            </p>
          ) : null}

          <div className="flex justify-end gap-3">
            <Button
              type="button"
              variant="secondary"
              onClick={() => dialogGrupoRef.current?.close()}
            >
              Cancelar
            </Button>
            <Button type="submit" isLoading={guardandoGrupo}>
              Crear grupo
            </Button>
          </div>
        </form>
      </dialog>
    </main>
  );
}
