export type Perfil = "SECRETARIA" | "ADMINISTRADORA";

export type Cuenta = {
  id_cuenta: number;
  usuario: string;
  perfil: Perfil;
  es_contrasena_temporal: boolean;
};

/** CLAUDE.md, sección 5: en la interfaz, SECRETARIA y ADMINISTRADORA
 * se muestran como «Secretaría» y «Administración». */
export function perfilDisplay(perfil: Perfil): string {
  return perfil === "SECRETARIA" ? "Secretaría" : "Administración";
}

export type OtraCuenta = {
  usuario: string;
  perfil: Perfil;
  perfil_display: string;
};

export type ContrasenaTemporalGenerada = {
  usuario: string;
  contrasena_temporal: string;
};

export type Persona = {
  id_persona: number;
  nombre: string;
  tipo_identificacion: string | null;
  identificacion: string | null;
};

export type VinculoVigente = {
  persona: Persona;
  rol: "TITULAR" | "COTITULAR" | "APODERADA";
  fecha_inicio: string;
  fecha_fin: string | null;
};

/** RF-14 (Q3): indicador breve para PAN-04; el detalle a fondo es PAN-07
 * (Incremento 4), que todavía no existe. */
export type Completitud = {
  completo: boolean;
  faltantes: string[];
};

export type Abonado = {
  id_abonado: number;
  numero_paja: string;
  sector: string | null;
  tipo_abonado: "PERSONA_FISICA" | "PERSONA_JURIDICA" | "PENDIENTE";
  estado: "ACTIVO" | "DE_BAJA";
  fecha_baja: string | null;
  titular_vigente: Persona | null;
  completitud: Completitud;
};

/** RF-03/RN-12: titulares anteriores (vínculo TITULAR cerrado). No
 * aparecen en búsquedas (RN-12), pero sí en el historial del propio
 * expediente ya abierto. */
export type TitularAnterior = {
  persona: Persona;
  fecha_inicio: string;
  fecha_fin: string;
};

export type VersionDocumento = {
  numero_version: number;
  nombre_original: string;
  formato: "PDF" | "PNG";
  tamano_bytes: number;
  fecha_documento: string;
  fecha_carga: string;
  hash_sha256: string;
};

export type DocumentoExpediente = {
  id_documento: number;
  tipo_documento: string;
  prioridad: number;
  nombre_identificador: string | null;
  persona: string | null;
  /** RF-03/RN-12: el documento lo aportó quien era titular cuando se
   * cargó, pero ya no es el titular vigente (ficha PAN-04: etiqueta
   * "titular anterior" junto al nombre). */
  aportante_titular_anterior: boolean;
  estado: "VIGENTE" | "ANULADO";
  motivo_anulacion: string | null;
  fecha_anulacion: string | null;
  version_vigente: VersionDocumento | null;
  numero_versiones: number;
};

export type Expediente = {
  abonado: Abonado;
  personas_vigentes: VinculoVigente[];
  documentos: DocumentoExpediente[];
  historial_titulares: TitularAnterior[];
};

/** RF-11: filtros en vivo del expediente (PAN-04), sobre el GET ya
 * existente. Todos opcionales: sin ninguno se ve el expediente completo
 * ordenado por RN-05. */
export type FiltrosExpediente = {
  id_tipo_documento?: number;
  nombre_identificador?: string;
  fecha_desde?: string;
  fecha_hasta?: string;
  mostrar_anulados?: boolean;
};

export type TipoDocumentoCatalogo = {
  id_tipo_documento: number;
  nombre: string;
  prioridad: number;
};

export type SectorCatalogo = {
  id_sector: number;
  nombre: string;
};

export type ResultadoBusqueda = {
  numero_paja: string;
  titular_vigente: string | null;
  identificacion_parcial: string | null;
  sector: string | null;
  tipo_abonado: "PERSONA_FISICA" | "PERSONA_JURIDICA" | "PENDIENTE";
  estado: "ACTIVO" | "DE_BAJA";
};

export type RespuestaBusqueda = {
  total: number;
  mostrados: number;
  tiempo_segundos: number;
  resultados: ResultadoBusqueda[];
};

export type CriteriosBusqueda = {
  numero_paja?: string;
  nombre?: string;
  identificacion?: string;
  id_sector?: number;
  incluir_baja: boolean;
};

export type MetadatoArchivo = {
  es_nueva_version: boolean;
  id_documento?: number;
  id_tipo_documento?: number;
  id_persona?: number | null;
  nombre_identificador?: string;
  fecha_documento: string;
};

export type ErrorArchivo = {
  indice: number;
  archivo: string;
  errores: Record<string, string>;
};

export type CargaDocumentosExito = {
  detail: string;
  documentos: Array<{
    id_documento: number;
    tipo_documento: string;
    numero_version: number;
    fecha_documento: string;
  }>;
};

export type CargaDocumentosError = {
  detail: string;
  errores: ErrorArchivo[];
};
