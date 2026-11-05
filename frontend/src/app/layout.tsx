import type { Metadata } from "next";

import { AuthProvider } from "@/features/auth/auth-context";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "SIGEDA",
    template: "%s | SIGEDA",
  },
  description:
    "Sistema de Gestión Documental del Acueducto Bodegas y Pilas.",
  applicationName: "SIGEDA",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}