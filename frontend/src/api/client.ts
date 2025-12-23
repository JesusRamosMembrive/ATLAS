import type {
  FileSummary,
  FileDiffResponse,
  ChangesResponse,
  DocsListResponse,
  ProjectTreeNode,
  SettingsPayload,
  SettingsUpdatePayload,
  StatusPayload,
  SymbolInfo,
  StageStatusPayload,
  StageInitPayload,
  StageInitResponse,
  SuperClaudeInstallResponse,
  BrowseDirectoryResponse,
  ListDirectoriesResponse,
  UMLDiagramResponse,
  LintersReportRecord,
  LintersReportListItem,
  LintersNotificationEntry,
  OllamaStatusPayload,
  OllamaStartPayload,
  OllamaStartResponse,
  OllamaTestPayload,
  OllamaTestResponse,
  OllamaTestErrorDetail,
  OllamaInsightEntry,
  OllamaInsightsResponse,
  OllamaInsightsClearResponse,
  GraphvizOptionsPayload,
  AuditRun,
  AuditRunListResponse,
  AuditRunCreatePayload,
  AuditRunClosePayload,
  AuditEvent,
  AuditEventListResponse,
  AuditEventCreatePayload,
  DiscoverContractsRequest,
  DiscoverContractsResponse,
  SymbolDetailsResponse,
  SymbolSearchResponse,
  SymbolSearchResult,
  CallFlowEntryPointsResponse,
  CallFlowResponse,
} from "./types";
import type {
  SimilarityReport,
  SimilarityAnalyzePayload,
  DuplicationHotspot,
} from "./similarityTypes";
import { useBackendStore } from "../state/useBackendStore";

const sanitizeBaseUrl = (value?: string | null): string | null => {
  if (!value) {
    return null;
  }

  const trimmed = String(value).trim();
  if (!trimmed) {
    return null;
  }

  return trimmed.replace(/\/$/, "");
};

const withApiSuffix = (url: string): string =>
  url.endsWith("/api") ? url : `${url}/api`;

const STATIC_API_BASE = sanitizeBaseUrl(import.meta.env.VITE_API_BASE_URL);
const DEFAULT_DEPLOY_BACKEND = sanitizeBaseUrl(
  import.meta.env.VITE_DEPLOY_BACKEND_URL ?? "http://127.0.0.1:8010"
);

export const resolveBackendBaseUrl = (
  runtimeOverride?: string | null
): string | null => {
  const runtimeUrl = sanitizeBaseUrl(
    runtimeOverride ?? useBackendStore.getState().backendUrl
  );

  const fromWindow =
    typeof window !== "undefined" && window.location?.origin
      ? sanitizeBaseUrl(window.location.origin)
      : null;

  return (
    runtimeUrl ??
    STATIC_API_BASE ??
    DEFAULT_DEPLOY_BACKEND ??
    fromWindow
  );
};

/**
 * Construye la URL completa para una llamada a la API.
 *
 * Args:
 *     path: Ruta relativa del endpoint (debe empezar con '/')
 *
 * Returns:
 *     URL completa combinando base URL, prefijo y path
 *
 * Notes:
 *     - Usa backend_url del store si está configurado
 *     - Fallback a VITE_API_BASE_URL para builds configurados explícitamente
 *     - Fallback adicional a VITE_DEPLOY_BACKEND_URL (default http://0.0.0.0:8010)
 *     - Fallback final a '/api' prefix para desarrollo local con proxy
 *     - Remueve trailing slash de la base URL y añade '/api' automáticamente
 */
const buildUrl = (path: string): string => {
  // Prioridad: Runtime store > Env var > fallback deployment URL > proxy /api
  const baseUrl = resolveBackendBaseUrl();

  if (baseUrl) {
    return `${withApiSuffix(baseUrl)}${path}`;
  }

  // Fallback a comportamiento original (usar proxy local /api)
  return `/api${path}`;
};

