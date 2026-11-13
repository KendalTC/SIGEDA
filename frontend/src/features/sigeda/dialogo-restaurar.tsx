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
import { restaurarRespaldo } from "./api";
import {
  formatearFechaHora,
  formatearTamano,
  textoTipoRespaldo,
} from "./respaldos-estado";
import type { Respaldo } from "./types";

export type DialogoRestaurarHandle = {
  abrir: () => void;
};

type DialogoRestaurarProps = {
  readonly token: string;
  /** Solo los respaldos con estado COMPLETO se pueden restaurar. */
  readonly respaldosCompletos: Respaldo[];
  readonly onRestaurado: () => void;
};

const PALABRA_CONFIRMACION = "RESTAURAR";

/**
 * D-05 "Restaurar un respaldo" (RF-16). Los 4 campos van en el orden
 * exacto de la ficha: respaldo a elegir, clave de cifrado (escrita a
 * mano, nunca autocompletada), contraseña de la cuenta Administración
 * (se valida contra esa cuenta sin importar la sesión activa — excepción
 * propuesta a RN-09) y la palabra "RESTAURAR" literal. El botón se
 * deshabilita hasta completar los tres campos de confirmación.
 *
 * Es un `<form>` real a propósito (hallazgo H-01): con los tres campos
 * completos, Enter debe enviar igual que el botón.
 *
 * IMPORTANTE: esta operación reemplaza la base de datos y el almacén de
 * documentos completos por los del respaldo elegido. No se prueba de
 * verdad contra el entorno de desarrollo compartido.
 */
export const DialogoRestaurar = forwardRef<
  DialogoRestaurarHandle,
  DialogoRestaurarProps
>(function DialogoRestaurar({ token, respaldosCompletos, onRestaurado }, ref) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  const [idRespaldo, setIdRespaldo] = useState<number | "">("");
  const [claveCifrado, setClaveCifrado] = useState("");
  const [contrasenaAdministracion, setContrasenaAdministracion] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  function limpiar() {
    setIdRespaldo(respaldosCompletos[0]?.id_respaldo ?? "");
    setClaveCifrado("");
    setContrasenaAdministracion("");
    setConfirmacion("");
    setError(null);
    setEnviando(false);
  }

  useImperativeHandle(ref, () => ({
    abrir() {
      limpiar();
      dialogRef.current?.showModal();
    },
  }));

  // Lógica de validación literal de la ficha: habilita el botón solo si
  // hay un respaldo elegido, la clave y la contraseña no están vacías
  // (sin espacios) y la confirmación es EXACTAMENTE "RESTAURAR".
  const listoParaRestaurar =
    idRespaldo !== "" &&
    claveCifrado.trim() !== "" &&
    contrasenaAdministracion.trim() !== "" &&
    confirmacion === PALABRA_CONFIRMACION;

  async function manejarEnvio(evento: FormEvent) {
    evento.preventDefault();

    if (!listoParaRestaurar) return;

    setEnviando(true);
    setError(null);

    try {
      await restaurarRespaldo(token, idRespaldo, {
        clave_cifrado: claveCifrado,
        contrasena_administracion: contrasenaAdministracion,
        confirmacion,
      });

      dialogRef.current?.close();
      onRestaurado();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible restaurar el respaldo.",
      );
    } finally {
      setEnviando(false);
    }
  }

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby="d05-titulo"
      className="m-auto w-[min(560px,calc(100vw-32px))] rounded-[var(--radius-xl)] border border-[var(--color-border)] bg-background p-6 text-foreground shadow-[var(--shadow-lg)] backdrop:bg-[rgb(15_23_42_/_45%)]"
    >
      <form onSubmit={manejarEnvio} className="flex flex-col gap-4">
        <h2 id="d05-titulo">Restaurar un respaldo</h2>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="d05-respaldo">Respaldo (obligatorio)</label>
          <Select
            id="d05-respaldo"
            value={idRespaldo}
            onChange={(e) =>
              setIdRespaldo(e.target.value ? Number(e.target.value) : "")
            }
          >
            {respaldosCompletos.length === 0 ? (
              <option value="">No hay respaldos completos disponibles</option>
            ) : null}
            {respaldosCompletos.map((respaldo) => (
              <option key={respaldo.id_respaldo} value={respaldo.id_respaldo}>
                {formatearFechaHora(respaldo.fecha_hora)} ·{" "}
                {textoTipoRespaldo(respaldo.tipo)} ·{" "}
                {formatearTamano(respaldo.tamano_bytes)}
              </option>
            ))}
          </Select>
        </div>

        <div className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]">
          <p className="font-semibold">
            Se reemplazarán TODOS los abonados y documentos actuales por los
            del respaldo elegido.
          </p>
          <p>
            Lo que se haya hecho después de esa fecha se perderá. Antes de
            restaurar, SIGEDA hace un respaldo del estado actual. La bitácora
            no se borra.
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="d05-clave-cifrado">Clave de cifrado (obligatorio)</label>
          <Input
            id="d05-clave-cifrado"
            type="password"
            autoComplete="off"
            placeholder="Copia física o digital de la clave"
            value={claveCifrado}
            onChange={(e) => {
              setClaveCifrado(e.target.value);
              setError(null);
            }}
          />
        </div>

        <p className="font-semibold">
          Autorización de la Administración (usuario administracion):
        </p>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="d05-contrasena-administracion">
            Contraseña de la Administración (obligatorio)
          </label>
          <Input
            id="d05-contrasena-administracion"
            type="password"
            autoComplete="off"
            value={contrasenaAdministracion}
            onChange={(e) => {
              setContrasenaAdministracion(e.target.value);
              setError(null);
            }}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="d05-confirmacion">
            Escriba RESTAURAR para confirmar (obligatorio)
          </label>
          <Input
            id="d05-confirmacion"
            autoComplete="off"
            value={confirmacion}
            onChange={(e) => {
              setConfirmacion(e.target.value);
              setError(null);
            }}
          />
        </div>

        {error ? (
          <p role="alert" className="text-sm text-[var(--color-danger)]">
            ⚠ {error}
          </p>
        ) : null}

        <p
          role="status"
          className={
            listoParaRestaurar
              ? "text-sm text-[var(--color-success)]"
              : "text-sm text-[var(--color-text-muted)]"
          }
        >
          {listoParaRestaurar
            ? "Listo: puede restaurar."
            : "El botón se activa al completar la clave, la autorización y la palabra RESTAURAR."}
        </p>

        <div className="flex justify-end gap-3">
          <Button
            type="button"
            variant="secondary"
            onClick={() => dialogRef.current?.close()}
          >
            Cancelar
          </Button>
          <Button
            type="submit"
            variant="danger"
            disabled={!listoParaRestaurar}
            isLoading={enviando}
            loadingText="Restaurando…"
          >
            Restaurar
          </Button>
        </div>
      </form>
    </dialog>
  );
});
