"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { buscarExpedientes, listarSectores } from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import type {
  ResultadoBusqueda,
  SectorCatalogo,
} from "@/features/sigeda/types";

const TOTAL_ABONADOS_APROX = "1 015";
const PATRON_PAJA = /^[0-9]+$/;

type Estado = "inicial" | "cargando" | "exito" | "sin_resultados" | "error";

function construirCriterioLegible(args: {
  nombre: string;
  numeroPaja: string;
  identificacion: string;
  sectorNombre: string | null;
}): string {
  if (args.nombre) return args.nombre;
  if (args.numeroPaja) return args.numeroPaja;
  if (args.identificacion) return args.identificacion;
  if (args.sectorNombre) return `el sector ${args.sectorNombre}`;
  return "los criterios indicados";
}

export default function BuscarExpedientePage() {
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [sectores, setSectores] = useState<SectorCatalogo[]>([]);
  const [numeroPaja, setNumeroPaja] = useState("");
  const [nombre, setNombre] = useState("");
  const [identificacion, setIdentificacion] = useState("");
  const [idSector, setIdSector] = useState("");
  const [incluirBaja, setIncluirBaja] = useState(true);

  const [estado, setEstado] = useState<Estado>("inicial");
  const [errorPaja, setErrorPaja] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [pajaSinResultados, setPajaSinResultados] = useState<string | null>(null);
  const [avisoLimite, setAvisoLimite] = useState<string | null>(null);
  const [resultados, setResultados] = useState<ResultadoBusqueda[]>([]);

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

  const hayCriterios = Boolean(
    numeroPaja || nombre || identificacion || idSector,
  );

  async function ejecutarBusqueda(idSectorOverride?: string) {
    if (!sesion) return;

    const idSectorActual = idSectorOverride ?? idSector;

    if (numeroPaja && !PATRON_PAJA.test(numeroPaja)) {
      setErrorPaja(
        "El número de paja solo lleva números (puede empezar con cero). " +
          "Escríbalo sin espacios, letras ni guiones, por ejemplo 0412.",
      );
      return;
    }

    setErrorPaja(null);

    const hayCriteriosActuales = Boolean(
      numeroPaja || nombre || identificacion || idSectorActual,
    );

    if (!hayCriteriosActuales) {
      setEstado("inicial");
      setMensaje(null);
      setAvisoLimite(null);
      setResultados([]);
      return;
    }

    setEstado("cargando");
    setMensaje(null);
    setAvisoLimite(null);

    const sectorNombre =
      sectores.find((s) => String(s.id_sector) === idSectorActual)?.nombre ??
      null;

    try {
      const respuesta = await buscarExpedientes(sesion.token, {
        numero_paja: numeroPaja || undefined,
        nombre: nombre || undefined,
        identificacion: identificacion || undefined,
        id_sector: idSectorActual ? Number(idSectorActual) : undefined,
        incluir_baja: incluirBaja,
      });

      const criterioLegible = construirCriterioLegible({
        nombre,
        numeroPaja,
        identificacion,
        sectorNombre,
      });
      const tiempoTexto = respuesta.tiempo_segundos
        .toFixed(1)
        .replace(".", ",");

      if (respuesta.total === 0) {
        setEstado("sin_resultados");
        setResultados([]);
        setPajaSinResultados(numeroPaja || null);
        setMensaje(
          numeroPaja
            ? `No hay expedientes con el número de paja ${numeroPaja}. Revise ` +
              "el número o busque por el nombre del titular. Si el abonado " +
              "es nuevo, puede registrarlo."
            : `No se encontraron expedientes para ${criterioLegible}. Revise ` +
              "los criterios e intente de nuevo.",
        );
        return;
      }

      setPajaSinResultados(null);
      setEstado("exito");
      setResultados(respuesta.resultados);
      setMensaje(
        `${respuesta.total} expedientes encontrados para ${criterioLegible} ` +
          `en ${tiempoTexto} s`,
      );

      if (respuesta.total > respuesta.mostrados) {
        const contexto = sectorNombre ? ` del sector ${sectorNombre}` : "";
        setAvisoLimite(
          `Se muestran los primeros ${respuesta.mostrados} de ` +
            `${respuesta.total} expedientes${contexto}. Agregue el nombre o ` +
            "el número de paja para acotar.",
        );
      }
    } catch (err) {
      setEstado("error");
      setResultados([]);
      setMensaje(
        err instanceof Error
          ? err.message
          : "No fue posible completar la búsqueda.",
      );
    }
  }

  async function manejarEnvio(evento: FormEvent) {
    evento.preventDefault();
    await ejecutarBusqueda();
  }

  function manejarCambioSector(evento: ChangeEvent<HTMLSelectElement>) {
    const nuevoSector = evento.target.value;
    setIdSector(nuevoSector);
    ejecutarBusqueda(nuevoSector);
  }

  function limpiar() {
    setNumeroPaja("");
    setNombre("");
    setIdentificacion("");
    setIdSector("");
    setIncluirBaja(true);
    setEstado("inicial");
    setMensaje(null);
    setPajaSinResultados(null);
    setAvisoLimite(null);
    setErrorPaja(null);
    setResultados([]);
  }

  if (cargandoSesion) {
    return <p className="p-6">Cargando…</p>;
  }

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <h1>Buscar expediente</h1>

      <form onSubmit={manejarEnvio} className="flex flex-col gap-4" noValidate>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="numero-paja">Número de paja</label>
            <Input
              id="numero-paja"
              value={numeroPaja}
              onChange={(e) => {
                setNumeroPaja(e.target.value);
                setErrorPaja(null);
              }}
              hasError={Boolean(errorPaja)}
            />
            {errorPaja ? (
              <p className="text-sm text-[var(--color-danger)]">
                ⚠ {errorPaja}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="nombre-titular">Nombre del titular</label>
            <Input
              id="nombre-titular"
              value={nombre}
              onChange={(e) => setNombre(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="identificacion">Identificación</label>
            <Input
              id="identificacion"
              value={identificacion}
              onChange={(e) => setIdentificacion(e.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="sector">Sector</label>
            <Select id="sector" value={idSector} onChange={manejarCambioSector}>
              <option value="">Todos</option>
              {sectores.map((sector) => (
                <option key={sector.id_sector} value={sector.id_sector}>
                  {sector.nombre}
                </option>
              ))}
            </Select>
          </div>
        </div>

        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={incluirBaja}
            onChange={(e) => setIncluirBaja(e.target.checked)}
          />
          Incluir abonados de baja
        </label>

        <div className="flex gap-3">
          <Button
            type="submit"
            isLoading={estado === "cargando"}
            loadingText="Buscando…"
            disabled={!hayCriterios}
          >
            Buscar
          </Button>
          <Button type="button" variant="secondary" onClick={limpiar}>
            Limpiar
          </Button>
        </div>
      </form>

      {estado === "inicial" ? (
        <p className="text-[var(--color-text-muted)]">
          Escriba al menos un criterio y presione Buscar
        </p>
      ) : null}

      {estado === "cargando" ? (
        <p role="status">Buscando en {TOTAL_ABONADOS_APROX} expedientes…</p>
      ) : null}

      {estado === "sin_resultados" ? (
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]"
        >
          {pajaSinResultados ? (
            <p>
              No hay expedientes con el número de paja {pajaSinResultados}.
              Revise el número o busque por el nombre del titular. Si el
              abonado es nuevo, puede{" "}
              <Link href="/sigeda/abonados/nuevo" className="underline">
                registrarlo
              </Link>
              .
            </p>
          ) : (
            mensaje
          )}
        </div>
      ) : null}

      {estado === "error" ? (
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {mensaje}
        </div>
      ) : null}

      {estado === "exito" ? (
        <section aria-labelledby="resultados-titulo">
          <p
            id="resultados-titulo"
            className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
          >
            {mensaje}
          </p>

          {avisoLimite ? (
            <p className="mt-2 text-[var(--color-warning)]">⚠ {avisoLimite}</p>
          ) : null}

          <table className="mt-4 w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2">Paja</th>
                <th className="py-2">Titular vigente</th>
                <th className="py-2">Identificación</th>
                <th className="py-2">Sector</th>
                <th className="py-2">Tipo</th>
                <th className="py-2">Estado</th>
              </tr>
            </thead>
            <tbody>
              {resultados.map((resultado) => (
                <tr
                  key={resultado.numero_paja}
                  className="cursor-pointer border-b border-[var(--color-border-soft)] hover:bg-[var(--color-surface-muted)]"
                  onClick={() =>
                    router.push(`/sigeda/expedientes/${resultado.numero_paja}`)
                  }
                >
                  <td className="py-2">
                    <Link
                      href={`/sigeda/expedientes/${resultado.numero_paja}`}
                      className="text-[var(--color-primary)] underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {resultado.numero_paja}
                    </Link>
                  </td>
                  <td className="py-2">{resultado.titular_vigente ?? "—"}</td>
                  <td className="py-2">
                    {resultado.identificacion_parcial ?? "—"}
                  </td>
                  <td className="py-2">{resultado.sector ?? "—"}</td>
                  <td className="py-2">
                    {resultado.tipo_abonado === "PERSONA_FISICA"
                      ? "Persona física"
                      : resultado.tipo_abonado === "PERSONA_JURIDICA"
                        ? "Persona jurídica"
                        : "Pendiente"}
                  </td>
                  <td className="py-2">
                    {resultado.estado === "ACTIVO" ? "Activo" : "De baja"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </main>
  );
}
