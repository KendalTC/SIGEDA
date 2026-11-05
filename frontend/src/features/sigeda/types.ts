export type Perfil = "SECRETARIA" | "ADMINISTRADORA";

export type Cuenta = {
  id_cuenta: number;
  usuario: string;
  perfil: Perfil;
  es_contrasena_temporal: boolean;
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

export type Abonado = {
  id_abonado: number;
  numero_paja: string;
  sector: string | null;
  tipo_abonado: "PERSONA_FISICA" | "PERSONA_JURIDICA" | "PENDIENTE";
  estado: "ACTIVO" | "DE_BAJA";
  fecha_baja: string | null;
  titular_vigente: Persona | null;
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
  estado: "VIGENTE" | "ANULADO";
  version_vigente: VersionDocumento | null;
  numero_versiones: number;
};

export type Expediente = {
  abonado: Abonado;
  personas_vigentes: VinculoVigente[];
  documentos: DocumentoExpediente[];
};

export type TipoDocumentoCatalogo = {
  id_tipo_documento: number;
  nombre: string;
  prioridad: number;
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
