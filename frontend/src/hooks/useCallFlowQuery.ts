import { useQuery, useMutation } from "@tanstack/react-query";

import { getCallFlow, getCallFlowEntryPoints, expandCallFlowBranch } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import type { CallFlowBranchExpansionResponse } from "../api/types";

interface EntryPointsOptions {
  filePath: string;
  enabled?: boolean;
}

export function useCallFlowEntryPointsQuery(options: EntryPointsOptions) {
  const { filePath, enabled = true } = options;

  return useQuery({
    queryKey: queryKeys.callFlowEntryPoints(filePath),
    queryFn: () => getCallFlowEntryPoints(filePath),
    enabled: enabled && !!filePath.trim(),
    staleTime: 60_000,
  });
}

interface CallFlowOptions {
  filePath: string;
  functionName: string;
  maxDepth?: number;
  className?: string | null;
  includeExternal?: boolean;
  extractionMode?: "full" | "lazy";
  enabled?: boolean;
}

export function useCallFlowQuery(options: CallFlowOptions) {
  const { filePath, functionName, maxDepth = 5, className, includeExternal = false, extractionMode = "lazy", enabled = true } = options;

  return useQuery({
    queryKey: [...queryKeys.callFlow(filePath, functionName, maxDepth), includeExternal, extractionMode],
    queryFn: () => getCallFlow(filePath, functionName, maxDepth, className, includeExternal, extractionMode),
    enabled: enabled && !!filePath.trim() && !!functionName.trim(),
    staleTime: 60_000,
  });
}

interface ExpandBranchOptions {
  filePath: string;
  functionName: string;
  maxDepth?: number;
  includeExternal?: boolean;
  onSuccess?: (data: CallFlowBranchExpansionResponse) => void;
  onError?: (error: Error) => void;
}

/**
 * Mutation hook for expanding a branch in lazy extraction mode.
 *
 * Usage:
 *   const expandMutation = useExpandBranchMutation({
 *     filePath: "/path/to/file.py",
 *     functionName: "main",
 *     onSuccess: (data) => { // merge new nodes/edges into state }
 *   });
 *
 *   // Then call:
 *   expandMutation.mutate(branchId);
 */
export function useExpandBranchMutation(options: ExpandBranchOptions) {
  const { filePath, functionName, maxDepth = 5, includeExternal = true, onSuccess, onError } = options;

  return useMutation({
    mutationFn: (branchId: string) =>
      expandCallFlowBranch(filePath, branchId, functionName, maxDepth, includeExternal),
    onSuccess,
    onError,
  });
}
