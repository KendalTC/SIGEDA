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
  /** RF-04/RF-21 (ficha PAN-06, estado "importado"): abonado creado por
   * importación de SADA al que todavía le falta tipo, sector e
   * identificación del titular. Opcional en el tipo mientras el backend
   * de la importación se termina de construir en paralelo (Incremento
   * 3b, 13/11/2026). */
  es_importado_pendiente?: boolean;
  fecha_importacion?: string | null;
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

/** RF-02/RF-21/D-04/D-06: resultado del buscador compartido de personas
 * (`GET /api/sigeda/abonados/personas/buscar/?q=`). */
export type PersonaBusqueda = {
  id_persona: number;
  nombre: string;
  tipo_identificacion: string | null;
  identificacion: string | null;
  vinculos_actuales: string[];
};

export type TipoIdentificacion =
  | "CEDULA_FISICA"
  | "CEDULA_JURIDICA"
  | "DIMEX"
  | "PASAPORTE";

/** Datos de una persona que todavía no está registrada; el backend la
 * crea (o, si la identificación ya existe, responde 409 con
 * `PersonaExistenteConflicto` para ofrecer "Usar esa persona"). */
export type DatosPersonaNueva = {
  nombre: string;
  tipo_identificacion: TipoIdentificacion;
  identificacion: string;
};

/** Cualquier endpoint que reciba "una persona" acepta una ya existente
 * por id o los datos para crear una nueva. */
export type PersonaReferencia = { id_persona: number } | DatosPersonaNueva;

/** Cuerpo 409 cuando la identificación escrita ya pertenece a una
 * persona registrada (RF-02/RF-21, ficha PAN-06 estado "persona-existente"). */
export type PersonaExistenteConflicto = {
  id_persona: number;
  nombre: string;
  numero_paja_titular: string | null;
};

export type AltaAbonadoDatos = {
  numero_paja: string;
  id_sector: number;
  tipo_abonado: "PERSONA_FISICA" | "PERSONA_JURIDICA";
  titular: PersonaReferencia;
};

export type ModificarAbonadoDatos = {
  id_sector: number;
  tipo_abonado: "PERSONA_FISICA" | "PERSONA_JURIDICA";
  /** Solo cuando el titular vigente todavía no tiene identificación
   * (abonado importado de SADA, ficha PAN-06 "importado"): el backend
   * la completa en la misma transacción que sector/tipo ("todo o
   * nada"); si el titular ya tenía identificación, los ignora sin
   * error. Ambos juntos o ninguno. */
  tipo_identificacion_titular?: TipoIdentificacion;
  identificacion_titular?: string;
};

export type RolAsociado = "COTITULAR" | "APODERADA";

export type AgregarPersonaDatos = {
  persona: PersonaReferencia;
  rol: RolAsociado;
  fecha_inicio: string;
};

export type CambiarTitularDatos = {
  persona: PersonaReferencia;
  fecha_cambio: string;
};

// --- RF-16 Respaldo y restauración (PAN-08, D-05) -------------------

export type TipoRespaldo = "AUTOMATICO" | "MANUAL";
export type EstadoRespaldo = "COMPLETO" | "PENDIENTE" | "FALLIDO";
export type DestinoCopiaRespaldo = "DISCO_EXTERNO" | "ONEDRIVE";
export type EstadoCopiaRespaldo = "PENDIENTE" | "VERIFICADA" | "FALLIDA";

export type CopiaRespaldo = {
  destino: DestinoCopiaRespaldo;
  estado: EstadoCopiaRespaldo;
  fecha_hora_verificacion: string | null;
};

export type Respaldo = {
  id_respaldo: number;
  fecha_hora: string;
  tipo: TipoRespaldo;
  estado: EstadoRespaldo;
  nombre_paquete: string | null;
  hash_sha256: string | null;
  tamano_bytes: number | null;
  copias: CopiaRespaldo[];
};

/** `GET /api/sigeda/respaldos/`. SUPUESTO de la forma exacta del
 * resumen: el backend se construye en paralelo y puede nombrar estos
 * campos distinto o no mandarlos todos. La insignia y PAN-08 recalculan
 * lo que necesitan a partir de `respaldos` (ver `respaldos-estado.ts`)
 * para no depender de la redacción exacta que mande el backend; lo que
 * sí venga en `resumen` se usa como complemento (p. ej. la ruta de
 * OneDrive, que no se puede derivar de la lista). */
export type ResumenRespaldos = {
  estado_global?: "completo" | "pendiente" | "fallido" | "sin_respaldos";
  disco_externo_configurado?: boolean;
  onedrive_configurado?: boolean;
  onedrive_ruta?: string | null;
  proximo_automatico?: string | null;
  archivos_en_cuarentena?: number;
};

export type RespuestaRespaldos = {
  resumen?: ResumenRespaldos;
  respaldos: Respaldo[];
};

/** `GET /api/sigeda/respaldos/cuarentena/`: archivos físicos en el
 * almacén sin registro en `version_documento` (p. ej. tras un corte de
 * luz durante una carga). SUPUESTO de nombres de campo exactos. */
export type ArchivoCuarentena = {
  nombre_archivo: string;
  tamano_bytes: number;
  fecha_deteccion: string;
  motivo: string;
};

export type ResultadoPruebaRestauracion = "EXITOSA" | "CON_PROBLEMAS";

/** `prueba_restauracion` (tabla propuesta, CLAUDE.md sección 9): registro
 * manual, no una ejecución automática. SUPUESTO de nombres de campo. */
export type PruebaRestauracion = {
  id_prueba_restauracion: number;
  fecha: string;
  id_respaldo: number;
  respaldo_descripcion?: string;
  computadora_usada: string;
  resultado: ResultadoPruebaRestauracion;
  observaciones: string | null;
};

export type DatosPruebaRestauracion = {
  fecha: string;
  id_respaldo: number;
  computadora_usada: string;
  resultado: ResultadoPruebaRestauracion;
  observaciones: string | null;
};

/** D-05: los 4 campos de confirmación, en el orden exacto de la ficha. */
export type DatosRestaurar = {
  clave_cifrado: string;
  contrasena_administracion: string;
  confirmacion: string;
};

// --- RF-04 Importar listado de SADA (PAN-09) -------------------------

/** `POST /api/sigeda/abonados/importar/vista-previa/`: paso "Revisar
 * columnas", solo lee el archivo, no guarda nada todavía. */
export type VistaPreviaImportacion = {
  columnas: string[];
  /** `null` cuando el archivo no tiene filas de datos. */
  ejemplo_fila_2: string[] | null;
  total_filas: number;
};

export type RechazoImportacion = {
  fila: number;
  problema: string;
  que_hacer: string;
};

/** `POST /api/sigeda/abonados/importar/`: paso "Importar" de verdad. */
export type ResultadoImportacion = {
  importados: number;
  omitidos: number;
  rechazados: RechazoImportacion[];
  fecha: string;
};

/** Qué representa cada columna real del archivo en la tabla de mapeo
 * de la ficha (PAN-09, paso 2): el nombre de columna que la usuaria
 * elija para "Número de paja" y para "Nombre del titular" es lo que se
 * manda como `columna_paja`/`columna_nombre`; el resto son "No se usa". */
export type UsoColumnaImportacion = "PAJA" | "NOMBRE" | "NO_USA";
