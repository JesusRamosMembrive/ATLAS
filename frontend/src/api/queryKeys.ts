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
  ollamaStatus: ["ollama", "status"] as const,
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
  // Similarity analysis (C++ module)
  similarityLatest: ["similarity", "latest"] as const,
  similarityAnalyze: (extensions: string[], type3: boolean) =>
    ["similarity", "analyze", extensions.sort().join(","), type3] as const,
  similarityHotspots: (limit: number, extensions?: string[]) =>
    ["similarity", "hotspots", limit, extensions?.sort().join(",") ?? ""] as const,
  // Contracts API (AEGIS v2 Phase 5)
  contracts: (filePath: string, symbolLine: number, levels?: number[]) =>
    ["contracts", "discover", filePath, symbolLine, levels?.join(",") ?? "default"] as const,
  // Symbols API (Phase 7.5 - Instance Graph Integration)
  symbolDetails: (filePath: string, line: number) =>
    ["symbols", "at-location", filePath, line] as const,
  symbolSearch: (query: string) =>
    ["symbols", "search", query] as const,
  symbolsInFile: (filePath: string) =>
    ["symbols", "file", filePath] as const,
  // Call Flow API (Function Call Chain Visualization)
  callFlowEntryPoints: (filePath: string) =>
    ["call-flow", "entry-points", filePath] as const,
  callFlow: (filePath: string, functionName: string, maxDepth: number) =>
    ["call-flow", filePath, functionName, maxDepth] as const,
};
