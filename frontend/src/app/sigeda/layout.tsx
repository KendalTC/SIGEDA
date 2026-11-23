import { SigedaAuthProvider } from "@/features/sigeda/auth-context";
import { BarraLateral } from "@/features/sigeda/barra-lateral";
import { GuardiaContrasenaTemporal } from "@/features/sigeda/guardia-contrasena-temporal";
import { IdleWatcher } from "@/features/sigeda/idle-watcher";

import "./sigeda.css";

export default function SigedaLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="sigeda-tema flex h-dvh overflow-hidden">
      <SigedaAuthProvider>
        <GuardiaContrasenaTemporal />
        <BarraLateral />
        <IdleWatcher />
        <div className="min-w-0 flex-1 overflow-y-auto">{children}</div>
      </SigedaAuthProvider>
    </div>
  );
}
