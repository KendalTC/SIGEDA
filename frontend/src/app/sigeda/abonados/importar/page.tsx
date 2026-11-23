"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Select } from "@/components/ui/select";
import {
  importarSada,
  vistaPreviaImportacionSada,
} from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import type {
  ResultadoImportacion,
  UsoColumnaImportacion,
  VistaPreviaImportacion,
} from "@/features/sigeda/types";

type Paso = "elegir" | "revisar" | "importando" | "resumen";

const ETIQUETAS_PASOS = [
  "1. Elegir archivo",
  "2. Revisar columnas",
  "3. Importar",
  "4. Resumen",
];

const INDICE_PASO: Record<Paso, number> = {
  elegir: 0,
  revisar: 1,
  importando: 2,
  resumen: 3,
};

function Pasos({ paso }: { paso: Paso }) {
  const actual = INDICE_PASO[paso];

  return (
    <ol
      aria-label="Pasos de la importación"
      className="flex flex-wrap gap-2"
    >
      {ETIQUETAS_PASOS.map((etiqueta, indice) => (
        <li key={etiqueta}>
          <span
            aria-current={indice === actual ? "step" : undefined}
            className={
              indice === actual
                ? "inline-flex items-center rounded-full bg-primary px-3 py-1 text-sm font-semibold text-white"
                : "inline-flex items-center rounded-full border border-[var(--color-border)] px-3 py-1 text-sm text-[var(--color-text-muted)]"
            }
          >
            {etiqueta}
          </span>
        </li>
      ))}
    </ol>
  );
}

function formatearMiles(n: number): string {
  return n.toString().replace(/\B(?=(\d{3})+(?!\d))/g, " ");
}

function formatearFecha(fechaIso: string): string {
  const [anio, mes, dia] = fechaIso.slice(0, 10).split("-");
  return `${dia}/${mes}/${anio}`;
}

/**
 * PAN-09 "Importar datos de SADA" (RF-04, CU no numerado de la ficha de
 * Prototipos v1.1). Los 4 pasos son fijos (no se puede saltar de uno a
 * otro con las pestañas; son un indicador de avance, no navegación).
 *
 * Decisión de hoy (ADR-04 ya tomado, ver plan): el archivo se manda al
 * backend dos veces — paso 2 solo lo lee para mostrar las columnas
 * reales y un ejemplo (fila 2), sin guardar nada; paso 3 lo manda otra
 * vez junto con el mapeo elegido y ahí sí crea los abonados. Es más
 * simple que guardar un archivo temporal en el servidor entre pasos, y
 * el listado de SADA es chico (1 015 filas).
 *
 * El paso 3 es un spinner indeterminado ("Importando…"): no hay forma
 * de calcular un avance real sin inventarlo (mismo criterio que
 * "Respaldar ahora" en el Incremento 3a), así que no se muestra ni
 * porcentaje ni "fila N de total" aunque la ficha original sí los
 * dibuja.
 */
