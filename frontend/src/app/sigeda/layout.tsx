import { SigedaAuthProvider } from "@/features/sigeda/auth-context";

import "./sigeda.css";

export default function SigedaLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <div className="sigeda-tema">
      <SigedaAuthProvider>{children}</SigedaAuthProvider>
    </div>
  );
}
