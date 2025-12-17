# SPDX-License-Identifier: MIT
"""
Esquemas Pydantic para serializar respuestas de la API.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field, ConfigDict

from ..models import AnalysisError, FileSummary, ProjectTreeNode, SymbolInfo, SymbolKind
from ..linters.report_schema import CheckStatus, Severity
from ..state import AppState
from ..stage_toolkit import AgentSelection


class HealthResponse(BaseModel):
    """Respuesta del endpoint de health."""

    status: str = "ok"


class AnalysisErrorSchema(BaseModel):
    """Esquema para un error de análisis."""

    message: str
    lineno: Optional[int] = None
    col_offset: Optional[int] = None


class SymbolSchema(BaseModel):
    """Esquema para un símbolo de código."""

    name: str
    kind: SymbolKind
    lineno: int
    parent: Optional[str] = None
    path: Optional[str] = None
    docstring: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None


class FileSummarySchema(BaseModel):
    """Esquema para el resumen de un archivo."""

    path: str
    modified_at: Optional[datetime] = None
    symbols: List[SymbolSchema] = Field(default_factory=list)
    errors: List[AnalysisErrorSchema] = Field(default_factory=list)
    change_status: Optional[str] = None
    change_summary: Optional[str] = None


class FileDiffResponse(BaseModel):
    """Respuesta básica con el diff del working tree versus HEAD."""

    path: str
    diff: str
    has_changes: bool
    change_status: Optional[str] = None
    change_summary: Optional[str] = None


class DocFileSchema(BaseModel):
    """Representa un archivo markdown dentro del directorio docs/."""

    name: str
    path: str
    size_bytes: int
    modified_at: Optional[datetime] = None


class DocsListResponse(BaseModel):
    """Respuesta para la lista de archivos de documentación."""

    docs_path: str
    exists: bool
    file_count: int
    files: List[DocFileSchema] = Field(default_factory=list)


class WorkingTreeChangeSchema(BaseModel):
    """Representa un archivo con cambios pendientes respecto a HEAD."""

    path: str
    status: str
    summary: Optional[str] = None


class ChangesResponse(BaseModel):
    """Respuesta con la lista completa de cambios detectados."""

    changes: List[WorkingTreeChangeSchema] = Field(default_factory=list)


class TreeNodeSchema(BaseModel):
    """Esquema para un nodo del árbol de archivos."""

    name: str
    path: str
    is_dir: bool
    children: List["TreeNodeSchema"] = Field(default_factory=list)
    symbols: Optional[List[SymbolSchema]] = None
    errors: Optional[List[AnalysisErrorSchema]] = None
    modified_at: Optional[datetime] = None
    change_status: Optional[str] = None
    change_summary: Optional[str] = None


TreeNodeSchema.model_rebuild()


class SearchResultsSchema(BaseModel):
    """Esquema para los resultados de una búsqueda."""

    results: List[SymbolSchema]


class RescanResponse(BaseModel):
    """Respuesta del endpoint de rescan."""

    files: int


class ChangeNotification(BaseModel):
    """Notificación de cambios en el sistema de archivos."""

    updated: List[str]
    deleted: List[str]


class SettingsResponse(BaseModel):
    """Respuesta del endpoint de settings."""

    root_path: str
    absolute_root: str
    exclude_dirs: List[str]
    include_docstrings: bool
    ollama_insights_enabled: bool
    ollama_insights_model: Optional[str]
    ollama_insights_frequency_minutes: Optional[int]
    ollama_insights_focus: Optional[str]
    backend_url: Optional[str]
    watcher_active: bool


class SettingsUpdateRequest(BaseModel):
    """Petición para actualizar los settings."""

    root_path: Optional[str] = None
    include_docstrings: Optional[bool] = None
    exclude_dirs: Optional[List[str]] = None
    ollama_insights_enabled: Optional[bool] = None
    ollama_insights_model: Optional[str] = Field(default=None, min_length=1)
    ollama_insights_frequency_minutes: Optional[int] = Field(
        default=None,
        ge=1,
        le=24 * 60,
        description="Frecuencia en minutos (1-1440).",
    )
    ollama_insights_focus: Optional[str] = Field(
        default=None,
        min_length=0,
        max_length=64,
        description="Foco de análisis para los insights automáticos.",
    )
    backend_url: Optional[str] = Field(
        default=None,
        min_length=0,
        max_length=256,
        description="URL del servidor backend (ej: http://192.168.1.100:8010)",
    )


class SettingsUpdateResponse(BaseModel):
    """Respuesta de la actualización de settings."""

    updated: List[str]
    settings: SettingsResponse


class AnalyzerCapabilitySchema(BaseModel):
    """Esquema para una capacidad del analizador."""

    key: str
    description: str
    extensions: List[str]
    available: bool
    dependency: Optional[str] = None
    error: Optional[str] = None
    degraded_extensions: List[str] = Field(default_factory=list)


class StatusResponse(BaseModel):
    """Respuesta del endpoint de status."""

    root_path: str
    absolute_root: str
    watcher_active: bool
    include_docstrings: bool
    ollama_insights_enabled: bool
    ollama_insights_model: Optional[str]
    ollama_insights_frequency_minutes: Optional[int]
    ollama_insights_last_model: Optional[str] = None
    ollama_insights_last_message: Optional[str] = None
    ollama_insights_last_error: Optional[str] = None
    ollama_insights_last_run: Optional[datetime]
    ollama_insights_next_run: Optional[datetime]
    ollama_insights_focus: Optional[str]
    last_full_scan: Optional[datetime]
    last_event_batch: Optional[datetime]
    files_indexed: int
    symbols_indexed: int
    pending_events: int
    analyzers_degraded: bool = False
    degraded_capabilities: List[str] = Field(default_factory=list)
    capabilities: List[AnalyzerCapabilitySchema] = Field(default_factory=list)


class PreviewResponse(BaseModel):
    """Respuesta del endpoint de preview."""

    content: str
    content_type: str


class OptionalFilesStatus(BaseModel):
    """Estado opcional (archivos recomendados pero no obligatorios)."""

    expected: List[str]
    present: List[str]
    missing: List[str]


class AgentInstallStatus(BaseModel):
    """Estado de instalación para un agente (Claude, Codex o Gemini)."""

    expected: List[str]
    present: List[str]
    missing: List[str]
    installed: bool
    optional: Optional[OptionalFilesStatus] = None


class DocsStatus(BaseModel):
    """Estado de los documentos de referencia."""

    expected: List[str]
    present: List[str]
    missing: List[str]
    complete: bool


class StageDetectionStatus(BaseModel):
    """Resultado de la detección automática de etapa."""

    available: bool
    recommended_stage: Optional[int] = None
    confidence: Optional[str] = None
    reasons: List[str] = Field(default_factory=list)
    metrics: Optional[dict] = None
    error: Optional[str] = None
    checked_at: Optional[datetime] = None


class StageStatusResponse(BaseModel):
    """Payload completo con el estado stage-aware del proyecto."""

    root_path: str
    claude: AgentInstallStatus
    codex: AgentInstallStatus
    gemini: AgentInstallStatus
    docs: DocsStatus
    detection: StageDetectionStatus


class OllamaModelSchema(BaseModel):
    """Modelo disponible en Ollama."""

    name: str
    size_bytes: Optional[int] = None
    size_human: Optional[str] = None
    digest: Optional[str] = None
    modified_at: Optional[datetime] = None
    format: Optional[str] = None


class OllamaStatusSchema(BaseModel):
    """Estado detectado para Ollama."""

    installed: bool
    running: bool
    models: List[OllamaModelSchema] = Field(default_factory=list)
    version: Optional[str] = None
    binary_path: Optional[str] = None
    endpoint: Optional[str] = None
    warning: Optional[str] = None
    error: Optional[str] = None


class OllamaStatusResponse(BaseModel):
    """Respuesta con el estado actual de Ollama."""

    status: OllamaStatusSchema
    checked_at: datetime


class OllamaStartRequest(BaseModel):
    """Petición para iniciar el servidor Ollama."""

    timeout_seconds: Optional[float] = Field(default=None, ge=1.0, le=60.0)


class OllamaStartResponse(BaseModel):
    """Respuesta tras intentar iniciar Ollama."""

    started: bool
    already_running: bool
    endpoint: str
    process_id: Optional[int] = None
    status: OllamaStatusSchema
    checked_at: datetime


class OllamaTestRequest(BaseModel):
    """Petición para realizar un chat de prueba con Ollama."""

    model: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    system_prompt: Optional[str] = None
    endpoint: Optional[str] = None
    timeout_seconds: Optional[float] = Field(default=None, ge=1.0, le=1200.0)


class OllamaTestResponse(BaseModel):
    """Respuesta tras ejecutar una prueba de chat contra Ollama."""

    success: bool
    model: str
    endpoint: str
    latency_ms: float
    message: str
    raw: Dict[str, Any]


class OllamaInsightsRequest(BaseModel):
    """Petición para generar insights manualmente."""

    model: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Modelo a utilizar (por defecto usa el configurado en settings).",
    )
    timeout_seconds: Optional[float] = Field(default=180.0, ge=1.0, le=600.0)
    focus: Optional[str] = Field(
        default=None,
        min_length=0,
        max_length=64,
        description="Foco de análisis a aplicar (por defecto usa el configurado en settings).",
    )


class OllamaInsightsResponse(BaseModel):
    """Respuesta tras generar insights manualmente."""

    model: str
    generated_at: datetime
    message: str


class OllamaInsightEntry(BaseModel):
    """Elemento individual dentro del historial de insights."""

    id: int
    model: str
    message: str
    generated_at: datetime


class OllamaInsightsClearResponse(BaseModel):
    """Respuesta tras limpiar el historial de insights."""

    deleted: int


class StageInitRequest(BaseModel):
    """Petición para inicializar los assets stage-aware."""

    agents: AgentSelection = Field(default="both")
    force: bool = Field(
        default=False,
        description="Si True, fuerza reinstalación limpia eliminando archivos existentes.",
    )


class StageInitResponse(BaseModel):
    """Respuesta tras ejecutar init_project.py."""

    success: bool
    exit_code: int
    command: List[str]
    stdout: str
    stderr: str
    status: StageStatusResponse


class SuperClaudeLogEntry(BaseModel):
    """Salida detallada de cada comando ejecutado por el instalador."""

    command: List[str]
    stdout: str
    stderr: str
    exit_code: int


class SuperClaudeInstallResponse(BaseModel):
    """Resultado de sincronizar el framework SuperClaude."""

    success: bool
    error: Optional[str] = None
    installed_at: Optional[datetime] = None
    source_repo: str
    source_commit: Optional[str] = None
    component_counts: Dict[str, int] = Field(default_factory=dict)
    copied_paths: List[str] = Field(default_factory=list)
    logs: List[SuperClaudeLogEntry] = Field(default_factory=list)


class LinterToolSchema(BaseModel):
    """Estado de una herramienta estándar de linters."""

    key: str
    name: str
    description: str
    installed: bool
    version: Optional[str] = None
    command_path: Optional[str] = None
    homepage: Optional[str] = None
    error: Optional[str] = None


class LinterCustomRuleSchema(BaseModel):
    """Descripción de una regla de calidad personalizada."""

    key: str
    name: str
    description: str
    enabled: bool = True
    threshold: Optional[int] = None
    configurable: bool = True


class NotificationChannelSchema(BaseModel):
    """Canal disponible para notificaciones de escritorio."""

    key: str
    name: str
    available: bool
    description: Optional[str] = None
    command: Optional[str] = None


class LintersDiscoveryResponse(BaseModel):
    """Payload con el resultado del discovery de linters."""

    root_path: str
    generated_at: datetime
    tools: List[LinterToolSchema] = Field(default_factory=list)
    custom_rules: List[LinterCustomRuleSchema] = Field(default_factory=list)
    notifications: List[NotificationChannelSchema] = Field(default_factory=list)


class LinterIssueDetailSchema(BaseModel):
    """Detalle de incidencias registradas por un linter."""

    model_config = ConfigDict(use_enum_values=True)

    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    column: Optional[int] = None
    code: Optional[str] = None
    severity: Severity = Severity.MEDIUM
    suggestion: Optional[str] = None


class LinterToolRunSchema(BaseModel):
    """Resultado de ejecutar una herramienta estándar."""

    model_config = ConfigDict(use_enum_values=True)

    key: str
    name: str
    status: CheckStatus
    command: Optional[str] = None
    duration_ms: Optional[int] = None
    exit_code: Optional[int] = None
    version: Optional[str] = None
    issues_found: int = 0
    issues_sample: List[LinterIssueDetailSchema] = Field(default_factory=list)
    stdout_excerpt: Optional[str] = None
    stderr_excerpt: Optional[str] = None


class LinterRunCustomRuleSchema(BaseModel):
    """Estado de una regla personalizada ejecutada."""

    model_config = ConfigDict(use_enum_values=True)

    key: str
    name: str
    description: str
    status: CheckStatus
    threshold: Optional[int] = None
    violations: List[LinterIssueDetailSchema] = Field(default_factory=list)


class LinterCoverageSchema(BaseModel):
    """Instantánea de cobertura de tests."""

    statement_coverage: Optional[float] = None
    branch_coverage: Optional[float] = None
    missing_lines: Optional[int] = None


class LinterReportSummarySchema(BaseModel):
    """Resumen de un reporte de linters."""

    model_config = ConfigDict(use_enum_values=True)

    overall_status: CheckStatus
    total_checks: int
    checks_passed: int
    checks_warned: int
    checks_failed: int
    duration_ms: Optional[int] = None
    files_scanned: Optional[int] = None
    lines_scanned: Optional[int] = None
    issues_total: int = 0
    critical_issues: int = 0


class LinterChartDataSchema(BaseModel):
    """Datos agregados para visualizaciones."""

    issues_by_tool: Dict[str, int] = Field(default_factory=dict)
    issues_by_severity: Dict[str, int] = Field(default_factory=dict)
    top_offenders: List[str] = Field(default_factory=list)


class LintersReportSchema(BaseModel):
    """Payload completo de un reporte de linters."""

    model_config = ConfigDict(use_enum_values=True)

    root_path: str
    generated_at: datetime
    summary: LinterReportSummarySchema
    tools: List[LinterToolRunSchema] = Field(default_factory=list)
    custom_rules: List[LinterRunCustomRuleSchema] = Field(default_factory=list)
    coverage: Optional[LinterCoverageSchema] = None
    metrics: Dict[str, float] = Field(default_factory=dict)
    chart_data: LinterChartDataSchema = Field(default_factory=LinterChartDataSchema)
    notes: List[str] = Field(default_factory=list)


class LintersReportListItemSchema(BaseModel):
    """Elemento resumido para listados de reportes."""

    model_config = ConfigDict(use_enum_values=True)

    id: int
    generated_at: datetime
    root_path: str
    overall_status: CheckStatus
    issues_total: int
    critical_issues: int


class LintersReportRecordSchema(LintersReportListItemSchema):
    """Registro completo con el payload detallado."""

    report: LintersReportSchema


class NotificationEntrySchema(BaseModel):
    """Notificación almacenada en la base de datos."""

    model_config = ConfigDict(use_enum_values=True)

    id: int
    created_at: datetime
    channel: str
    severity: Severity
    title: str
    message: str
    payload: Optional[dict] = None
    root_path: Optional[str] = None
    read: bool = False


class BrowseDirectoryResponse(BaseModel):
    """Respuesta al seleccionar un directorio en el servidor."""

    path: str


class DirectoryItem(BaseModel):
    """Representa un directorio en el listado."""

    name: str = Field(..., description="Nombre del directorio")
    path: str = Field(..., description="Path absoluto del directorio")
    is_parent: bool = Field(
        default=False, description="True si es el directorio padre (..)"
    )


class ListDirectoriesResponse(BaseModel):
    """Respuesta al listar directorios disponibles."""

    current_path: str = Field(..., description="Path del directorio actual")
    directories: List[DirectoryItem] = Field(
        default_factory=list, description="Lista de subdirectorios"
    )


class FileItem(BaseModel):
    """Representa un archivo en el listado."""

    name: str = Field(..., description="Nombre del archivo")
    path: str = Field(..., description="Path absoluto del archivo")
    extension: str = Field(..., description="Extensión del archivo")
    size_bytes: int = Field(default=0, description="Tamaño en bytes")


class ListFilesResponse(BaseModel):
    """Respuesta al listar directorios y archivos."""

    current_path: str = Field(..., description="Path del directorio actual")
    directories: List[DirectoryItem] = Field(
        default_factory=list, description="Lista de subdirectorios"
    )
    files: List[FileItem] = Field(
        default_factory=list, description="Lista de archivos que coinciden con el filtro"
    )


class ClassGraphNode(BaseModel):
    """Nodo del grafo de clases."""

    id: str
    name: str
    module: str
    file: str


class ClassGraphEdge(BaseModel):
    """Arista del grafo de clases."""

    source: str
    target: str
    type: str
    internal: bool
    raw_target: str


class ClassGraphStats(BaseModel):
    """Métricas del grafo generado."""

    nodes: int
    edges: int
    edges_by_type: Dict[str, int]


class ClassGraphResponse(BaseModel):
    """Respuesta completa del grafo de clases."""

    nodes: List[ClassGraphNode]
    edges: List[ClassGraphEdge]
    stats: ClassGraphStats


class UMLAttribute(BaseModel):
    name: str
    type: Optional[str] = None
    optional: bool = False


class UMLMethod(BaseModel):
    name: str
    parameters: List[str] = Field(default_factory=list)
    returns: Optional[str] = None


class UMLClass(BaseModel):
    id: str
    name: str
    module: str
    file: str
    bases: List[str] = Field(default_factory=list)
    attributes: List[UMLAttribute] = Field(default_factory=list)
    methods: List[UMLMethod] = Field(default_factory=list)
    associations: List[str] = Field(default_factory=list)


class UMLDiagramResponse(BaseModel):
    classes: List[UMLClass]
    stats: Dict[str, int]


# -----------------------------------------------------------------------------
# Call Flow Schemas (v2)
# -----------------------------------------------------------------------------


class CallFlowResolutionStatus(str, Enum):
    """
    Resolution status for a call in the call flow graph.

    Values:
        resolved_project: Successfully resolved to a project symbol
        ignored_builtin: Python builtin (print, len, etc.)
        ignored_stdlib: Standard library (os, json, etc.)
        ignored_third_party: Third-party package
        unresolved: Could not resolve (unknown symbol)
        ambiguous: Multiple possible targets
    """
    RESOLVED_PROJECT = "resolved_project"
    IGNORED_BUILTIN = "ignored_builtin"
    IGNORED_STDLIB = "ignored_stdlib"
    IGNORED_THIRD_PARTY = "ignored_third_party"
    UNRESOLVED = "unresolved"
    AMBIGUOUS = "ambiguous"


class CallFlowIgnoredCallSchema(BaseModel):
    """
    Information about an ignored/external call.

    Attributes:
        expression: The call expression (e.g., "print", "os.path.join")
        status: Why it was ignored (builtin, stdlib, third-party)
        call_site_line: Line where the call occurs
        module_hint: Module name if known
        caller_id: ID of the node that made this call
    """
    expression: str
    status: CallFlowResolutionStatus
    call_site_line: int
    module_hint: Optional[str] = None
    caller_id: Optional[str] = None


class CallFlowNodeSchema(BaseModel):
    """
    A node in the call flow graph representing a function or method.

    Attributes:
        id: Unique node identifier (stable symbol ID format)
        name: Function/method name
        qualified_name: Full name including class (e.g., "MainWindow.on_click")
        file_path: Path to source file
        line: Line number of definition
        column: Column number of definition
        kind: Type: function, method, class
        is_entry_point: True if this is the starting node
        depth: Distance from entry point
        docstring: First line of docstring
        symbol_id: Stable symbol ID (same as id in v2)
        resolution_status: How this node was resolved
        reasons: Explanation if unresolved/ambiguous
    """

    id: str
    name: str
    qualified_name: str
    file_path: Optional[str] = None
    line: int = 0
    column: int = 0
    kind: str = "function"
    is_entry_point: bool = False
    depth: int = 0
    docstring: Optional[str] = None
    symbol_id: Optional[str] = None
    resolution_status: CallFlowResolutionStatus = CallFlowResolutionStatus.RESOLVED_PROJECT
    reasons: Optional[str] = None


class CallFlowEdgeSchema(BaseModel):
    """
    An edge representing a function call.

    Attributes:
        id: Unique edge identifier
        source: Source node ID (caller)
        target: Target node ID (callee)
        call_site_line: Line where the call occurs
        call_type: Type of call: direct, method, super, static
        expression: The call expression (e.g., "self.load()")
        resolution_status: How this edge's target was resolved
    """

    id: str
    source: str
    target: str
    call_site_line: int
    call_type: str = "direct"
    expression: Optional[str] = None
    resolution_status: CallFlowResolutionStatus = CallFlowResolutionStatus.RESOLVED_PROJECT


class CallFlowReactFlowNodeSchema(BaseModel):
    """React Flow formatted node for call flow visualization."""

    id: str
    type: str = "callNode"
    position: Dict[str, float]
    data: Dict[str, Any]


class CallFlowReactFlowEdgeSchema(BaseModel):
    """React Flow formatted edge for call flow visualization."""

    id: str
    source: str
    target: str
    type: str = "smoothstep"
    animated: bool = False
    data: Optional[Dict[str, Any]] = None


class CallFlowResponse(BaseModel):
    """
    Complete call flow graph response for React Flow visualization.

    Attributes:
        nodes: List of nodes formatted for React Flow
        edges: List of edges formatted for React Flow
        metadata: Graph metadata (entry_point, max_depth, etc.)
        ignored_calls: Calls that were classified as external (builtins, stdlib, third-party)
        unresolved_calls: Calls that could not be resolved
        diagnostics: Diagnostic info (cycles detected, max depth reached, etc.)
    """

    nodes: List[CallFlowReactFlowNodeSchema] = Field(default_factory=list)
    edges: List[CallFlowReactFlowEdgeSchema] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Graph metadata: entry_point, max_depth, source_file",
    )
    ignored_calls: List[CallFlowIgnoredCallSchema] = Field(
        default_factory=list,
        description="External calls (builtins, stdlib, third-party)",
    )
    unresolved_calls: List[str] = Field(
        default_factory=list,
        description="Calls that could not be resolved",
    )
    diagnostics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostic info: cycles_detected, max_depth_reached, etc.",
    )


class CallFlowEntryPointSchema(BaseModel):
    """An entry point (function/method) that can be used as call flow start."""

    name: str
    qualified_name: str
    line: int
    kind: str  # function, method, class
    class_name: Optional[str] = None
    node_count: Optional[int] = None  # Estimated number of nodes in call graph


class CallFlowEntryPointsResponse(BaseModel):
    """List of available entry points in a file."""

    file_path: str
    entry_points: List[CallFlowEntryPointSchema] = Field(default_factory=list)


# -----------------------------------------------------------------------------
# Audit Schemas
# -----------------------------------------------------------------------------


class AuditRunSchema(BaseModel):
    """Metadata for an auditable agent session."""

    id: int
    name: Optional[str] = None
    status: str
    root_path: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    closed_at: Optional[datetime] = None
    event_count: int = 0


class AuditRunCreateRequest(BaseModel):
    """Payload to start a new audit run."""

    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(
        default=None, max_length=128, description="Human-friendly label for the session"
    )
    notes: Optional[str] = Field(
        default=None, max_length=2000, description="Optional context or goal"
    )
    root_path: Optional[str] = Field(
        default=None, description="Root path to associate with the run"
    )


class AuditRunCloseRequest(BaseModel):
    """Payload to finalize a run."""

    model_config = ConfigDict(extra="forbid")

    status: Optional[str] = Field(
        default="closed", description="Status label when closing the run"
    )
    notes: Optional[str] = Field(
        default=None, max_length=2000, description="Extra notes captured on close"
    )


class AuditRunListResponse(BaseModel):
    """List wrapper for runs."""

    runs: List[AuditRunSchema]


class AuditEventSchema(BaseModel):
    """Single auditable event within a run."""

    id: int
    run_id: int
    type: str
    title: str
    detail: Optional[str] = None
    actor: Optional[str] = None
    phase: Optional[str] = None
    status: Optional[str] = None
    ref: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime


class AuditEventCreateRequest(BaseModel):
    """Payload to append a new event to a run."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(
        ...,
        description="Event type, e.g. intent|plan|command|command_result|diff|test|note",
    )
    title: str = Field(..., max_length=200, description="Short label for the event")
    detail: Optional[str] = Field(
        default=None, description="Optional expanded description or output"
    )
    actor: Optional[str] = Field(
        default=None, description="Who triggered the event (agent|human)"
    )
    phase: Optional[str] = Field(
        default=None, description="Workflow phase like explore|plan|apply|validate"
    )
    status: Optional[str] = Field(
        default=None, description="Status marker (ok|error|pending|running)"
    )
    ref: Optional[str] = Field(
        default=None, description="File or resource reference related to the event"
    )
    payload: Optional[Dict[str, Any]] = Field(
        default=None, description="Structured payload (command args, exit code, etc.)"
    )


