import { useQuery } from "@tanstack/react-query";

import { getCallFlow, getCallFlowEntryPoints } from "../api/client";
import { queryKeys } from "../api/queryKeys";

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
  enabled?: boolean;
}

export function useCallFlowQuery(options: CallFlowOptions) {
  const { filePath, functionName, maxDepth = 5, className, enabled = true } = options;

  return useQuery({
    queryKey: queryKeys.callFlow(filePath, functionName, maxDepth),
    queryFn: () => getCallFlow(filePath, functionName, maxDepth, className),
    enabled: enabled && !!filePath.trim() && !!functionName.trim(),
    staleTime: 60_000,
  });
}