/**
 * Realiza una petición HTTP y parsea la respuesta como JSON.
 *
 * Wrapper genérico sobre fetch() que:
 * - Añade headers JSON automáticamente
 * - Maneja errores HTTP con mensajes descriptivos
 * - Parsea respuesta como tipo genérico T
 *
 * Args:
 *     path: Ruta relativa del endpoint
 *     init: Opciones adicionales de fetch (method, body, headers, etc.)
 *
 * Returns:
 *     Promise con datos parseados del tipo T
 *
 * Raises:
 *     Error: Si response.ok es false, con mensaje de status y detalle
 *
 * Notes:
 *     - Content-Type: application/json se añade por defecto
 *     - Headers personalizados pueden sobrescribir defaults
 *     - Error detail extrae response.text() si está disponible
 */
async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildUrl(path), {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(
      `API request failed (${response.status}): ${detail || "Unknown error"}`
    );
  }

  return (await response.json()) as T;
}

async function fetchJsonNullable<T>(
  path: string,
  init?: RequestInit
): Promise<T | null> {
  const response = await fetch(buildUrl(path), {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (response.status === 404) {
    return null;
  }

  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(
      `API request failed (${response.status}): ${detail || "Unknown error"}`
    );
  }

  if (response.status === 204) {
    return null;
  }

  return (await response.json()) as T;
}

export class OllamaTestError extends Error {
  status: number;
  detail?: OllamaTestErrorDetail;

  constructor(message: string, status: number, detail?: OllamaTestErrorDetail) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

/**
 * Obtiene el árbol completo del proyecto.
 *
 * Returns:
 *     Promise con la estructura jerárquica del proyecto (carpetas y archivos)
 *
 * Notes:
 *     - Endpoint: GET /api/tree
 *     - Incluye metadata de archivos y símbolos
 *     - Estructura recursiva ProjectTreeNode
 */
export function getTree(): Promise<ProjectTreeNode> {
  return fetchJson<ProjectTreeNode>("/tree");
}

/**
 * Obtiene el resumen de análisis de un archivo específico.
 *
 * Args:
 *     path: Ruta del archivo (relativa a root del proyecto)
 *
 * Returns:
 *     Promise con símbolos, errores y metadata del archivo
 *
 * Notes:
 *     - Endpoint: GET /api/files/{path}
 *     - Path se encoda automáticamente (espacios, caracteres especiales)
 *     - Incluye funciones, clases, métodos detectados
 */
export function getFileSummary(path: string): Promise<FileSummary> {
  const encoded = encodeURIComponent(path);
  return fetchJson<FileSummary>(`/files/${encoded}`);
}

export function getWorkingTreeDiff(path: string): Promise<FileDiffResponse> {
  const encoded = encodeURIComponent(path);
  return fetchJson<FileDiffResponse>(`/file-diff/${encoded}`);
}

export function getWorkingTreeChanges(): Promise<ChangesResponse> {
  return fetchJson<ChangesResponse>("/changes");
}

export function getDocsListing(): Promise<DocsListResponse> {
  return fetchJson<DocsListResponse>("/docs");
}

/**
 * Busca símbolos en todo el proyecto.
 *
 * Args:
 *     term: Término de búsqueda (nombre de función, clase, método)
 *
 * Returns:
 *     Promise con lista de símbolos que coinciden con el término
 *
 * Notes:
 *     - Endpoint: GET /api/search?q={term}
 *     - Búsqueda parcial (substring matching)
 *     - Resultados incluyen path y ubicación de cada símbolo
 */
export function searchSymbols(term: string): Promise<{ results: SymbolInfo[] }> {
  const params = new URLSearchParams({ q: term });
  return fetchJson(`/search?${params.toString()}`);
}

/**
 * Dispara un rescaneo manual del proyecto.
 *
 * Returns:
 *     Promise con número de archivos procesados
 *
 * Notes:
 *     - Endpoint: POST /api/rescan
 *     - Fuerza actualización completa del índice
 *     - Útil después de cambios masivos (git checkout, etc.)
 */
export function triggerRescan(): Promise<{ files: number }> {
  return fetchJson<{ files: number }>("/rescan", {
    method: "POST",
  });
}

/**
 * Obtiene la URL del stream de eventos SSE.
 *
 * Returns:
 *     URL completa del endpoint de eventos
 *
 * Notes:
 *     - Endpoint: GET /api/events (Server-Sent Events)
 *     - Usado por useEventStream hook
 *     - Mantiene conexión persistente para notificaciones en tiempo real
 */
export function getEventsUrl(): string {
  return buildUrl("/events");
}

export type { ChangeNotification } from "./types";

/**
 * Obtiene la configuración actual del proyecto.
 *
 * Returns:
 *     Promise con settings actuales (root, excludes, docstrings, etc.)
 *
 * Notes:
 *     - Endpoint: GET /api/settings
 *     - Incluye tanto configuración persistente como runtime
 *     - Usado por formulario de configuración
 */
export function getSettings(): Promise<SettingsPayload> {
  return fetchJson<SettingsPayload>("/settings");
}

/**
 * Actualiza la configuración del proyecto.
 *
 * Args:
 *     payload: Objeto con campos a actualizar (parcial)
 *
 * Returns:
 *     Promise con lista de campos actualizados y settings completos
 *
 * Notes:
 *     - Endpoint: PUT /api/settings
 *     - Update parcial: solo enviar campos a modificar
 *     - Algunos cambios requieren rescaneo (root, excludes)
 *     - Respuesta incluye settings completos actualizados
 */
export function updateSettings(payload: SettingsUpdatePayload): Promise<{
  updated: string[];
  settings: SettingsPayload;
}> {
  return fetchJson("/settings", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

/**
 * Solicita al backend un cuadro de diálogo nativo para seleccionar directorio.
 */
export function browseForRoot(): Promise<BrowseDirectoryResponse> {
  return fetchJson("/settings/browse", {
    method: "POST",
  });
}

export function listDirectories(path?: string): Promise<ListDirectoriesResponse> {
  const url = path ? `/settings/list-directories?path=${encodeURIComponent(path)}` : "/settings/list-directories";
  return fetchJson(url, {
    method: "GET",
  });
}

export interface ListFilesResponse {
  current_path: string;
  directories: { name: string; path: string; is_parent: boolean }[];
  files: { name: string; path: string; extension: string; size_bytes: number }[];
}

export function listFiles(path?: string, extensions: string = ".py"): Promise<ListFilesResponse> {
  const params = new URLSearchParams();
  if (path) params.set("path", path);
  params.set("extensions", extensions);
  return fetchJson(`/settings/list-files?${params.toString()}`, {
    method: "GET",
  });
}

/**
 * Obtiene el estado Stage-Aware del proyecto.
 */
export function getStageStatus(): Promise<StageStatusPayload> {
  return fetchJson<StageStatusPayload>("/stage/status");
}

/**
 * Obtiene el estado del servidor Ollama (instalación, servicio y modelos).
 */
export function getOllamaStatus(): Promise<OllamaStatusPayload> {
  return fetchJson<OllamaStatusPayload>("/integrations/ollama/status");
}

/**
 * Requests the backend to start the Ollama server.
 */
export async function startOllama(payload: OllamaStartPayload): Promise<OllamaStartResponse> {
  const response = await fetch(buildUrl("/integrations/ollama/start"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let detailMessage = `Could not start Ollama (${response.status})`;
    const body = await response.text().catch(() => "");
    if (body) {
      try {
        const parsed = JSON.parse(body);
        const candidate = (parsed && parsed.detail) ?? parsed;
        if (candidate && typeof candidate === "object" && candidate.message) {
          detailMessage = String(candidate.message);
        }
      } catch {
        // No-op, keep the generic message.
      }
    }
    throw new Error(detailMessage);
  }

  return (await response.json()) as OllamaStartResponse;
}

/**
 * Runs a simple chat request against Ollama to verify connectivity.
 */
export async function testOllamaChat(payload: OllamaTestPayload): Promise<OllamaTestResponse> {
  const response = await fetch(buildUrl("/integrations/ollama/test"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const bodyText = await response.text().catch(() => "");

  if (!response.ok) {
    let detail: OllamaTestErrorDetail | undefined;
    if (bodyText) {
      try {
        const parsed = JSON.parse(bodyText);
        const candidate = (parsed && parsed.detail) ?? parsed;
        if (candidate && typeof candidate === "object") {
          detail = candidate as OllamaTestErrorDetail;
        }
      } catch {
        // Ignore parse errors, fall back to generic message.
      }
    }

    const message =
      detail?.message ?? `Ollama test request failed (${response.status})`;
    throw new OllamaTestError(message, response.status, detail);
  }

  if (!bodyText) {
    throw new OllamaTestError("Empty response from Ollama.", response.status);
  }

  try {
    return JSON.parse(bodyText) as OllamaTestResponse;
  } catch {
    throw new OllamaTestError(
      "Invalid server response while parsing JSON.",
      response.status
    );
  }
}

/**
 * Recupera el historial reciente de insights generados con Ollama.
 */
export function getOllamaInsights(limit = 20): Promise<OllamaInsightEntry[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  return fetchJson(`/integrations/ollama/insights?${params.toString()}`);
}

export function triggerOllamaInsights(payload?: {
  model?: string;
  timeout_seconds?: number;
  focus?: string;
}): Promise<OllamaInsightsResponse> {
  const bodyPayload = payload
    ? {
        ...payload,
        focus:
          payload.focus && payload.focus.trim()
            ? payload.focus.trim().toLowerCase()
            : undefined,
      }
    : {};
  return fetchJson("/integrations/ollama/analyze", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(bodyPayload),
  });
}

export function clearOllamaInsights(): Promise<OllamaInsightsClearResponse> {
  return fetchJson("/integrations/ollama/insights", {
    method: "DELETE",
  });
}

/**
 * Ejecuta init_project.py sobre el proyecto actual con los agentes seleccionados.
 */
export function initializeStageToolkit(payload: StageInitPayload): Promise<StageInitResponse> {
  return fetchJson<StageInitResponse>("/stage/init", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function installSuperClaudeFramework(): Promise<SuperClaudeInstallResponse> {
  return fetchJson<SuperClaudeInstallResponse>("/stage/superclaude/install", {
    method: "POST",
  });
}

/**
 * Audit log endpoints (pair programming sessions).
 */
export function listAuditRuns(limit = 20): Promise<AuditRunListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return fetchJson<AuditRunListResponse>(`/audit/runs?${params.toString()}`);
}

export function createAuditRun(payload: AuditRunCreatePayload): Promise<AuditRun> {
  return fetchJson<AuditRun>("/audit/runs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function closeAuditRun(
  runId: number,
  payload: AuditRunClosePayload = {}
): Promise<AuditRun> {
  return fetchJson<AuditRun>(`/audit/runs/${runId}/close`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getAuditRun(runId: number): Promise<AuditRun> {
  return fetchJson<AuditRun>(`/audit/runs/${runId}`);
}

export function getAuditEvents(
  runId: number,
  options?: { limit?: number; afterId?: number | null }
): Promise<AuditEventListResponse> {
  const params = new URLSearchParams();
  if (options?.limit) {
    params.set("limit", String(options.limit));
  }
  if (options?.afterId) {
    params.set("after_id", String(options.afterId));
  }
  const suffix = params.toString();
  const path = suffix ? `/audit/runs/${runId}/events?${suffix}` : `/audit/runs/${runId}/events`;
  return fetchJson<AuditEventListResponse>(path);
}

export function appendAuditEvent(
  runId: number,
  payload: AuditEventCreatePayload
): Promise<AuditEvent> {
  return fetchJson<AuditEvent>(`/audit/runs/${runId}/events`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getClassUml(options?: {
  includeExternal?: boolean;
  modulePrefixes?: string[];
  edgeTypes?: string[];
  graphvizOptions?: GraphvizOptionsPayload;
}): Promise<UMLDiagramResponse> {
  const params = new URLSearchParams();
  if (options?.includeExternal) {
    params.set("include_external", "true");
  }
  if (options?.modulePrefixes) {
    options.modulePrefixes.forEach((prefix) => {
      if (prefix.trim()) {
        params.append("module_prefix", prefix.trim());
      }
    });
  }
  if (options?.edgeTypes) {
    options.edgeTypes.forEach((type) => {
      params.append("edge_types", type);
    });
  }
  appendGraphvizParams(params, options?.graphvizOptions);
  const query = params.toString();
  return fetchJson(`/graph/uml${query ? `?${query}` : ""}`);
}

export async function getClassUmlSvg(options?: {
  includeExternal?: boolean;
  modulePrefixes?: string[];
  edgeTypes?: string[];
  graphvizOptions?: GraphvizOptionsPayload;
}): Promise<string> {
  const params = new URLSearchParams();
  if (options?.includeExternal) {
    params.set("include_external", "true");
  }
  if (options?.modulePrefixes) {
    options.modulePrefixes.forEach((prefix) => {
      const trimmed = prefix.trim();
      if (trimmed) {
        params.append("module_prefix", trimmed);
      }
    });
  }
  if (options?.edgeTypes) {
    options.edgeTypes.forEach((type) => {
      params.append("edge_types", type);
    });
  }
  appendGraphvizParams(params, options?.graphvizOptions);
  const query = params.toString();
  const response = await fetch(buildUrl(`/graph/uml/svg${query ? `?${query}` : ""}`));
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`API request failed (${response.status}): ${detail || "Unknown error"}`);
  }
  return await response.text();
}

/**
 * Get code as UML project definition for the UML Editor.
 *
 * Analyzes Python and TypeScript/TSX files and returns a complete
 * UML project definition that can be imported into the UML Editor.
 *
 * @param options Configuration options
 * @returns Promise with UmlProjectDef compatible structure
 */
export async function getCodeAsUmlProject(options?: {
  includeExternal?: boolean;
  modulePrefixes?: string[];
  projectName?: string;
  targetLanguage?: string;
}): Promise<{
  name: string;
  version: string;
  description: string;
  targetLanguage: string;
  modules: Array<{
    id: string;
    name: string;
    description: string;
    classes: any[];
    interfaces: any[];
    enums: any[];
    structs: any[];
    relationships: any[];
  }>;
}> {
  const params = new URLSearchParams();
  if (options?.includeExternal) {
    params.set("include_external", "true");
  }
  if (options?.modulePrefixes) {
    options.modulePrefixes.forEach((prefix) => {
      const trimmed = prefix.trim();
      if (trimmed) {
        params.append("module_prefix", trimmed);
      }
    });
  }
  if (options?.projectName) {
    params.set("project_name", options.projectName);
  }
  if (options?.targetLanguage) {
    params.set("target_language", options.targetLanguage);
  }
  const query = params.toString();
  return fetchJson(`/graph/uml/project${query ? `?${query}` : ""}`);
}

/**
 * Obtiene el estado actual del analizador.
 *
 * Returns:
 *     Promise con información de estado (archivos indexados, errores, etc.)
 *
 * Notes:
 *     - Endpoint: GET /api/status
 *     - Útil para monitoreo y diagnóstico
 *     - Incluye contadores y métricas de rendimiento
 */
export function getStatus(): Promise<StatusPayload> {
  return fetchJson<StatusPayload>("/status");
}

export async function getPreview(path: string): Promise<{ content: string; contentType: string }> {
  const response = await fetch(buildUrl(`/preview?path=${encodeURIComponent(path)}`));
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`Preview request failed (${response.status}): ${detail || "Unknown error"}`);
  }
  const content = await response.text();
  const contentType = response.headers.get("Content-Type") ?? "text/plain";
  return { content, contentType };
}

const GRAPHVIZ_PARAM_ENTRIES: Array<[keyof GraphvizOptionsPayload, string]> = [
  ["layoutEngine", "layout_engine"],
  ["rankdir", "rankdir"],
  ["splines", "splines"],
  ["nodesep", "nodesep"],
  ["ranksep", "ranksep"],
  ["pad", "pad"],
  ["margin", "margin"],
  ["bgcolor", "bgcolor"],
  ["graphFontname", "graph_fontname"],
  ["graphFontsize", "graph_fontsize"],
  ["nodeShape", "node_shape"],
  ["nodeStyle", "node_style"],
  ["nodeFillcolor", "node_fillcolor"],
  ["nodeColor", "node_color"],
  ["nodeFontcolor", "node_fontcolor"],
  ["nodeFontname", "node_fontname"],
  ["nodeFontsize", "node_fontsize"],
  ["nodeWidth", "node_width"],
  ["nodeHeight", "node_height"],
  ["nodeMarginX", "node_margin_x"],
  ["nodeMarginY", "node_margin_y"],
  ["edgeColor", "edge_color"],
  ["edgeFontname", "edge_fontname"],
  ["edgeFontsize", "edge_fontsize"],
  ["edgePenwidth", "edge_penwidth"],
  ["inheritanceStyle", "inheritance_style"],
  ["inheritanceColor", "inheritance_color"],
  ["associationColor", "association_color"],
  ["instantiationColor", "instantiation_color"],
  ["referenceColor", "reference_color"],
  ["inheritanceArrowhead", "inheritance_arrowhead"],
  ["associationArrowhead", "association_arrowhead"],
  ["instantiationArrowhead", "instantiation_arrowhead"],
  ["referenceArrowhead", "reference_arrowhead"],
  ["associationStyle", "association_style"],
  ["instantiationStyle", "instantiation_style"],
  ["referenceStyle", "reference_style"],
];

function appendGraphvizParams(
  params: URLSearchParams,
  options?: GraphvizOptionsPayload,
): void {
  if (!options) {
    return;
  }
  for (const [key, queryKey] of GRAPHVIZ_PARAM_ENTRIES) {
    const value = options[key];
    if (value === undefined || value === null) {
      continue;
    }
    params.set(queryKey, String(value));
  }
}

export function getLintersLatestReport(): Promise<LintersReportRecord | null> {
  return fetchJsonNullable<LintersReportRecord>("/linters/reports/latest");
}

export function getLintersReports(
  limit = 20,
  offset = 0
): Promise<LintersReportListItem[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  return fetchJson<LintersReportListItem[]>(`/linters/reports?${params.toString()}`);
}

export function getLintersNotifications(
  limit = 50,
  unreadOnly = false
): Promise<LintersNotificationEntry[]> {
  const params = new URLSearchParams({
    limit: String(limit),
    unread_only: unreadOnly ? "true" : "false",
  });
  return fetchJson<LintersNotificationEntry[]>(
    `/linters/notifications?${params.toString()}`
  );
}

export async function markNotificationAsRead(
  notificationId: number,
  read = true
): Promise<void> {
  const query = read ? "" : "?read=false";
  await fetchJsonNullable<void>(
    `/linters/notifications/${notificationId}/read${query}`,
    { method: "POST" }
  );
}

// =============================================================================
// Similarity Analysis API (C++ Module)
// =============================================================================

/**
 * Run similarity analysis on the current project.
 *
 * Args:
 *     payload: Analysis options (extensions, type3 detection, etc.)
 *
 * Returns:
 *     Promise with full similarity report including clones, hotspots, metrics
 *
 * Notes:
 *     - Endpoint: POST /api/similarity/analyze
 *     - Calls the C++ similarity detector via UDS server
 *     - Can be slow for large codebases (progress shown in UI)
 */
export function analyzeSimilarity(
  payload: SimilarityAnalyzePayload = {}
): Promise<SimilarityReport> {
  return fetchJson<SimilarityReport>("/similarity/analyze", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

/**
 * Get duplication hotspots (files with highest duplication scores).
 *
 * Args:
 *     limit: Maximum number of hotspots to return (default 10)
 *     extensions: File extensions to include (default [".py"])
 *
 * Returns:
 *     Promise with list of hotspot files sorted by duplication score
 */
export function getSimilarityHotspots(
  limit = 10,
  extensions?: string[]
): Promise<{ hotspots: DuplicationHotspot[]; count: number }> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (extensions && extensions.length > 0) {
    extensions.forEach((ext) => params.append("extension", ext));
  }
  return fetchJson(`/similarity/hotspots?${params.toString()}`);
}

/**
 * Get the latest cached similarity report if available.
 *
 * Returns:
 *     Promise with cached report or null if not available
 */
export function getSimilarityLatest(): Promise<SimilarityReport | null> {
  return fetchJsonNullable<SimilarityReport>("/similarity/latest");
}

/**
 * Get the default exclude patterns for similarity analysis.
 *
 * Returns:
 *     Promise with array of default glob patterns (e.g., "**\/tests\/**", "**\/venv\/**")
 */
export function getSimilarityDefaultPatterns(): Promise<string[]> {
  return fetchJson<{ patterns: string[] }>("/similarity/default-exclude-patterns").then(
    (res) => res.patterns
  );
}

// =============================================================================
// Contracts API (Phase 5 - AEGIS v2)
// =============================================================================

/**
 * Discover contracts for a symbol in a file.
 *
 * Args:
 *     request: Discovery request with file path and optional symbol line
 *
 * Returns:
 *     Promise with discovered contracts and stats
 *
 * Notes:
 *     - Endpoint: POST /api/contracts/discover
 *     - Runs multi-level discovery pipeline (L1: @aegis-contract, L2: patterns, etc.)
 *     - Requires symbol_line to be specified
 */
export function discoverContracts(
  request: DiscoverContractsRequest
): Promise<DiscoverContractsResponse> {
  return fetchJson<DiscoverContractsResponse>("/contracts/discover", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

// =============================================================================
// Symbols API (Phase 7.5 - Instance Graph Integration)
// =============================================================================

/**
 * Get detailed symbol information at a specific file:line location.
 *
 * Args:
 *     filePath: Path to the source file (relative or absolute)
 *     line: Line number where the symbol is defined (1-indexed)
 *
 * Returns:
 *     Promise with symbol details including name, kind, members, etc.
 *
 * Notes:
 *     - Endpoint: GET /api/symbols/at-location
 *     - Returns class members if symbol is a class
 *     - Returns parent class name if symbol is a method
 */
export function getSymbolAtLocation(
  filePath: string,
  line: number
): Promise<SymbolDetailsResponse> {
  const params = new URLSearchParams({
    file_path: filePath,
    line: String(line),
  });
  return fetchJson<SymbolDetailsResponse>(`/symbols/at-location?${params.toString()}`);
}

/**
 * Search for symbols by name across the project.
 *
 * Args:
 *     query: Search term (minimum 1 character)
 *     limit: Maximum number of results (default 50)
 *
 * Returns:
 *     Promise with matching symbols and total count
 */
export function searchSymbolsByName(
  query: string,
  limit = 50
): Promise<SymbolSearchResponse> {
  const params = new URLSearchParams({
    query,
    limit: String(limit),
  });
  return fetchJson<SymbolSearchResponse>(`/symbols/search?${params.toString()}`);
}

/**
 * Get all symbols defined in a specific file.
 *
 * Args:
 *     filePath: Path to the source file (relative or absolute)
 *
 * Returns:
 *     Promise with list of symbols sorted by line number
 */
export function getSymbolsInFile(filePath: string): Promise<SymbolSearchResult[]> {
  return fetchJson<SymbolSearchResult[]>(`/symbols/file/${encodeURIComponent(filePath)}`);
}

// =============================================================================
// Call Flow API (Function Call Chain Visualization)
// =============================================================================

/**
 * Get entry points (functions/methods) available in a file.
 *
 * Args:
 *     filePath: Absolute path to Python file
 *
 * Returns:
 *     Promise with list of entry points (name, qualified_name, line, kind)
 *
 * Notes:
 *     - Endpoint: GET /api/call-flow/entry-points/{filePath}
 *     - Returns all functions and methods that can be used as call flow entry points
 */
export function getCallFlowEntryPoints(
  filePath: string
): Promise<CallFlowEntryPointsResponse> {
  return fetchJson<CallFlowEntryPointsResponse>(
    `/call-flow/entry-points/${encodeURIComponent(filePath)}`
  );
}

/**
 * Get the call flow graph from a function/method entry point.
 *
 * Args:
 *     filePath: Absolute path to Python file
 *     functionName: Name of function or method to analyze
 *     maxDepth: Maximum call depth to follow (default 5, max 20)
 *     className: Class name if analyzing a method (optional)
 *     includeExternal: Include external calls (builtins, stdlib, third-party) as leaf nodes
 *
 * Returns:
 *     Promise with React Flow compatible graph (nodes, edges, metadata)
 *
 * Notes:
 *     - Endpoint: GET /api/call-flow/{filePath}?function=X&max_depth=N
 *     - Follows function calls recursively up to maxDepth
 *     - External calls (stdlib, third-party) are marked but not followed
 *     - With includeExternal=true, external calls appear as gray leaf nodes
 */
export function getCallFlow(
  filePath: string,
  functionName: string,
  maxDepth = 5,
  className?: string | null,
  includeExternal = false
): Promise<CallFlowResponse> {
  const params = new URLSearchParams({
    function: functionName,
    max_depth: String(maxDepth),
  });
  if (className) {
    params.set("class_name", className);
  }
  if (includeExternal) {
    params.set("include_external", "true");
  }
  return fetchJson<CallFlowResponse>(
    `/call-flow/${encodeURIComponent(filePath)}?${params.toString()}`
  );
}

/**
 * Get source code from a file for call flow node details.
 *
 * This endpoint allows reading files outside the AEGIS root since
 * Call Flow can analyze external projects.
 *
 * Args:
 *     filePath: Absolute path to the source file
 *     startLine: Start line number (1-indexed, default: 1)
 *     endLine: End line number (optional)
 *
 * Returns:
 *     Promise with plain text source code content
 *
 * Notes:
 *     - Endpoint: GET /api/call-flow/source/{filePath}
 *     - Only allows code file extensions (.py, .js, .ts, etc.)
 *     - File size limited to 512 KB
 */
export async function getCallFlowSource(
  filePath: string,
  startLine = 1,
  endLine?: number
): Promise<string> {
  const params = new URLSearchParams({
    start_line: String(startLine),
  });
  if (endLine !== undefined) {
    params.set("end_line", String(endLine));
  }
  const response = await fetch(
    buildUrl(`/call-flow/source/${encodeURIComponent(filePath)}?${params.toString()}`)
  );
  if (!response.ok) {
    const detail = await response.text().catch(() => response.statusText);
    throw new Error(`Source code request failed (${response.status}): ${detail || "Unknown error"}`);
  }
  return response.text();
}
