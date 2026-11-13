"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  crearRespaldoManual,
  listarPruebasRestauracion,
  obtenerRespaldos,
} from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import {
  DialogoRestaurar,
  type DialogoRestaurarHandle,
} from "@/features/sigeda/dialogo-restaurar";
import {
  calcularResumen,
  formatearFechaHora,
  formatearTamano,
  textoCopiaDestino,
  textoEstadoRespaldo,
  textoTipoRespaldo,
} from "@/features/sigeda/respaldos-estado";
import type {
  PruebaRestauracion,
  Respaldo,
  RespuestaRespaldos,
} from "@/features/sigeda/types";

function badgeEstado(estado: Respaldo["estado"]) {
  const estilos: Record<Respaldo["estado"], string> = {
    COMPLETO:
      "border-[var(--color-success)] bg-[var(--color-success-soft)] text-[var(--color-success)]",
    PENDIENTE:
      "border-[var(--color-warning)] bg-[var(--color-warning-soft)] text-[var(--color-warning)]",
    FALLIDO:
      "border-[var(--color-danger)] bg-[var(--color-danger-soft)] text-[var(--color-danger)]",
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border px-3 py-0.5 text-sm font-semibold ${estilos[estado]}`}
    >
      {textoEstadoRespaldo(estado)}
    </span>
  );
}

/**
 * PAN-08 "Respaldo y restauración" (RF-16). Los textos de cada estado
 * (hecho, pendiente, error/fallido, vacío) son literales de la ficha
 * del Prototipos v1.1; donde la ficha usaba una fecha de ejemplo fija,
 * acá se interpola la fecha real del respaldo correspondiente.
 */
export default function RespaldosPage() {
  const router = useRouter();
  const { sesion, cargando: cargandoSesion } = useSigedaAuth();

  const [datos, setDatos] = useState<RespuestaRespaldos | null>(null);
  const [pruebas, setPruebas] = useState<PruebaRestauracion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mensajeAccion, setMensajeAccion] = useState<string | null>(null);
  const [respaldando, setRespaldando] = useState(false);
  const primeraCargaHecha = useRef(false);

  const cargar = useCallback(async () => {
    if (!sesion) return;

    if (!primeraCargaHecha.current) setCargando(true);
    setError(null);

    try {
      const respuesta = await obtenerRespaldos(sesion.token);
      setDatos(respuesta);
      primeraCargaHecha.current = true;
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "No fue posible consultar los respaldos.",
      );
    } finally {
      setCargando(false);
    }

    // Las pruebas de restauración no son indispensables para pintar
    // PAN-08: si fallan, se muestra "Pendiente" en vez de tumbar la
    // pantalla completa.
    try {
      setPruebas(await listarPruebasRestauracion(sesion.token));
    } catch {
      setPruebas([]);
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

  async function manejarRespaldarAhora() {
    if (!sesion) return;

    setRespaldando(true);
    setError(null);
    setMensajeAccion(null);

    try {
      await crearRespaldoManual(sesion.token);
      setMensajeAccion("Respaldo creado.");
      await cargar();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible crear el respaldo.",
      );
    } finally {
      setRespaldando(false);
    }
  }

  const dialogoRestaurarRef = useRef<DialogoRestaurarHandle>(null);

  if (cargandoSesion || cargando) {
    return <p className="p-6">Cargando…</p>;
  }

  if (error && !datos) {
    return (
      <main className="mx-auto flex max-w-5xl flex-col gap-4 p-6">
        <h1>Respaldo y restauración</h1>
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

  if (!datos) return null;

  const { respaldos } = datos;
  const { estadoGlobal, ultimoCompleto, ultimoIntento } = calcularResumen(
    respaldos,
    datos.resumen,
  );
  const respaldosCompletos = respaldos.filter((r) => r.estado === "COMPLETO");
  const copiaDisco = (respaldo: Respaldo) =>
    respaldo.copias.find((c) => c.destino === "DISCO_EXTERNO");
  const copiaOneDrive = (respaldo: Respaldo) =>
    respaldo.copias.find((c) => c.destino === "ONEDRIVE");
  const ultimaPrueba = pruebas[0] ?? null;
  const archivosEnCuarentena = datos.resumen?.archivos_en_cuarentena;

  // --- Estado "vacío": todavía no hay ningún respaldo -----------------
  if (estadoGlobal === "sin_respaldos") {
    return (
      <main className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
        <h1>Respaldo y restauración</h1>

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

        <div
          role="status"
          className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]"
        >
          <p className="font-semibold">Aún no hay ningún respaldo.</p>
          <p>
            Conecte el disco externo y presione «Respaldar ahora». Después
            SIGEDA respaldará solo todos los días.
          </p>
        </div>

        <div>
          <Button isLoading={respaldando} loadingText="Respaldando…" onClick={manejarRespaldarAhora}>
            Respaldar ahora
          </Button>
        </div>
      </main>
    );
  }

  // --- Estados "hecho" / "pendiente" / "fallido" (con panel completo) -
  let panelEstado: React.ReactNode;

  if (estadoGlobal === "completo" && ultimoIntento) {
    panelEstado = (
      <div
        role="status"
        className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
      >
        <p className="font-semibold">
          Respaldo completo y verificado: {formatearFechaHora(ultimoIntento.fecha_hora)}.
        </p>
        <p>
          La copia en el disco externo coincide con el original. Ya puede
          desconectar el disco al cerrar la jornada.
        </p>
      </div>
    );
  } else if (estadoGlobal === "fallido" && ultimoIntento) {
    panelEstado = (
      <div
        role="alert"
        className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
      >
        <p className="font-semibold">
          El respaldo de hoy a las{" "}
          {formatearFechaHora(ultimoIntento.fecha_hora).slice(-5)} falló: la
          copia en el disco externo no coincide con el original.
        </p>
        <p>
          No se usará esa copia. Revise que el disco tenga espacio y no esté
          dañado, y presione «Respaldar ahora». Si vuelve a fallar, cambie de
          disco.
        </p>
      </div>
    );
  } else if (ultimoIntento) {
    panelEstado = (
      <div
        role="status"
        className="rounded-[var(--radius-md)] border border-[var(--color-warning)] bg-[var(--color-warning-soft)] px-4 py-3 text-[var(--color-warning)]"
      >
        <p className="font-semibold">
          El disco externo no está conectado. El respaldo automático de{" "}
          {formatearFechaHora(ultimoIntento.fecha_hora)} quedó pendiente.
        </p>
        <p>
          SIGEDA lo reintenta cada 30 minutos y avisa al iniciar sesión.
          Conecte el disco y presione «Respaldar ahora».
        </p>
      </div>
    );
  }

  return (
    <main className="mx-auto flex max-w-5xl flex-col gap-6 p-6">
      <div className="flex flex-col gap-1">
        <h1>Respaldo y restauración</h1>
        <p>
          SIGEDA hace un respaldo completo y cifrado todos los días. Aquí ve
          si salió bien y puede hacer uno a mano o restaurar.
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

      {panelEstado}

      <div className="grid gap-6 md:grid-cols-2">
        <section
          aria-labelledby="ultimo-completo-titulo"
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4"
        >
          <h2 id="ultimo-completo-titulo" className="mt-0">
            Último respaldo completo
          </h2>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">
            <dt className="text-[var(--color-text-muted)]">Fecha</dt>
            <dd>
              {ultimoCompleto ? formatearFechaHora(ultimoCompleto.fecha_hora) : "—"}
            </dd>
            <dt className="text-[var(--color-text-muted)]">Disco externo</dt>
            <dd>
              {ultimoCompleto
                ? textoCopiaDestino(copiaDisco(ultimoCompleto), "DISCO_EXTERNO")
                : "—"}
            </dd>
            <dt className="text-[var(--color-text-muted)]">OneDrive</dt>
            <dd>
              {ultimoCompleto && copiaOneDrive(ultimoCompleto)
                ? textoCopiaDestino(copiaOneDrive(ultimoCompleto), "ONEDRIVE")
                : "No configurado"}
              {" · "}
              <Link href="/sigeda/respaldos/onedrive" className="text-[var(--color-primary)] underline">
                Configurar
              </Link>
            </dd>
            <dt className="text-[var(--color-text-muted)]">Próximo automático</dt>
            <dd>
              {datos.resumen?.proximo_automatico
                ? formatearFechaHora(datos.resumen.proximo_automatico)
                : "Diario, automático"}
            </dd>
          </dl>
        </section>

        <section
          aria-labelledby="acciones-titulo"
          className="rounded-[var(--radius-md)] border border-[var(--color-border)] p-4"
        >
          <h2 id="acciones-titulo" className="mt-0">
            Acciones
          </h2>
          <div className="flex flex-wrap gap-3">
            <Button
              isLoading={respaldando}
              loadingText="Respaldando…"
              onClick={manejarRespaldarAhora}
            >
              Respaldar ahora
            </Button>
            <Button
              variant="danger"
              disabled={respaldosCompletos.length === 0}
              onClick={() => dialogoRestaurarRef.current?.abrir()}
            >
              Restaurar un respaldo…
            </Button>
          </div>
          <p className="mt-3">
            Restaurar reemplaza los abonados y documentos actuales por los del
            respaldo elegido. La bitácora no se borra: se agrega el registro
            de la restauración. Restaurar requiere la autorización de la
            Administración.
          </p>

          <p className="mt-3 text-sm">
            Prueba de restauración en otra computadora:{" "}
            {ultimaPrueba
              ? `${formatearFechaHora(ultimaPrueba.fecha)} · ${
                  ultimaPrueba.resultado === "EXITOSA"
                    ? "se recuperó todo"
                    : "hubo problemas"
                }`
              : "Pendiente (propuesta: cada 3 meses)"}
            {" · "}
            <Link
              href="/sigeda/respaldos/prueba-restauracion"
              className="text-[var(--color-primary)] underline"
            >
              Registrar prueba
            </Link>
          </p>

          <p className="mt-2 text-sm">
            Archivos en cuarentena: {archivosEnCuarentena ?? "—"}{" "}
            <Link
              href="/sigeda/respaldos/cuarentena"
              className="text-[var(--color-primary)] underline"
            >
              ver lista
            </Link>
          </p>
        </section>
      </div>

      <section aria-labelledby="tabla-respaldos-titulo">
        <h2 id="tabla-respaldos-titulo">
          Últimos respaldos (se conservan 7 diarios y 4 semanales)
        </h2>

        {respaldos.length === 0 ? (
          <p>No hay respaldos registrados todavía.</p>
        ) : (
          <table className="mt-4 w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-[var(--color-border)]">
                <th className="py-2">Fecha y hora</th>
                <th className="py-2">Tipo</th>
                <th className="py-2">Estado</th>
                <th className="py-2">Disco externo</th>
                <th className="py-2">OneDrive</th>
                <th className="py-2">Tamaño</th>
              </tr>
            </thead>
            <tbody>
              {respaldos.map((respaldo) => (
                <tr
                  key={respaldo.id_respaldo}
                  className="border-b border-[var(--color-border-soft)]"
                >
                  <td className="py-2">{formatearFechaHora(respaldo.fecha_hora)}</td>
                  <td className="py-2">{textoTipoRespaldo(respaldo.tipo)}</td>
                  <td className="py-2">{badgeEstado(respaldo.estado)}</td>
                  <td className="py-2">
                    {textoCopiaDestino(copiaDisco(respaldo), "DISCO_EXTERNO")}
                  </td>
                  <td className="py-2">
                    {textoCopiaDestino(copiaOneDrive(respaldo), "ONEDRIVE")}
                  </td>
                  <td className="py-2">{formatearTamano(respaldo.tamano_bytes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {sesion ? (
        <DialogoRestaurar
          ref={dialogoRestaurarRef}
          token={sesion.token}
          respaldosCompletos={respaldosCompletos}
          onRestaurado={() => {
            setMensajeAccion("Respaldo restaurado.");
            cargar();
          }}
        />
      ) : null}
    </main>
  );
}
