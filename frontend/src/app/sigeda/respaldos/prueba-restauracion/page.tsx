"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { FechaInput } from "@/components/forms/fecha-input";
import {
  listarPruebasRestauracion,
  obtenerRespaldos,
  registrarPruebaRestauracion,
} from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import {
  formatearFecha,
  formatearFechaHora,
  textoTipoRespaldo,
} from "@/features/sigeda/respaldos-estado";
import { hoyComoFechaIso } from "@/features/sigeda/validacion-archivo";
import type {
  PruebaRestauracion,
  Respaldo,
  ResultadoPruebaRestauracion,
} from "@/features/sigeda/types";

/**
 * Sub-pantalla de PAN-08: "Registrar una prueba de restauración"
 * (RNF-04). Es un registro manual, no una ejecución automática
 * (CLAUDE.md sección 9, tabla propuesta `prueba_restauracion`). Textos
 * literales del Prototipos v1.1.
 */
export default function PruebaRestauracionPage() {
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [respaldosCompletos, setRespaldosCompletos] = useState<Respaldo[]>([]);
  const [pruebas, setPruebas] = useState<PruebaRestauracion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [errorCarga, setErrorCarga] = useState<string | null>(null);

  const [fecha, setFecha] = useState(hoyComoFechaIso());
  const [idRespaldo, setIdRespaldo] = useState<number | "">("");
  const [computadoraUsada, setComputadoraUsada] = useState("");
  const [resultado, setResultado] = useState<ResultadoPruebaRestauracion | "">("");
  const [observaciones, setObservaciones] = useState("");

  const [errorRespaldo, setErrorRespaldo] = useState<string | null>(null);
  const [errorResultado, setErrorResultado] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [guardada, setGuardada] = useState(false);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    Promise.all([
      obtenerRespaldos(sesion.token),
      listarPruebasRestauracion(sesion.token).catch(() => []),
    ])
      .then(([respuestaRespaldos, listaPruebas]) => {
        const completos = respuestaRespaldos.respaldos.filter(
          (r) => r.estado === "COMPLETO",
        );
        setRespaldosCompletos(completos);
        setIdRespaldo(completos[0]?.id_respaldo ?? "");
        setPruebas(listaPruebas);
      })
      .catch((err) =>
        setErrorCarga(
          err instanceof Error
            ? err.message
            : "No fue posible cargar los respaldos disponibles.",
        ),
      )
      .finally(() => setCargando(false));
  }, [cargandoSesion, sesion, router]);

  async function manejarEnvio(evento: FormEvent) {
    evento.preventDefault();
    if (!sesion) return;

    setErrorRespaldo(null);
    setErrorResultado(null);

    if (!idRespaldo) {
      setErrorRespaldo("Elija el respaldo que se probó.");
      return;
    }
    if (!resultado) {
      setErrorResultado("Elija el resultado de la prueba.");
      return;
    }

    setEnviando(true);
    setError(null);

    try {
      await registrarPruebaRestauracion(sesion.token, {
        fecha,
        id_respaldo: idRespaldo,
        computadora_usada: computadoraUsada.trim(),
        resultado,
        observaciones: observaciones.trim() || null,
      });
      setGuardada(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible guardar la prueba.",
      );
    } finally {
      setEnviando(false);
    }
  }

  if (cargandoSesion || cargando) {
    return <p className="p-6">Cargando…</p>;
  }

  if (guardada) {
    return (
      <main className="mx-auto flex max-w-2xl flex-col gap-6 p-6">
        <h1>Prueba de restauración registrada</h1>
        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
        >
          La prueba quedó registrada.
        </div>
        <div className="flex gap-3">
          <Button onClick={() => router.push("/sigeda/respaldos")}>
            Volver a respaldos
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              setGuardada(false);
              setComputadoraUsada("");
              setResultado("");
              setObservaciones("");
              setFecha(hoyComoFechaIso());
            }}
          >
            Registrar otra prueba
          </Button>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto flex max-w-2xl flex-col gap-6 p-6">
      <nav aria-label="Ruta">
        <Link href="/sigeda/respaldos" className="text-[var(--color-primary)]">
          Respaldos
        </Link>
        {" › "}
        <span>Prueba de restauración</span>
      </nav>

      <div className="flex flex-col gap-1">
        <h1>Registrar una prueba de restauración</h1>
        <p>
          Cada 3 meses (propuesta) se restaura un respaldo en otra computadora
          para comprobar que sirve (RNF-04). Aquí se anota el resultado.
        </p>
      </div>

      {errorCarga ? (
        <div
          role="alert"
          className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
        >
          {errorCarga}
        </div>
      ) : null}

      {pruebas.length > 0 ? (
        <details>
          <summary className="cursor-pointer select-none font-semibold">
            Pruebas registradas anteriormente ({pruebas.length})
          </summary>
          <ul className="mt-2 flex flex-col gap-1 text-sm text-[var(--color-text-muted)]">
            {pruebas.map((prueba) => (
              <li key={prueba.id_prueba_restauracion}>
                {formatearFecha(prueba.fecha)} · {prueba.computadora_usada} ·{" "}
                {prueba.resultado === "EXITOSA"
                  ? "Se recuperó todo y las huellas coinciden"
                  : "Hubo problemas"}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      <form onSubmit={manejarEnvio} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="prueba-fecha">Fecha de la prueba (obligatorio)</label>
          <FechaInput id="prueba-fecha" valorIso={fecha} onChangeIso={setFecha} />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="prueba-respaldo">Respaldo probado (obligatorio)</label>
          <Select
            id="prueba-respaldo"
            value={idRespaldo}
            hasError={Boolean(errorRespaldo)}
            onChange={(e) => {
              setIdRespaldo(e.target.value ? Number(e.target.value) : "");
              setErrorRespaldo(null);
            }}
          >
            {respaldosCompletos.length === 0 ? (
              <option value="">No hay respaldos completos disponibles</option>
            ) : null}
            {respaldosCompletos.map((respaldo) => (
              <option key={respaldo.id_respaldo} value={respaldo.id_respaldo}>
                {formatearFechaHora(respaldo.fecha_hora)} ·{" "}
                {textoTipoRespaldo(respaldo.tipo)}
              </option>
            ))}
          </Select>
          {errorRespaldo ? (
            <p className="text-sm text-[var(--color-danger)]">⚠ {errorRespaldo}</p>
          ) : null}
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="prueba-computadora">Computadora usada (obligatorio)</label>
          <Input
            id="prueba-computadora"
            placeholder="Computadora personal de la Administración"
            value={computadoraUsada}
            onChange={(e) => setComputadoraUsada(e.target.value)}
          />
        </div>

        <fieldset className="flex flex-col gap-2">
          <legend className="font-semibold">Resultado (obligatorio)</legend>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="resultado"
              value="EXITOSA"
              checked={resultado === "EXITOSA"}
              onChange={() => {
                setResultado("EXITOSA");
                setErrorResultado(null);
              }}
            />
            Se recuperó todo y las huellas coinciden
          </label>
          <label className="flex items-center gap-2">
            <input
              type="radio"
              name="resultado"
              value="CON_PROBLEMAS"
              checked={resultado === "CON_PROBLEMAS"}
              onChange={() => {
                setResultado("CON_PROBLEMAS");
                setErrorResultado(null);
              }}
            />
            Hubo problemas
          </label>
          {errorResultado ? (
            <p className="text-sm text-[var(--color-danger)]">⚠ {errorResultado}</p>
          ) : null}
        </fieldset>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="prueba-observaciones">Observaciones (opcional)</label>
          <Textarea
            id="prueba-observaciones"
            rows={3}
            value={observaciones}
            onChange={(e) => setObservaciones(e.target.value)}
          />
        </div>

        {error ? (
          <p role="alert" className="text-sm text-[var(--color-danger)]">
            ⚠ {error}
          </p>
        ) : null}

        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => router.push("/sigeda/respaldos")}
          >
            Cancelar
          </Button>
          <Button type="submit" isLoading={enviando}>
            Guardar prueba
          </Button>
        </div>
      </form>
    </main>
  );
}