class AuditEventListResponse(BaseModel):
    """List wrapper for events."""

    events: List[AuditEventSchema]


def serialize_symbol(
    symbol: SymbolInfo, state: AppState, *, include_path: bool = True
) -> SymbolSchema:
    """Serializa un objeto SymbolInfo a un SymbolSchema."""
    path = state.to_relative(symbol.path) if include_path else None
    return SymbolSchema(
        name=symbol.name,
        kind=symbol.kind,
        lineno=symbol.lineno,
        parent=symbol.parent,
        path=path,
        docstring=symbol.docstring,
        metrics=symbol.metrics if symbol.metrics else None,
    )


def serialize_error(error: AnalysisError) -> AnalysisErrorSchema:
    """Serializa un objeto AnalysisError a un AnalysisErrorSchema."""
    return AnalysisErrorSchema(
        message=error.message,
        lineno=error.lineno,
        col_offset=error.col_offset,
    )


def serialize_summary(
    summary: FileSummary,
    state: AppState,
    change: Optional[Dict[str, str]] = None,
) -> FileSummarySchema:
    """Serializa un objeto FileSummary a un FileSummarySchema."""
    symbols = [
        serialize_symbol(symbol, state, include_path=False)
        for symbol in summary.symbols
    ]
    errors = [serialize_error(error) for error in summary.errors]
    change_status = change.get("status") if change else None
    change_summary = change.get("summary") if change else None
    return FileSummarySchema(
        path=state.to_relative(summary.path),
        modified_at=summary.modified_at,
        symbols=symbols,
        errors=errors,
        change_status=change_status,
        change_summary=change_summary,
    )


