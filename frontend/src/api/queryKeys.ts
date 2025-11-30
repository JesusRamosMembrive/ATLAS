export const queryKeys = {
  tree: ["tree"] as const,
  file: (path: string) => ["file", path] as const,
  fileDiff: (path: string) => ["file-diff", path] as const,
  changes: ["changes"] as const,
  docs: ["docs"] as const,
  docPreview: (path: string) => ["doc-preview", path] as const,
  search: (term: string) => ["search", term] as const,
  settings: ["settings"] as const,
  status: ["status"] as const,
  preview: (path: string) => ["preview", path] as const,
  stageStatus: ["stage-status"] as const,
  ollamaInsights: (limit: number) => ["ollama", "insights", limit] as const,
  classUml: (
    includeExternal: boolean,
    prefixes?: string[],
    edgeTypes?: string[],
    graphvizSignature?: string,
  ) =>
    [
      "class-uml",
      includeExternal,
      prefixes ? [...prefixes].sort().join(",") : "",
      edgeTypes ? [...edgeTypes].sort().join(",") : "",
      graphvizSignature ?? "",
    ] as const,
  lintersLatest: ["linters", "latest"] as const,
  lintersReports: (limit: number, offset: number) =>
    ["linters", "reports", limit, offset] as const,
  lintersNotifications: (unreadOnly: boolean) =>
    ["linters", "notifications", unreadOnly] as const,
  auditRuns: (limit: number) => ["audit", "runs", limit] as const,
  auditRun: (runId: number) => ["audit", "runs", runId] as const,
  auditEvents: (runId: number, limit?: number) =>
    ["audit", "runs", runId, "events", limit ?? "all"] as const,
};
