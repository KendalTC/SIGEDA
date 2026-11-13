import type { TipoIdentificacion } from "./types";

/** CLAUDE.md sección 5, dominio `persona.tipo_identificacion`; orden y
 * etiquetas tomadas de la ficha PAN-06 ("Tipo de identificación"). */
export const OPCIONES_TIPO_IDENTIFICACION: Array<{
  valor: TipoIdentificacion;
  etiqueta: string;
}> = [
  { valor: "CEDULA_FISICA", etiqueta: "Cédula física" },
  { valor: "CEDULA_JURIDICA", etiqueta: "Cédula jurídica" },
  { valor: "DIMEX", etiqueta: "DIMEX" },
  { valor: "PASAPORTE", etiqueta: "Pasaporte" },
];

/** Nota fija bajo "Número de identificación" en la ficha PAN-06, citada
 * literal. SUPUESTO confirmado en el Anexo de pendientes: cédula
 * jurídica de 10 dígitos. */
export const AYUDA_FORMATOS_IDENTIFICACION =
  "Cédula física: 9 dígitos (0-0000-0000) · jurídica: 10 (3-000-000000) · " +
  "DIMEX: 11 o 12 · pasaporte: letras y números.";
