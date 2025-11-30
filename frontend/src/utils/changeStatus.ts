export type WorkingTreeStatus = string | null | undefined;

export function getChangeLabel(status: WorkingTreeStatus): string {
  switch (status) {
    case "untracked":
      return "New";
    case "added":
      return "Added";
    case "deleted":
      return "Deleted";
    case "renamed":
      return "Renamed";
    case "conflict":
      return "Conflict";
    case "copied":
      return "Copied";
    default:
      return "Modified";
  }
}

export function getChangeVariant(
  status: WorkingTreeStatus,
): "added" | "deleted" | "conflict" | "renamed" | "default" {
  switch (status) {
    case "untracked":
    case "added":
      return "added";
    case "deleted":
      return "deleted";
    case "conflict":
      return "conflict";
    case "renamed":
    case "copied":
      return "renamed";
    default:
      return "default";
  }
}

export function isNewFileStatus(status: WorkingTreeStatus): boolean {
  return status === "untracked" || status === "added";
}
