/**
 * Hook for fetching symbol details at a specific file:line location.
 *
 * Used by DetailPanel to display symbol information (class members, docstring)
 * when a node is selected in the instance graph.
 */

import { useQuery } from "@tanstack/react-query";
import { queryKeys } from "../api/queryKeys";
import { getSymbolAtLocation } from "../api/client";
import type { SymbolDetailsResponse } from "../api/types";

export interface UseSymbolDetailsOptions {
  /** Path to the source file */
  filePath?: string;
  /** Line number where the symbol is defined (1-indexed) */
  line?: number;
  /** Whether to enable the query (default: true when filePath and line are provided) */
  enabled?: boolean;
}

export interface UseSymbolDetailsResult {
  /** Symbol details data */
  data: SymbolDetailsResponse | undefined;
  /** Whether the query is loading */
  isLoading: boolean;
  /** Whether the query has errored */
  isError: boolean;
  /** Error object if query failed */
  error: Error | null;
  /** Refetch the data */
  refetch: () => void;
}

/**
 * Fetch symbol details for a specific file:line location.
 *
 * @param options - Query options including filePath and line
 * @returns Query result with symbol details
 *
 * @example
 * ```tsx
 * const { data, isLoading } = useSymbolDetails({
 *   filePath: "code_map/analyzer.py",
 *   line: 42,
 * });
 *
 * if (data?.kind === "class") {
 *   console.log("Class members:", data.members);
 * }
 * ```
 */
export function useSymbolDetails(
  options: UseSymbolDetailsOptions
): UseSymbolDetailsResult {
  const { filePath, line, enabled } = options;

  const query = useQuery({
    queryKey: queryKeys.symbolDetails(filePath ?? "", line ?? 0),
    queryFn: () => getSymbolAtLocation(filePath!, line!),
    enabled: enabled ?? (!!filePath && typeof line === "number" && line > 0),
    staleTime: 30_000, // 30 seconds - symbols don't change often
    retry: 1,
  });

  return {
    data: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
  };
}