export default function ImportarSadaPage() {
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [paso, setPaso] = useState<Paso>("elegir");

  const [archivo, setArchivo] = useState<File | null>(null);
  const [revisando, setRevisando] = useState(false);
  const [errorArchivo, setErrorArchivo] = useState<string | null>(null);

  const [vistaPrevia, setVistaPrevia] = useState<VistaPreviaImportacion | null>(
    null,
  );
  const [mapeo, setMapeo] = useState<Record<string, UsoColumnaImportacion>>({});
  const [errorMapeo, setErrorMapeo] = useState<string | null>(null);
  const [errorImportar, setErrorImportar] = useState<string | null>(null);

  const [resultado, setResultado] = useState<ResultadoImportacion | null>(null);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
    }
  }, [cargandoSesion, sesion, router]);

  const columnaPaja = Object.keys(mapeo).find((c) => mapeo[c] === "PAJA");
  const columnaNombre = Object.keys(mapeo).find((c) => mapeo[c] === "NOMBRE");

  // Paso 3: dispara la importación de verdad al entrar a este paso.
  useEffect(() => {
    if (paso !== "importando") return;
    if (!sesion || !archivo || !columnaPaja || !columnaNombre) return;

    let cancelado = false;

    (async () => {
      try {
        const respuesta = await importarSada(
          sesion.token,
          archivo,
          columnaPaja,
          columnaNombre,
        );

        if (cancelado) return;
        setResultado(respuesta);
        setPaso("resumen");
      } catch (err) {
        if (cancelado) return;

        setErrorImportar(
          err instanceof Error ? err.message : "No fue posible importar el archivo.",
        );
        setPaso("revisar");
      }
    })();

    return () => {
      cancelado = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paso]);

  function reiniciar() {
    setArchivo(null);
    setVistaPrevia(null);
    setMapeo({});
    setErrorMapeo(null);
    setErrorImportar(null);
    setErrorArchivo(null);
    setPaso("elegir");
  }

  async function elegirArchivo(lista: FileList | null) {
    const elegido = lista?.[0];
    if (!elegido || !sesion) return;

    setErrorArchivo(null);
    setRevisando(true);

    try {
      const previa = await vistaPreviaImportacionSada(sesion.token, elegido);

      setArchivo(elegido);
      setVistaPrevia(previa);
      // Decisión de hoy: todas las columnas arrancan en "No se usa" (no
      // se adivina el mapeo por el nombre de la columna) — SADA no
      // exporta nombres de columna fijos (S-05/RT-04), así que la
      // usuaria elige a mano las dos que importan.
      setMapeo(
        Object.fromEntries(
          previa.columnas.map((columna) => [columna, "NO_USA" as const]),
        ),
      );
      setErrorMapeo(null);
      setPaso("revisar");
    } catch (err) {
      setErrorArchivo(
        err instanceof Error ? err.message : "No fue posible leer el archivo.",
      );
    } finally {
      setRevisando(false);
    }
  }

  function cambiarUso(columna: string, uso: UsoColumnaImportacion) {
    setMapeo((actual) => {
      const nuevo = { ...actual };

      // Cada rol ("Número de paja", "Nombre del titular") solo puede
      // estar en una columna a la vez: si ya estaba en otra, esa otra
      // vuelve a "No se usa".
      if (uso !== "NO_USA") {
        for (const clave of Object.keys(nuevo)) {
          if (nuevo[clave] === uso) nuevo[clave] = "NO_USA";
        }
      }

      nuevo[columna] = uso;
      return nuevo;
    });
    setErrorMapeo(null);
  }

  function manejarEnvioRevisar(evento: FormEvent) {
    evento.preventDefault();

    if (!columnaPaja || !columnaNombre) {
      setErrorMapeo(
        "Elija qué columna es el número de paja y cuál es el nombre del titular.",
      );
      return;
    }

    setErrorImportar(null);
    setPaso("importando");
  }

  if (cargandoSesion || !sesion) {
    return <p className="p-6">Cargando…</p>;
  }

  return (
    <main className="mx-auto flex max-w-6xl flex-col gap-6 p-8">
      <nav aria-label="Ruta">
        <Link href="/sigeda/buscar" className="text-[var(--color-primary)]">
          Buscar expediente
        </Link>
        {" › "}
        <span>Importar SADA</span>
      </nav>

      <div className="flex flex-col gap-1">
        <h1>Importar datos de SADA</h1>
        <p>
          Crea los abonados a partir del listado que exporta SADA (número de
          paja y nombre).
        </p>
      </div>

      <Pasos paso={paso} />

      {paso === "elegir" ? (
        <fieldset className="rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] p-6">
          <legend className="px-1 font-semibold">Archivo de SADA</legend>

          <label
            className="flex min-h-28 cursor-pointer flex-col items-center justify-center gap-1 rounded-[var(--radius-md)] border-2 border-dashed border-[var(--color-border-strong)] bg-[var(--color-surface-muted)] p-4 text-center"
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              elegirArchivo(e.dataTransfer.files);
            }}
          >
            <span>
              Arrastre aquí el archivo exportado por SADA o{" "}
              <span className="font-semibold text-[var(--color-primary)]">
                Elegir archivo
              </span>
            </span>
            <span className="text-sm text-[var(--color-text-muted)]">
              Excel (.xlsx) o texto delimitado (.csv)
            </span>
            <input
              type="file"
              accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
              className="sr-only"
              onChange={(e) => {
                elegirArchivo(e.target.files);
                e.target.value = "";
              }}
            />
          </label>

          {revisando ? (
            <p role="status" className="mt-3 flex items-center gap-2">
              <span
                className="size-4 animate-spin rounded-full border-2 border-current border-r-transparent"
                aria-hidden="true"
              />
              Revisando archivo…
            </p>
          ) : null}

          {errorArchivo ? (
            <div
              role="alert"
              className="mt-3 rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
            >
              <p className="font-semibold">{errorArchivo}</p>
            </div>
          ) : null}

          <p className="mt-3 text-sm text-[var(--color-text-muted)]">
            Solo se crean los números de paja que no estén registrados. Los
            abonados importados quedan con tipo pendiente.
          </p>
        </fieldset>
      ) : null}

      {paso === "revisar" && vistaPrevia ? (
        <fieldset className="rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] p-6">
          <legend className="px-1 font-semibold">Columnas detectadas</legend>

          <p className="mb-3">
            <strong>{archivo?.name}</strong> ·{" "}
            {formatearMiles(vistaPrevia.total_filas)} filas
          </p>

          <form onSubmit={manejarEnvioRevisar} className="flex flex-col gap-4">
            <table className="w-full border-collapse text-left">
              <caption className="sr-only">Columnas detectadas</caption>
              <thead>
                <tr className="border-b border-[var(--color-border)]">
                  <th className="py-2" scope="col">
                    Columna del archivo
                  </th>
                  <th className="py-2" scope="col">
                    Se usa como
                  </th>
                  <th className="py-2" scope="col">
                    Ejemplo (fila 2)
                  </th>
                </tr>
              </thead>
              <tbody>
                {vistaPrevia.columnas.map((columna, indice) => (
                  <tr
                    key={columna}
                    className="border-b border-[var(--color-border-soft)]"
                  >
                    <td className="py-2">{columna}</td>
                    <td className="py-2">
                      <label className="sr-only" htmlFor={`uso-${columna}`}>
                        Uso de la columna {columna}
                      </label>
                      <Select
                        id={`uso-${columna}`}
                        value={mapeo[columna] ?? "NO_USA"}
                        onChange={(e) =>
                          cambiarUso(
                            columna,
                            e.target.value as UsoColumnaImportacion,
                          )
                        }
                      >
                        <option value="NO_USA">No se usa</option>
                        <option value="PAJA">Número de paja</option>
                        <option value="NOMBRE">Nombre del titular</option>
                      </Select>
                    </td>
                    <td className="py-2">
                      {vistaPrevia.ejemplo_fila_2?.[indice] || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {errorMapeo ? (
              <p className="text-[var(--color-danger)]">⚠ {errorMapeo}</p>
            ) : null}

            {errorImportar ? (
              <div
                role="alert"
                className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
              >
                {errorImportar}
              </div>
            ) : null}

            <div className="flex gap-3">
              <Button type="button" variant="secondary" onClick={reiniciar}>
                Elegir otro archivo
              </Button>
              <Button type="submit">Importar</Button>
            </div>
          </form>
        </fieldset>
      ) : null}

      {paso === "importando" ? (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] bg-[var(--color-surface-muted)] p-6"
        >
          <span
            className="size-5 animate-spin rounded-full border-2 border-current border-r-transparent"
            aria-hidden="true"
          />
          <span>Importando…</span>
        </div>
      ) : null}

      {paso === "resumen" && resultado ? (
        <div className="flex flex-col gap-6">
          <div
            role="status"
            className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
          >
            <p className="font-semibold">
              Importación terminada: {formatearMiles(resultado.importados)}{" "}
              abonado{resultado.importados === 1 ? "" : "s"} creado
              {resultado.importados === 1 ? "" : "s"} (
              {formatearFecha(resultado.fecha)}).
            </p>
            <p>Quedó en la bitácora a nombre de la cuenta {sesion.cuenta.usuario}.</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] border-l-4 border-l-[var(--color-success)] p-6">
              <p className="text-3xl font-bold">
                {formatearMiles(resultado.importados)}
              </p>
              <p className="text-sm text-[var(--color-text-muted)]">
                Importados (tipo pendiente)
              </p>
            </div>
            <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] border-l-4 border-l-[var(--color-border-strong)] p-6">
              <p className="text-3xl font-bold">
                {formatearMiles(resultado.omitidos)}
              </p>
              <p className="text-sm text-[var(--color-text-muted)]">
                Omitidos: la paja ya existía
              </p>
            </div>
            <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] border-l-4 border-l-[var(--color-danger)] p-6">
              <p className="text-3xl font-bold">
                {formatearMiles(resultado.rechazados.length)}
              </p>
              <p className="text-sm text-[var(--color-text-muted)]">
                Rechazados por error de formato
              </p>
            </div>
          </div>

          {resultado.rechazados.length > 0 ? (
            <section aria-labelledby="rechazados-titulo">
              <h2 id="rechazados-titulo">Rechazados</h2>
              <table className="mt-2 w-full border-collapse text-left">
                <caption className="sr-only">Filas rechazadas</caption>
                <thead>
                  <tr className="border-b border-[var(--color-border)]">
                    <th className="py-2" scope="col">
                      Fila
                    </th>
                    <th className="py-2" scope="col">
                      Problema
                    </th>
                    <th className="py-2" scope="col">
                      Qué hacer
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {resultado.rechazados.map((rechazo) => (
                    <tr
                      key={rechazo.fila}
                      className="border-b border-[var(--color-border-soft)]"
                    >
                      <td className="py-2">{rechazo.fila}</td>
                      <td className="py-2">{rechazo.problema}</td>
                      <td className="py-2">{rechazo.que_hacer}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          ) : null}

          <div
            role="status"
            className="rounded-[var(--radius-lg)] border border-[var(--color-border)] shadow-[var(--shadow-sm)] bg-[var(--color-surface-muted)] px-4 py-3"
          >
            <p className="font-semibold">Los nombres repetidos no se unen solos.</p>
            <p>
              SADA no trae la cédula. Cuando la complete en el expediente,
              SIGEDA avisa si esa persona ya existe y le ofrece usar sus datos.
            </p>
          </div>

          <div className="flex gap-3">
            <Button onClick={() => router.push("/sigeda/buscar")}>
              Ver abonados con tipo pendiente
            </Button>
          </div>
        </div>
      ) : null}
    </main>
  );
}
