/**
 * TypeScript types for the C++ Similarity Detector module output.
 * Matches the JSON structure from cpp/src/models/report.hpp
 */

export type CloneType = "Type-1" | "Type-2" | "Type-3";

export interface CloneLocation {
  file: string;
  start_line: number;
  end_line: number;
  snippet_preview: string;
}

export interface CloneEntry {
  id: string;
  type: CloneType;
  similarity: number;
  locations: CloneLocation[];
  recommendation: string;
}

export interface SimilaritySummary {
  files_analyzed: number;
  total_lines: number;
  clone_pairs_found: number;
  estimated_duplication: string;
  analysis_time_ms: number;
}

export interface SimilarityPerformance {
  loc_per_second: number;
  tokens_per_second: number;
  files_per_second: number;
  total_tokens: number;
  thread_count: number;
  parallel_enabled: boolean;
}

export interface SimilarityTiming {
  tokenize_ms: number;
  hash_ms: number;
  match_ms: number;
  total_ms: number;
}

export interface SimilarityMetrics {
  by_type: Record<CloneType, number>;
  by_language: Record<string, number>;
}

export interface DuplicationHotspot {
  file: string;
  duplication_score: number;
  clone_count: number;
  duplicated_lines?: number;
  total_lines?: number;
  recommendation?: string;
}

export interface SimilarityReport {
  summary: SimilaritySummary;
  performance: SimilarityPerformance;
  timing: SimilarityTiming;
  metrics: SimilarityMetrics;
  hotspots: DuplicationHotspot[];
  clones: CloneEntry[];
}

export interface SimilarityAnalyzePayload {
  extensions?: string[];
  exclude_patterns?: string[] | null;
  type3?: boolean;
  min_tokens?: number;
  min_similarity?: number;
  threads?: number;
}

export interface SimilarityHotspotsPayload {
  limit?: number;
  extensions?: string[];
}
