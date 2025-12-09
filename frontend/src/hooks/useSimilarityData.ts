import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../api/queryKeys";
import {
  analyzeSimilarity,
  getSimilarityLatest,
  getSimilarityHotspots,
} from "../api/client";
import type {
  SimilarityReport,
  SimilarityAnalyzePayload,
} from "../api/similarityTypes";

/**
 * Hook to fetch the latest cached similarity report.
 */
export function useSimilarityLatest() {
  return useQuery({
    queryKey: queryKeys.similarityLatest,
    queryFn: () => getSimilarityLatest(),
    staleTime: 5 * 60 * 1000, // 5 minutes
    refetchOnWindowFocus: false,
  });
}

/**
 * Hook to fetch duplication hotspots.
 */
export function useSimilarityHotspots(limit = 10, extensions?: string[]) {
  return useQuery({
    queryKey: queryKeys.similarityHotspots(limit, extensions),
    queryFn: () => getSimilarityHotspots(limit, extensions),
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
}

/**
 * Hook to run similarity analysis (mutation).
 * Returns a mutation object that can be triggered with analyzeSimilarity.mutate()
 */
export function useSimilarityAnalyze() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (payload: SimilarityAnalyzePayload = {}) =>
      analyzeSimilarity(payload),
    onSuccess: (data: SimilarityReport) => {
      // Update the cached "latest" report
      queryClient.setQueryData(queryKeys.similarityLatest, data);
      // Invalidate hotspots to refresh them
      queryClient.invalidateQueries({
        queryKey: ["similarity", "hotspots"],
      });
    },
  });
}

/**
 * Combined hook for similarity dashboard.
 * Provides latest report and analyze mutation.
 */
export function useSimilarityDashboard() {
  const latestQuery = useSimilarityLatest();
  const analyzeMutation = useSimilarityAnalyze();

  return {
    // Latest report data
    report: latestQuery.data ?? null,
    isLoading: latestQuery.isLoading,
    isError: latestQuery.isError,
    error: latestQuery.error,
    refetch: latestQuery.refetch,

    // Analysis mutation
    analyze: analyzeMutation.mutate,
    isAnalyzing: analyzeMutation.isPending,
    analyzeError: analyzeMutation.error,
    lastAnalysis: analyzeMutation.data ?? null,
  };
}
