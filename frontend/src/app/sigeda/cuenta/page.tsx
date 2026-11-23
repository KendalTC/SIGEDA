"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  asignarContrasenaTemporal,
  cambiarContrasena,
  obtenerOtraCuenta,
} from "@/features/sigeda/api";
import { useSigedaAuth } from "@/features/sigeda/auth-context";
import { perfilDisplay, type ContrasenaTemporalGenerada, type OtraCuenta } from "@/features/sigeda/types";

const MENSAJE_CONTRASENAS_DISTINTAS =
  "Las contraseñas no coinciden. Vuelva a escribirlas iguales.";

export default function MiCuentaPage() {
  const router = useRouter();
  const { sesion, cargando: cargandoSesion, establecerSesion } =
    useSigedaAuth();

  // Panel "Cambiar mi contraseña".
  const [contrasenaActual, setContrasenaActual] = useState("");
  const [contrasenaNueva, setContrasenaNueva] = useState("");
  const [repetirContrasena, setRepetirContrasena] = useState("");
  const [errorCambio, setErrorCambio] = useState<string | null>(null);
  const [errorCampoNueva, setErrorCampoNueva] = useState<string | null>(null);
  const [exitoCambio, setExitoCambio] = useState<string | null>(null);
  const [guardandoCambio, setGuardandoCambio] = useState(false);

  // Panel "Contraseña temporal para la otra cuenta".
  const [otraCuenta, setOtraCuenta] = useState<OtraCuenta | null>(null);
  const [errorOtraCuenta, setErrorOtraCuenta] = useState<string | null>(null);
  const [generando, setGenerando] = useState(false);
  const [temporalGenerada, setTemporalGenerada] =
    useState<ContrasenaTemporalGenerada | null>(null);
  const [errorGenerar, setErrorGenerar] = useState<string | null>(null);

  useEffect(() => {
    if (cargandoSesion) return;

    if (!sesion) {
      router.push("/sigeda/login");
      return;
    }

    obtenerOtraCuenta(sesion.token)
      .then(setOtraCuenta)
      .catch((err) =>
        setErrorOtraCuenta(
          err instanceof Error
            ? err.message
            : "No fue posible consultar la otra cuenta.",
        ),
      );
  }, [cargandoSesion, sesion, router]);

  async function manejarCambioContrasena(evento: FormEvent) {
    evento.preventDefault();

    if (!sesion) return;

    setErrorCambio(null);
    setErrorCampoNueva(null);
    setExitoCambio(null);

    if (contrasenaNueva.length < 8) {
      setErrorCambio(
        `La contraseña nueva tiene ${contrasenaNueva.length} caracteres y ` +
          "el mínimo es 8. Escriba una contraseña de al menos 8 caracteres.",
      );
      setErrorCampoNueva(
        `⚠ Tiene ${contrasenaNueva.length} caracteres; el mínimo es 8.`,
      );
      return;
    }

    if (contrasenaNueva !== repetirContrasena) {
      setErrorCambio(MENSAJE_CONTRASENAS_DISTINTAS);
      return;
    }

    setGuardandoCambio(true);

    try {
      const respuesta = await cambiarContrasena(sesion.token, {
        nueva_contrasena: contrasenaNueva,
        contrasena_actual: contrasenaActual,
        repetir_contrasena: repetirContrasena,
      });

      establecerSesion({
        token: respuesta.token,
        cuenta: { ...sesion.cuenta, es_contrasena_temporal: false },
      });

      setContrasenaActual("");
      setContrasenaNueva("");
      setRepetirContrasena("");
      setExitoCambio("Contraseña actualizada.");
    } catch (err) {
      setErrorCambio(
        err instanceof Error
          ? err.message
          : "No fue posible cambiar la contraseña.",
      );
    } finally {
      setGuardandoCambio(false);
    }
  }

  async function manejarGenerarTemporal(evento: FormEvent) {
    evento.preventDefault();

    if (!sesion) return;

    setErrorGenerar(null);
    setGenerando(true);

    try {
      const respuesta = await asignarContrasenaTemporal(sesion.token);
      setTemporalGenerada(respuesta);
    } catch (err) {
      setErrorGenerar(
        err instanceof Error
          ? err.message
          : "No fue posible generar la contraseña temporal.",
      );
    } finally {
      setGenerando(false);
    }
  }

  if (cargandoSesion || !sesion) {
    return <p className="p-6">Cargando…</p>;
  }

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-8 p-8">
      <div>
        <h1>Mi cuenta</h1>
        <p className="text-[var(--color-text-muted)]">
          Sesión de la {perfilDisplay(sesion.cuenta.perfil)} (usuario{" "}
          {sesion.cuenta.usuario}). Las dos cuentas tienen los mismos
          permisos, salvo restaurar respaldos, que requiere la autorización
          de la Administración.
        </p>
      </div>

      <section className="flex flex-col gap-4">
        <h2>Cambiar mi contraseña</h2>

        <form
          onSubmit={manejarCambioContrasena}
          className="flex flex-col gap-4"
          noValidate
        >
          <div className="flex flex-col gap-1.5">
            <label htmlFor="contrasena-actual">Contraseña actual</label>
            <Input
              id="contrasena-actual"
              name="contrasena-actual"
              type="password"
              autoComplete="current-password"
              value={contrasenaActual}
              onChange={(e) => setContrasenaActual(e.target.value)}
              required
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="contrasena-nueva">Contraseña nueva</label>
            <Input
              id="contrasena-nueva"
              name="contrasena-nueva"
              type="password"
              autoComplete="new-password"
              value={contrasenaNueva}
              onChange={(e) => {
                setContrasenaNueva(e.target.value);
                setErrorCampoNueva(null);
              }}
              hasError={Boolean(errorCampoNueva)}
              required
            />
            <p className="text-sm text-[var(--color-text-muted)]">
              Mínimo 8 caracteres.
            </p>
            {errorCampoNueva ? (
              <p className="text-sm text-[var(--color-danger)]">
                {errorCampoNueva}
              </p>
            ) : null}
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="repetir-contrasena">
              Repita la contraseña nueva
            </label>
            <Input
              id="repetir-contrasena"
              name="repetir-contrasena"
              type="password"
              autoComplete="new-password"
              value={repetirContrasena}
              onChange={(e) => setRepetirContrasena(e.target.value)}
              required
            />
          </div>

          {errorCambio ? (
            <div
              role="alert"
              className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
            >
              {errorCambio}
            </div>
          ) : null}

          {exitoCambio ? (
            <div
              role="status"
              className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
            >
              {exitoCambio}
            </div>
          ) : null}

          <Button
            type="submit"
            isLoading={guardandoCambio}
            loadingText="Cambiando…"
          >
            Cambiar contraseña
          </Button>
        </form>
      </section>

      <section className="flex flex-col gap-4">
        <h2>Contraseña temporal para la otra cuenta</h2>

        {errorOtraCuenta ? (
          <div
            role="alert"
            className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
          >
            {errorOtraCuenta}
          </div>
        ) : otraCuenta ? (
          <form
            onSubmit={manejarGenerarTemporal}
            className="flex flex-col gap-4"
            noValidate
          >
            <p className="text-[var(--color-text-muted)]">
              Use esta opción si la {otraCuenta.perfil_display} olvidó su
              contraseña o su cuenta quedó bloqueada.
            </p>
            <p>
              Cuenta: {otraCuenta.usuario} ({otraCuenta.perfil_display})
            </p>

            {errorGenerar ? (
              <div
                role="alert"
                className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
              >
                {errorGenerar}
              </div>
            ) : null}

            {temporalGenerada ? (
              <div
                role="status"
                className="rounded-[var(--radius-md)] border border-[var(--color-success)] bg-[var(--color-success-soft)] px-4 py-3 text-[var(--color-success)]"
              >
                <p>
                  Contraseña temporal de «{temporalGenerada.usuario}»:{" "}
                  {temporalGenerada.contrasena_temporal}
                </p>
                <p>
                  Désela en persona. Solo se muestra esta vez y deberá
                  cambiarla al entrar. Quedó en la bitácora.
                </p>
              </div>
            ) : null}

            <Button
              type="submit"
              isLoading={generando}
              loadingText="Generando…"
            >
              Generar contraseña temporal
            </Button>
          </form>
        ) : (
          <p className="text-[var(--color-text-muted)]">Cargando…</p>
        )}
      </section>
    </main>
  );
}
