const FIRMA_PDF = [0x25, 0x50, 0x44, 0x46, 0x2d]; // %PDF-
const FIRMA_PNG = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];

const TAMANO_MAXIMO_BYTES = 10 * 1024 * 1024;

function coincideFirma(bytes: Uint8Array, firma: number[]): boolean {
  return firma.every((valor, indice) => bytes[indice] === valor);
}

function extension(nombreArchivo: string): string {
  const partes = nombreArchivo.split(".");
  return partes.length > 1 ? partes[partes.length - 1].toUpperCase() : "?";
}

/**
 * Valida en el navegador, igual que el backend (ControladorDocumentos
 * .validarArchivo): revisa el contenido real del archivo, no solo la
 * extensión, para dar el mensaje de error de inmediato, al elegir el
 * archivo (ficha PAN-05, acción "Elegir archivos").
 */
export async function validarArchivoEnNavegador(
  archivo: File,
): Promise<string | null> {
  if (archivo.size > TAMANO_MAXIMO_BYTES) {
    const tamanoMb = (archivo.size / (1024 * 1024)).toFixed(1).replace(".", ",");

    return `Pesa ${tamanoMb} MB y el máximo es 10 MB. Escanéelo a menor resolución o divídalo en dos archivos.`;
  }

  const cabecera = new Uint8Array(await archivo.slice(0, 8).arrayBuffer());

  if (coincideFirma(cabecera, FIRMA_PDF) || coincideFirma(cabecera, FIRMA_PNG)) {
    return null;
  }

  return `Es un archivo ${extension(archivo.name)}. Solo se aceptan PDF o PNG: conviértalo con la fotocopiadora o elija otro archivo.`;
}

export function hoyComoFechaIso(): string {
  const ahora = new Date();
  const mes = String(ahora.getMonth() + 1).padStart(2, "0");
  const dia = String(ahora.getDate()).padStart(2, "0");
  return `${ahora.getFullYear()}-${mes}-${dia}`;
}
