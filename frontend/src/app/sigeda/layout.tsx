import { SigedaAuthProvider } from "@/features/sigeda/auth-context";
import { BarraSesion } from "@/features/sigeda/barra-sesion";
import { GuardiaContrasenaTemporal } from "@/features/sigeda/guardia-contrasena-temporal";
import { IdleWatcher } from "@/features/sigeda/idle-watcher";

import "./sigeda.css";

export default function SigedaLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="sigeda-tema">
      <SigedaAuthProvider>
        <GuardiaContrasenaTemporal />
        <BarraSesion />
        <IdleWatcher />
        {children}
      </SigedaAuthProvider>
    </div>
  );
}
