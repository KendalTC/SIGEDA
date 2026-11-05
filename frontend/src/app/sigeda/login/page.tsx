"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSigedaAuth } from "@/features/sigeda/auth-context";

export default function SigedaLoginPage() {
  const router = useRouter();
  const { iniciarSesion } = useSigedaAuth();
  const [usuario, setUsuario] = useState("");
  const [contrasena, setContrasena] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(false);

  async function manejarEnvio(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setCargando(true);

    try {
      await iniciarSesion(usuario, contrasena);
      router.push("/sigeda/expedientes/0412");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "No fue posible iniciar sesión.",
      );
    } finally {
      setCargando(false);
    }
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

        <Button type="submit" isLoading={cargando} loadingText="Entrando…">
          Entrar
        </Button>
      </form>
    </main>
  );
}
