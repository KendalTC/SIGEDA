"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/errors";
import { cambiarContrasena } from "@/features/sigeda/api";
import { useSigedaAuth, type Sesion } from "@/features/sigeda/auth-context";

const MENSAJE_CONTRASENAS_DISTINTAS =
  "Las contraseñas no coinciden. Vuelva a escribirlas iguales.";

/**
 * Pantalla partida de PAN-01 (rediseño del 23/11/2026, aprobado con
 * Kendal sobre prototipos): un panel de marca a la izquierda (se
 * oculta en pantallas angostas) y la tarjeta del formulario a la
 * derecha. Comparte las manchas animadas (`.sigeda-orb`) y la entrada
 * suave (`.sigeda-aparecer`) con la barra lateral del resto de la
 * aplicación, para que el cambio de una pantalla a otra se sienta
 * continuo.
 */
function PantallaAutenticacion({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-dvh w-full flex-wrap">
      <aside
        aria-label="Acueducto Bodegas y Pilas, SIGEDA"
        className="relative flex min-h-dvh min-w-[340px] flex-[1_1_440px] flex-col items-center justify-center overflow-hidden p-[60px] text-white max-[780px]:hidden"
        style={{
          background:
            "linear-gradient(155deg, var(--color-primary) 0%, var(--color-primary-active) 100%)",
        }}
      >
        <span
          className="sigeda-orb"
          style={{
            width: 420,
            height: 420,
            top: -130,
            right: -110,
            opacity: 0.65,
            background: "radial-gradient(circle at 30% 30%, #55AEDC, transparent 70%)",
            animationDuration: "17s",
          }}
        />
        <span
          className="sigeda-orb"
          style={{
            width: 320,
            height: 320,
            bottom: -110,
            left: -90,
            opacity: 0.55,
            background: "radial-gradient(circle at 50% 50%, #7DC6EA, transparent 70%)",
            animationDuration: "21s",
            animationDelay: "-5s",
          }}
        />
        <span
          className="sigeda-orb"
          style={{
            width: 220,
            height: 220,
            top: "38%",
            left: "8%",
            opacity: 0.1,
            background: "radial-gradient(circle at 50% 50%, #ffffff, transparent 70%)",
            animationDuration: "13s",
            animationDelay: "-2s",
          }}
        />

        <div
          className="sigeda-aparecer relative flex flex-col items-center gap-[18px] text-center"
          style={{ fontFamily: "var(--font-brand)" }}
        >
          <span className="text-[12.5px] font-semibold uppercase tracking-[0.16em] opacity-70">
            Acueducto Bodegas y Pilas
          </span>
          <span className="text-[68px] font-semibold leading-none tracking-[-0.025em]">
            SIGEDA
          </span>
          <span className="mt-1 h-[3px] w-10 rounded-full bg-white/40" />
        </div>
      </aside>

      <div className="relative flex min-w-[320px] flex-[2_1_480px] items-center justify-center overflow-hidden p-6 sm:p-10">
        <span
          className="sigeda-orb"
          style={{
            width: 360,
            height: 360,
            top: -120,
            right: -80,
            opacity: 0.5,
            background: "radial-gradient(circle at 50% 50%, #BFE0F0, transparent 70%)",
            filter: "blur(60px)",
            animationDuration: "19s",
          }}
        />
        <span
          className="sigeda-orb"
          style={{
            width: 260,
            height: 260,
            bottom: -80,
            left: "10%",
            opacity: 0.4,
            background: "radial-gradient(circle at 50% 50%, #CFE8D9, transparent 70%)",
            filter: "blur(60px)",
            animationDuration: "23s",
            animationDelay: "-6s",
          }}
        />
        {children}
      </div>
    </div>
  );
}

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
      <PantallaAutenticacion>
      <main className="sigeda-aparecer relative w-full max-w-[400px] rounded-[var(--radius-lg)] border border-[var(--color-border-soft)] bg-surface p-10 shadow-[var(--shadow-lg)]">
        <h2 className="mt-0">Cree su contraseña</h2>
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
      </PantallaAutenticacion>
    );
  }

  return (
    <PantallaAutenticacion>
    <main className="sigeda-aparecer relative w-full max-w-[400px] rounded-[var(--radius-lg)] border border-[var(--color-border-soft)] bg-surface p-10 shadow-[var(--shadow-lg)]">
      <div className="mb-2">
        <h1 className="mt-0 mb-1">Iniciar sesión</h1>
        <p className="text-[var(--color-text-muted)]">
          Escriba su usuario y contraseña.
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
    </PantallaAutenticacion>
  );
}
