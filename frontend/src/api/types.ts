export type SymbolKind = "function" | "class" | "method";

export interface SymbolInfo {
  name: string;
  kind: SymbolKind;
  lineno: number;
  parent?: string | null;
  path?: string | null;
  docstring?: string | null;
  metrics?: Record<string, any> | null;
}

export interface AnalysisError {
  message: string;
  lineno?: number | null;
  col_offset?: number | null;
}

export interface FileSummary {
  path: string;
  modified_at?: string | null;
  symbols: SymbolInfo[];
  errors: AnalysisError[];
  change_status?: string | null;
  change_summary?: string | null;
}

export interface FileDiffResponse {
  path: string;
  diff: string;
  has_changes: boolean;
  change_status?: string | null;
  change_summary?: string | null;
}

export interface WorkingTreeChange {
  path: string;
  status: string;
  summary?: string | null;
}

export interface ChangesResponse {
  changes: WorkingTreeChange[];
}

export interface DocFileInfo {
  name: string;
  path: string;
  size_bytes: number;
  modified_at?: string | null;
}

export interface DocsListResponse {
  docs_path: string;
  exists: boolean;
  file_count: number;
  files: DocFileInfo[];
}

export interface ProjectTreeNode {
  name: string;
  path: string;
  is_dir: boolean;
  children: ProjectTreeNode[];
  symbols: SymbolInfo[] | null;
  errors: AnalysisError[] | null;
  modified_at?: string | null;
  change_status?: string | null;
  change_summary?: string | null;
}

export interface ChangeNotification {
  updated: string[];
  deleted: string[];
}

export interface SettingsPayload {
  root_path: string;
  absolute_root: string;
  exclude_dirs: string[];
  include_docstrings: boolean;
  ollama_insights_enabled: boolean;
  ollama_insights_model: string | null;
  ollama_insights_frequency_minutes: number | null;
  ollama_insights_focus: string | null;
  backend_url: string | null;
  watcher_active: boolean;
}

export interface SettingsUpdatePayload {
  root_path?: string;
  include_docstrings?: boolean;
  exclude_dirs?: string[];
  ollama_insights_enabled?: boolean;
  ollama_insights_model?: string | null;
  ollama_insights_frequency_minutes?: number | null;
  ollama_insights_focus?: string | null;
  backend_url?: string | null;
}

export interface AnalyzerCapability {
  key: string;
  description: string;
  extensions: string[];
  available: boolean;
  dependency?: string | null;
  error?: string | null;
  degraded_extensions: string[];
}

export interface StatusPayload {
  root_path: string;
  absolute_root: string;
  watcher_active: boolean;
  include_docstrings: boolean;
  ollama_insights_enabled: boolean;
  ollama_insights_model: string | null;
  ollama_insights_frequency_minutes: number | null;
  ollama_insights_focus: string | null;
  ollama_insights_last_model: string | null;
  ollama_insights_last_message: string | null;
  ollama_insights_last_error: string | null;
  ollama_insights_last_run: string | null;
  ollama_insights_next_run: string | null;
  last_full_scan: string | null;
  last_event_batch: string | null;
  files_indexed: number;
  symbols_indexed: number;
  pending_events: number;
  analyzers_degraded: boolean;
  degraded_capabilities: string[];
  capabilities: AnalyzerCapability[];
}

export type StageAgentSelection = "claude" | "codex" | "gemini" | "both" | "all";

export interface OptionalFilesStatus {
  expected: string[];
  present: string[];
  missing: string[];
}

export interface AgentInstallStatus {
  expected: string[];
  present: string[];
  missing: string[];
  installed: boolean;
  optional?: OptionalFilesStatus | null;
}

export interface DocsStatus {
  expected: string[];
  present: string[];
  missing: string[];
  complete: boolean;
}

export interface StageDetectionStatus {
  available: boolean;
  recommended_stage?: number | null;
  confidence?: string | null;
  reasons: string[];
  metrics?: Record<string, any> | null;
  error?: string | null;
  checked_at?: string | null;
}

export interface StageStatusPayload {
  root_path: string;
  claude: AgentInstallStatus;
  codex: AgentInstallStatus;
  gemini: AgentInstallStatus;
  docs: DocsStatus;
  detection: StageDetectionStatus;
}

export interface OllamaModelInfo {
  name: string;
  size_bytes?: number | null;
  size_human?: string | null;
  digest?: string | null;
  modified_at?: string | null;
  format?: string | null;
}

