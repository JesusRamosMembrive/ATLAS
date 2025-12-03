import { useQuery } from "@tanstack/react-query";

export interface CommitInfo {
  hash: string;
  author: string;
  date: string;
  message: string;
  files_changed: string[];
}

interface TimelineCommitsResponse {
  commits: CommitInfo[];
  total_commits: number;
}

export function useRecentCommits(limit = 5) {
  return useQuery<CommitInfo[]>({
    queryKey: ["timeline-commits", limit],
    queryFn: async () => {
      const response = await fetch(`/api/timeline/commits?limit=${limit}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch commits: ${response.statusText}`);
      }
      const data: TimelineCommitsResponse = await response.json();
      return data.commits ?? [];
    },
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: false,
  });
}
