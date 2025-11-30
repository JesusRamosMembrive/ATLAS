import { useMutation } from "@tanstack/react-query";

import { installSuperClaudeFramework } from "../api/client";
import type { SuperClaudeInstallResponse } from "../api/types";

export function useSuperClaudeInstallMutation() {
  return useMutation<SuperClaudeInstallResponse, Error, void>({
    mutationFn: installSuperClaudeFramework,
  });
}
