"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/errors";
import { cambiarContrasena } from "@/features/sigeda/api";
import { useSigedaAuth, type Sesion } from "@/features/sigeda/auth-context";

const MENSAJE_CONTRASENAS_DISTINTAS =
  "Las contraseñas no coinciden. Vuelva a escribirlas iguales.";

export default function SigedaLoginPage() {
  const router = useRouter();
  const { sesion, iniciarSesion, establecerSesion } = useSigedaAuth();

  // Formulario de inicio de sesión (PAN-01).
  const [usuario, setUsuario] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [bloqueada, setBloqueada] = useState(false);
  const [cargando, setCargando] = useState(false);

  // RF-20: entró con una contraseña temporal; hay que crear una propia
  // antes de continuar. `sesionTemporal` guarda el token ya recibido
  // del login (hace falta para autenticar `cambiar-contrasena/`), pero
  // todavía no se marca la sesión de la aplicación como iniciada: eso
  // pasa solo al terminar este paso.
  const [sesionTemporal, setSesionTemporal] = useState<Sesion | null>(null);
  const [contrasenaNueva, setContrasenaNueva] = useState("");
  const [repetirContrasena, setRepetirContrasena] = useState("");
  const [errorNueva, setErrorNueva] = useState<string | null>(null);
  const [guardandoNueva, setGuardandoNueva] = useState(false);

  async function manejarEnvio(evento: FormEvent) {
    evento.preventDefault();

    if (bloqueada) return;

    setError(null);
    setCargando(true);

    try {
      const sesion = await iniciarSesion(usuario, contrasena);

      if (sesion.cuenta.es_contrasena_temporal) {
        setSesionTemporal(sesion);
        return;
      }

      router.push("/sigeda/expedientes/0412");
    } catch (err) {
      if (err instanceof ApiError && err.status === 423) {
        setBloqueada(true);
      }

      setError(
        err instanceof Error ? err.message : "No fue posible iniciar sesión.",
      );
    } finally {
      setCargando(false);
    }
  }

  // Cubre tanto el login recién hecho en esta misma carga de página
  // (`sesionTemporal`) como el caso de recargar PAN-01, o navegar a
  // ella de nuevo, con una sesión que ya quedó marcada como temporal
  // desde antes (la guardia global trae de vuelta aquí en ese caso).
  const sesionPendienteDeContrasena =
    sesionTemporal ??
    (sesion?.cuenta.es_contrasena_temporal ? sesion : null);

  async function manejarEnvioContrasenaNueva(evento: FormEvent) {
    evento.preventDefault();

    if (!sesionPendienteDeContrasena) return;

    if (contrasenaNueva.length < 8) {
      setErrorNueva(
        `La contraseña nueva tiene ${contrasenaNueva.length} caracteres y el mínimo es 8.`,
      );
      return;
    }

    if (contrasenaNueva !== repetirContrasena) {
      setErrorNueva(MENSAJE_CONTRASENAS_DISTINTAS);
      return;
    }

    setErrorNueva(null);
    setGuardandoNueva(true);

    try {
      const respuesta = await cambiarContrasena(
        sesionPendienteDeContrasena.token,
        { nueva_contrasena: contrasenaNueva, repetir_contrasena: repetirContrasena },
      );

      establecerSesion({
        token: respuesta.token,
        cuenta: {
          ...sesionPendienteDeContrasena.cuenta,
          es_contrasena_temporal: false,
        },
      });

      router.push("/sigeda/expedientes/0412");
    } catch (err) {
      setErrorNueva(
        err instanceof Error
          ? err.message
          : "No fue posible guardar la contraseña nueva.",
      );
    } finally {
      setGuardandoNueva(false);
    }
  }

  if (sesionPendienteDeContrasena) {
    return (
      <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 px-4">
        <div>
          <h1>SIGEDA</h1>
          <p className="text-[var(--color-text-muted)]">
            Acueducto Bodegas y Pilas
          </p>
        </div>

        <h2>Cree su contraseña</h2>
        <p className="text-[var(--color-text-muted)]">
          Ingresó con una contraseña temporal asignada desde la otra cuenta.
          Antes de continuar, cree una propia.
        </p>

        <form
          onSubmit={manejarEnvioContrasenaNueva}
          className="flex flex-col gap-4"
          noValidate
        >
          <div className="flex flex-col gap-1.5">
            <label htmlFor="contrasena-nueva">Contraseña nueva</label>
            <Input
              id="contrasena-nueva"
              name="contrasena-nueva"
              type="password"
              autoComplete="new-password"
              value={contrasenaNueva}
              onChange={(e) => setContrasenaNueva(e.target.value)}
              hasError={Boolean(errorNueva)}
              required
            />
            <p className="text-sm text-[var(--color-text-muted)]">
              Mínimo 8 caracteres.
            </p>
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
              hasError={Boolean(errorNueva)}
              required
            />
          </div>

          {errorNueva ? (
            <div
              role="alert"
              className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
            >
              {errorNueva}
            </div>
          ) : null}

          <Button
            type="submit"
            isLoading={guardandoNueva}
            loadingText="Guardando…"
          >
            Guardar y entrar
          </Button>
        </form>
      </main>
    );
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-sm flex-col justify-center gap-6 px-4">
      <div>
        <h1>SIGEDA</h1>
        <p className="text-[var(--color-text-muted)]">
          Acueducto Bodegas y Pilas
        </p>
      </div>

      <form onSubmit={manejarEnvio} className="flex flex-col gap-4" noValidate>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="usuario">Usuario</label>
          <Input
            id="usuario"
            name="usuario"
            autoComplete="username"
            value={usuario}
            onChange={(e) => setUsuario(e.target.value)}
            disabled={bloqueada}
            required
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="contrasena">Contraseña</label>
          <Input
            id="contrasena"
            name="contrasena"
            type="password"
            autoComplete="current-password"
            value={contrasena}
            onChange={(e) => setContrasena(e.target.value)}
            disabled={bloqueada}
            required
          />
        </div>

        {error ? (
          <div
            role="alert"
            className="rounded-[var(--radius-md)] border border-[var(--color-danger)] bg-[var(--color-danger-soft)] px-4 py-3 text-[var(--color-danger)]"
          >
            {error}
          </div>
        ) : null}

        <Button
          type="submit"
          isLoading={cargando}
          loadingText="Entrando…"
          disabled={bloqueada}
        >
          Entrar
        </Button>

        <p className="text-sm text-[var(--color-text-muted)]">
          ¿Olvidó su contraseña? Pida a la otra cuenta (Secretaría o
          Administración) que le asigne una contraseña temporal desde «Mi
          cuenta».
        </p>
      </form>
    </main>
  );
}