export interface OllamaStatus {
  installed: boolean;
  running: boolean;
  models: OllamaModelInfo[];
  version?: string | null;
  binary_path?: string | null;
  endpoint?: string | null;
  warning?: string | null;
  error?: string | null;
}

export interface OllamaStatusPayload {
  status: OllamaStatus;
  checked_at: string;
}

export interface OllamaTestPayload {
  model: string;
  prompt: string;
  system_prompt?: string;
  endpoint?: string;
  timeout_seconds?: number;
}

export interface OllamaTestResponse {
  success: boolean;
  model: string;
  endpoint: string;
  latency_ms: number;
  message: string;
  raw: Record<string, unknown>;
}

export interface OllamaTestErrorDetail {
  message?: string;
  endpoint?: string;
  original_error?: string;
  status_code?: number | null;
  reason_code?: string;
  retry_after_seconds?: number;
  loading?: boolean;
  loading_since?: string;
}

export interface OllamaStartPayload {
  timeout_seconds?: number;
}

export interface OllamaStartResponse {
  started: boolean;
  already_running: boolean;
  endpoint: string;
  process_id?: number | null;
  status: OllamaStatus;
  checked_at: string;
}

export interface OllamaInsightEntry {
  id: number;
  model: string;
  message: string;
  generated_at: string;
}

export interface OllamaInsightsResponse {
  model: string;
  generated_at: string;
  message: string;
}

export interface OllamaInsightsClearResponse {
  deleted: number;
}

export interface StageInitPayload {
  agents: StageAgentSelection;
  force?: boolean;
}

export interface StageInitResponse {
  success: boolean;
  exit_code: number;
  command: string[];
  stdout: string;
  stderr: string;
  status: StageStatusPayload;
}

export interface SuperClaudeLogEntry {
  command: string[];
  stdout: string;
  stderr: string;
  exit_code: number;
}

export interface SuperClaudeInstallResponse {
  success: boolean;
  error?: string | null;
  installed_at?: string | null;
  source_repo: string;
  source_commit?: string | null;
  component_counts: Record<string, number>;
  copied_paths: string[];
  logs: SuperClaudeLogEntry[];
}

export interface BrowseDirectoryResponse {
  path: string;
}

export interface DirectoryItem {
  name: string;
  path: string;
  is_parent: boolean;
}

export interface ListDirectoriesResponse {
  current_path: string;
  directories: DirectoryItem[];
}

export interface UMLAttribute {
  name: string;
  type?: string | null;
  optional: boolean;
}

export interface UMLMethod {
  name: string;
  parameters: string[];
  returns?: string | null;
}

export interface UMLClass {
  id: string;
  name: string;
  module: string;
  file: string;
  bases: string[];
  attributes: UMLAttribute[];
  methods: UMLMethod[];
  associations: string[];
}

export interface UMLDiagramResponse {
  classes: UMLClass[];
  stats: Record<string, number>;
}

export interface GraphvizOptionsPayload {
  layoutEngine?: string;
  rankdir?: string;
  splines?: string;
  nodesep?: number;
  ranksep?: number;
  pad?: number;
  margin?: number;
  bgcolor?: string;
  graphFontname?: string;
  graphFontsize?: number;
  nodeShape?: string;
  nodeStyle?: string;
  nodeFillcolor?: string;
  nodeColor?: string;
  nodeFontcolor?: string;
  nodeFontname?: string;
  nodeFontsize?: number;
  nodeWidth?: number;
  nodeHeight?: number;
  nodeMarginX?: number;
  nodeMarginY?: number;
  edgeColor?: string;
  edgeFontname?: string;
  edgeFontsize?: number;
  edgePenwidth?: number;
  inheritanceStyle?: string;
  inheritanceColor?: string;
  associationColor?: string;
  instantiationColor?: string;
  referenceColor?: string;
  inheritanceArrowhead?: string;
  associationArrowhead?: string;
  instantiationArrowhead?: string;
  referenceArrowhead?: string;
  associationStyle?: string;
  instantiationStyle?: string;
  referenceStyle?: string;
}

export type LinterCheckStatus = "pass" | "warn" | "fail" | "skipped" | "error";
export type LinterSeverity = "info" | "low" | "medium" | "high" | "critical";

export interface LinterIssueDetail {
  message: string;
  file?: string | null;
  line?: number | null;
  column?: number | null;
  code?: string | null;
  severity: LinterSeverity;
  suggestion?: string | null;
}

