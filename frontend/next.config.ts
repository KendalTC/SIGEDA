import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  // Permite acceder al servidor de desarrollo por el nombre de los
  // servicios de Docker Compose (nginx, frontend), no solo
  // localhost: lo necesita Playwright corriendo en otro contenedor
  // para tomar capturas reales de evidencia (docs/evidencia/).
  allowedDevOrigins: ["nginx", "frontend", "localhost", "127.0.0.1"],
};

export default nextConfig;