def serialize_tree(
    node: ProjectTreeNode,
    state: AppState,
    *,
    change_map: Optional[Dict[str, Dict[str, str]]] = None,
) -> TreeNodeSchema:
    """Serializa un objeto ProjectTreeNode a un TreeNodeSchema."""
    children = [
        serialize_tree(child, state, change_map=change_map)
        for child in sorted(node.children.values(), key=lambda n: n.name)
    ]
    summary = node.file_summary
    symbols = None
    errors = None
    modified_at = None
    if summary:
        symbols = [
            serialize_symbol(symbol, state, include_path=False)
            for symbol in summary.symbols
        ]
        errors = [serialize_error(error) for error in summary.errors]
        modified_at = summary.modified_at

    rel_path = state.to_relative(node.path)
    change = change_map.get(rel_path) if change_map else None
    change_status = change.get("status") if change else None
    change_summary = change.get("summary") if change else None

    if node.is_dir and not change_status:
        child_has_changes = any(child.change_status for child in children)
        if child_has_changes:
            change_status = "modified"
            change_summary = "Contiene archivos modificados desde el último commit"

    return TreeNodeSchema(
        name=node.name,
        path=state.to_relative(node.path),
        is_dir=node.is_dir,
        children=children,
        symbols=symbols,
        errors=errors,
        modified_at=modified_at,
        change_status=change_status,
        change_summary=change_summary,
    )


def serialize_search_results(
    symbols: Iterable[SymbolInfo], state: AppState
) -> SearchResultsSchema:
    """Serializa una lista de SymbolInfo a un SearchResultsSchema."""
    return SearchResultsSchema(
        results=[serialize_symbol(symbol, state) for symbol in symbols]
    )


def serialize_settings(state: AppState) -> SettingsResponse:
    """Serializa el estado de la configuración a un SettingsResponse."""
    payload = state.get_settings_payload()
    return SettingsResponse(**payload)


def serialize_status(state: AppState) -> StatusResponse:
    """Serializa el estado de la aplicación a un StatusResponse."""
    payload = state.get_status_payload()
    return StatusResponse(**payload)