export interface LinterToolRun {
  key: string;
  name: string;
  status: LinterCheckStatus;
  command?: string | null;
  duration_ms?: number | null;
  exit_code?: number | null;
  version?: string | null;
  issues_found: number;
  issues_sample: LinterIssueDetail[];
  stdout_excerpt?: string | null;
  stderr_excerpt?: string | null;
}

export interface LinterCustomRuleRun {
  key: string;
  name: string;
  description: string;
  status: LinterCheckStatus;
  threshold?: number | null;
  violations: LinterIssueDetail[];
}

export interface LinterCoverageSnapshot {
  statement_coverage?: number | null;
  branch_coverage?: number | null;
  missing_lines?: number | null;
}

export interface LinterReportSummary {
  overall_status: LinterCheckStatus;
  total_checks: number;
  checks_passed: number;
  checks_warned: number;
  checks_failed: number;
  duration_ms?: number | null;
  files_scanned?: number | null;
  lines_scanned?: number | null;
  issues_total: number;
  critical_issues: number;
}

export interface LinterChartData {
  issues_by_tool: Record<string, number>;
  issues_by_severity: Record<LinterSeverity | string, number>;
  top_offenders: string[];
}

export interface LintersReportPayload {
  root_path: string;
  generated_at: string;
  summary: LinterReportSummary;
  tools: LinterToolRun[];
  custom_rules: LinterCustomRuleRun[];
  coverage?: LinterCoverageSnapshot | null;
  metrics: Record<string, number>;
  chart_data: LinterChartData;
  notes: string[];
}

export interface LintersReportListItem {
  id: number;
  generated_at: string;
  root_path: string;
  overall_status: LinterCheckStatus;
  issues_total: number;
  critical_issues: number;
}

export interface LintersReportRecord extends LintersReportListItem {
  report: LintersReportPayload;
}

export interface LintersNotificationEntry {
  id: number;
  created_at: string;
  channel: string;
  severity: LinterSeverity;
  title: string;
  message: string;
  payload?: Record<string, unknown> | null;
  root_path?: string | null;
  read: boolean;
}

export interface AuditRun {
  id: number;
  name?: string | null;
  status: string;
  root_path?: string | null;
  notes?: string | null;
  created_at: string;
  closed_at?: string | null;
  event_count: number;
}

export interface AuditRunListResponse {
  runs: AuditRun[];
}

export interface AuditRunCreatePayload {
  name?: string | null;
  notes?: string | null;
  root_path?: string | null;
}

export interface AuditRunClosePayload {
  status?: string | null;
  notes?: string | null;
}

export interface AuditEvent {
  id: number;
  run_id: number;
  type: string;
  title: string;
  detail?: string | null;
  actor?: string | null;
  phase?: string | null;
  status?: string | null;
  ref?: string | null;
  payload?: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditEventListResponse {
  events: AuditEvent[];
}

export interface AuditEventCreatePayload {
  type: string;
  title: string;
  detail?: string | null;
  actor?: string | null;
  phase?: string | null;
  status?: string | null;
  ref?: string | null;
  payload?: Record<string, unknown> | null;
}

// =============================================================================
// Contracts API (Phase 5 - AEGIS v2)
// =============================================================================

export type ThreadSafety = "not_safe" | "safe" | "safe_after_start" | "immutable" | "unknown";
export type EvidencePolicy = "required" | "optional" | "warning";

export interface EvidenceItemResponse {
  type: string;
  reference: string;
  policy: EvidencePolicy;
}

export interface ContractResponse {
  thread_safety?: ThreadSafety | null;
  lifecycle?: string | null;
  invariants: string[];
  preconditions: string[];
  postconditions: string[];
  errors: string[];
  dependencies: string[];
  evidence: EvidenceItemResponse[];
  confidence: number;
  source_level: number;
  needs_review: boolean;
  inferred: boolean;
  confidence_notes?: string | null;
  file_path?: string | null;
  start_line?: number | null;
  end_line?: number | null;
}

export interface DiscoverContractsRequest {
  file_path: string;
  symbol_line?: number | null;
  levels?: number[] | null;
}

export type DocumentationType = "aegis" | "doxygen" | "comment" | "none";

export interface DiscoverContractsResponse {
  contracts: ContractResponse[];
  stats: Record<string, number>;
  // New fields for interactive flow
  documentation_type?: DocumentationType | null;
  warning?: string | null;  // "no_documentation_found", etc.
  llm_available: boolean;
}
