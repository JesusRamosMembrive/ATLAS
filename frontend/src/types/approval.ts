/**
 * Type definitions for tool approval system.
 *
 * Provides type-safe interfaces for preview data, eliminating
 * unsafe type assertions like `as boolean` and `as unknown as`.
 */

// ============================================================================
// Preview Data Types
// ============================================================================

/**
 * Preview data for file diff operations (Write, Edit tools)
 */
export interface DiffPreviewData {
  file_path?: string;
  is_new_file?: boolean;
  original_lines?: number;
  new_lines?: number;
  // Edit-specific fields
  old_string_preview?: string;
  new_string_preview?: string;
  replace_all?: boolean;
  occurrences?: number;
  will_replace?: number;
  // Error case
  error?: string;
}

/**
 * Preview data for command execution (Bash tool)
 */
export interface CommandPreviewData {
  command?: string;
  description?: string;
  timeout_ms?: number;
  cwd?: string;
  // Warning flags
  has_sudo?: boolean;
  has_rm?: boolean;
  has_pipe?: boolean;
  has_redirect?: boolean;
  is_dangerous?: boolean;
}

/**
 * Preview data for multi-file edits (MultiEdit tool)
 */
export interface MultiDiffPreviewData {
  edits?: MultiDiffEdit[];
  total_files?: number;
  total_changes?: number;
}

export interface MultiDiffEdit {
  file_path: string;
  diff: string[];
  error?: string;
}

/**
 * Generic preview data for unknown tools
 */
export interface GenericPreviewData {
  tool_name?: string;
  input_summary?: string;
  [key: string]: unknown;
}

// ============================================================================
// Type Guards
// ============================================================================

/**
 * Type guard for CommandPreviewData
 */
export function isCommandPreviewData(data: unknown): data is CommandPreviewData {
  if (!data || typeof data !== "object") return false;
  const obj = data as Record<string, unknown>;
  // Command preview always has command field or warning flags
  return (
    typeof obj.command === "string" ||
    typeof obj.has_sudo === "boolean" ||
    typeof obj.has_rm === "boolean"
  );
}

/**
 * Type guard for DiffPreviewData
 */
export function isDiffPreviewData(data: unknown): data is DiffPreviewData {
  if (!data || typeof data !== "object") return false;
  const obj = data as Record<string, unknown>;
  return (
    typeof obj.is_new_file === "boolean" ||
    typeof obj.original_lines === "number" ||
    typeof obj.file_path === "string"
  );
}

/**
 * Type guard for MultiDiffPreviewData
 */
export function isMultiDiffPreviewData(data: unknown): data is MultiDiffPreviewData {
  if (!data || typeof data !== "object") return false;
  const obj = data as Record<string, unknown>;
  return Array.isArray(obj.edits);
}

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Safely get boolean value from preview data
 */
export function getPreviewBoolean(
  data: Record<string, unknown>,
  key: string,
  defaultValue = false
): boolean {
  const value = data[key];
  return typeof value === "boolean" ? value : defaultValue;
}

/**
 * Safely get string value from preview data
 */
export function getPreviewString(
  data: Record<string, unknown>,
  key: string,
  defaultValue = ""
): string {
  const value = data[key];
  return typeof value === "string" ? value : defaultValue;
}

/**
 * Safely get number value from preview data
 */
export function getPreviewNumber(
  data: Record<string, unknown>,
  key: string,
  defaultValue = 0
): number {
  const value = data[key];
  return typeof value === "number" ? value : defaultValue;
}

/**
 * Extract command preview data with safe defaults
 */
export function extractCommandPreview(data: Record<string, unknown>): CommandPreviewData {
  return {
    command: getPreviewString(data, "command"),
    description: getPreviewString(data, "description"),
    timeout_ms: getPreviewNumber(data, "timeout_ms"),
    cwd: getPreviewString(data, "cwd"),
    has_sudo: getPreviewBoolean(data, "has_sudo"),
    has_rm: getPreviewBoolean(data, "has_rm"),
    has_pipe: getPreviewBoolean(data, "has_pipe"),
    has_redirect: getPreviewBoolean(data, "has_redirect"),
    is_dangerous: getPreviewBoolean(data, "is_dangerous"),
  };
}

/**
 * Extract diff preview data with safe defaults
 */
export function extractDiffPreview(data: Record<string, unknown>): DiffPreviewData {
  return {
    file_path: getPreviewString(data, "file_path"),
    is_new_file: getPreviewBoolean(data, "is_new_file"),
    original_lines: getPreviewNumber(data, "original_lines"),
    new_lines: getPreviewNumber(data, "new_lines"),
    old_string_preview: getPreviewString(data, "old_string_preview"),
    new_string_preview: getPreviewString(data, "new_string_preview"),
    replace_all: getPreviewBoolean(data, "replace_all"),
    occurrences: getPreviewNumber(data, "occurrences"),
    will_replace: getPreviewNumber(data, "will_replace"),
    error: getPreviewString(data, "error"),
  };
}

/**
 * Extract multi-diff edits with safe defaults
 */
export function extractMultiDiffEdits(data: Record<string, unknown>): MultiDiffEdit[] {
  const edits = data.edits;
  if (!Array.isArray(edits)) return [];

  return edits
    .filter((edit): edit is Record<string, unknown> =>
      edit !== null && typeof edit === "object"
    )
    .map((edit) => ({
      file_path: getPreviewString(edit, "file_path"),
      diff: Array.isArray(edit.diff) ? edit.diff.filter((l): l is string => typeof l === "string") : [],
      error: typeof edit.error === "string" ? edit.error : undefined,
    }));
}
