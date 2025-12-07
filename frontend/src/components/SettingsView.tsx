import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";

import { browseForRoot, updateSettings } from "../api/client";
import type { SettingsPayload, SettingsUpdatePayload } from "../api/types";
import { queryKeys } from "../api/queryKeys";
import { DEFAULT_EXCLUDED_DIRS } from "../config/defaultExcludes";
import { useActivityStore } from "../state/useActivityStore";
import { useSelectionStore } from "../state/useSelectionStore";
import { useBackendStore } from "../state/useBackendStore";
import { useStatusQuery } from "../hooks/useStatusQuery";
import { DocstringsSection } from "./settings/DocstringsSection";
import { ExcludeDirsSection } from "./settings/ExcludeDirsSection";
import { RootPathSection } from "./settings/RootPathSection";
import { BackendUrlSection } from "./settings/BackendUrlSection";
import { DirectoryBrowserModal } from "./settings/DirectoryBrowserModal";
import { SupportedExtensionsSection } from "./settings/SupportedExtensionsSection";

interface SettingsViewProps {
  settingsQuery: UseQueryResult<SettingsPayload>;
}

const DEFAULT_EXCLUDES_LOWER = new Set(DEFAULT_EXCLUDED_DIRS.map((dir) => dir.toLowerCase()));

function extractCustomExcludes(list?: string[]): string[] {
  if (!list) {
    return [];
  }
  return list.filter((dir) => !DEFAULT_EXCLUDES_LOWER.has(dir.toLowerCase()));
}

function sortExcludes(list: string[]): string[] {
  return [...list].sort((a, b) => a.localeCompare(b));
}

export function SettingsView({ settingsQuery }: SettingsViewProps): JSX.Element {
  const activityClear = useActivityStore((state) => state.clear);
  const queryClient = useQueryClient();
  const statusQuery = useStatusQuery();

  const settings = settingsQuery.data;
  const originalRoot = settings?.root_path ?? "";
  const originalDoc = settings?.include_docstrings ?? true;
  const originalBackendUrl = settings?.backend_url ?? "";
  const originalCustomExcludes = useMemo(
    () => sortExcludes(extractCustomExcludes(settings?.exclude_dirs)),
    [settings?.exclude_dirs],
  );

  const [formRoot, setFormRoot] = useState(originalRoot);
  const [formDocstrings, setFormDocstrings] = useState(originalDoc);
  const [formBackendUrl, setFormBackendUrl] = useState(originalBackendUrl);
  const [customExcludes, setCustomExcludes] = useState<string[]>(originalCustomExcludes);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [showDirectoryBrowser, setShowDirectoryBrowser] = useState(false);

  const setBackendUrl = useBackendStore((state) => state.setBackendUrl);

  useEffect(() => {
    if (!settings) {
      return;
    }
    setFormRoot(settings.root_path);
    setFormDocstrings(settings.include_docstrings);
    setFormBackendUrl(settings.backend_url ?? "");
    setCustomExcludes(sortExcludes(extractCustomExcludes(settings.exclude_dirs)));
  }, [settings]);

  const mutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.settings, result.settings);
      queryClient.invalidateQueries({ queryKey: queryKeys.tree });
      queryClient.invalidateQueries({ queryKey: queryKeys.status });
      queryClient.invalidateQueries({ queryKey: queryKeys.stageStatus });
      if (result.updated.includes("root_path")) {
        useSelectionStore.getState().clearSelection();
      }
      if (result.updated.includes("backend_url")) {
        // Update Zustand store when backend_url changes
        setBackendUrl(result.settings.backend_url ?? null);
      }
      setCustomExcludes(sortExcludes(extractCustomExcludes(result.settings.exclude_dirs)));
      setStatusMessage(
        result.updated.length > 0
          ? `Applied changes: ${result.updated.join(", ")}`
          : "No changes needed saving.",
      );
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "Unknown error";
      setStatusMessage(`Error while saving: ${message}`);
    },
  });

  const excludesChanged = useMemo(() => {
    if (!settings) {
      return false;
    }
    if (originalCustomExcludes.length !== customExcludes.length) {
      return true;
    }
    return originalCustomExcludes.some((dir, index) => dir !== customExcludes[index]);
  }, [settings, originalCustomExcludes, customExcludes]);

  const isDirty = useMemo(() => {
    if (!settings) {
      return false;
    }
    if (originalRoot !== formRoot.trim()) {
      return true;
    }
    if (originalDoc !== formDocstrings) {
      return true;
    }
    if (originalBackendUrl !== formBackendUrl.trim()) {
      return true;
    }
    return excludesChanged;
  }, [settings, originalRoot, formRoot, originalDoc, formDocstrings, originalBackendUrl, formBackendUrl, excludesChanged]);

  const handleSave = () => {
    if (!settings || !isDirty || mutation.isPending) {
      return;
    }

    const payload: SettingsUpdatePayload = {};
    const trimmedRoot = formRoot.trim();
    const trimmedBackendUrl = formBackendUrl.trim();

    if (trimmedRoot && trimmedRoot !== originalRoot) {
      payload.root_path = trimmedRoot;
    }

    if (formDocstrings !== originalDoc) {
      payload.include_docstrings = formDocstrings;
    }

    if (trimmedBackendUrl !== originalBackendUrl) {
      payload.backend_url = trimmedBackendUrl || null;
    }

    if (excludesChanged) {
      payload.exclude_dirs = customExcludes;
    }

    if (Object.keys(payload).length === 0) {
      setStatusMessage("There are no changes to save.");
      return;
    }

    setStatusMessage(null);
    mutation.mutate(payload);
  };

  const handleAddExclude = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      return { ok: false, error: "Enter a valid directory name." };
    }

    if (/[\\/]/.test(trimmed)) {
      return { ok: false, error: "Use directory names only (no paths or separators)." };
    }

    const lowered = trimmed.toLowerCase();
    if (DEFAULT_EXCLUDES_LOWER.has(lowered)) {
      return { ok: false, error: "That directory is already excluded by default." };
    }

    if (customExcludes.some((dir) => dir.toLowerCase() === lowered)) {
      return { ok: false, error: "That directory is already in your exclusions." };
    }

    setCustomExcludes((prev) => sortExcludes([...prev, trimmed]));
    return { ok: true };
  };

  const handleRemoveExclude = (value: string) => {
    setCustomExcludes((prev) => prev.filter((dir) => dir !== value));
  };

  const statusTone = statusMessage?.toLowerCase().startsWith("error") ? "error" : "info";
  const isLoading = settingsQuery.isLoading;
  const isMutating = mutation.isPending;
  const browseMutation = useMutation({
    mutationFn: browseForRoot,
    onSuccess: (response) => {
      setFormRoot(response.path);
      setStatusMessage(`Selected directory: ${response.path}`);
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "Could not open the dialog";
      // If error contains "tkinter", open fallback modal
      if (message.includes("tkinter")) {
        setShowDirectoryBrowser(true);
        setStatusMessage("Using directory browser (tkinter not available)");
      } else if (message.includes("cancelada") || message.includes("cancelled")) {
        // User cancelled the dialog, don't show error
        return;
      } else {
        setStatusMessage(`Error selecting directory: ${message}`);
      }
    },
  });

  const handleDirectorySelect = (path: string) => {
    setFormRoot(path);
    setStatusMessage(`Selected directory: ${path}`);
    setShowDirectoryBrowser(false);
  };

  return (
    <div className="settings-view">
      <section className="settings-status-banner" aria-live="polite">
        <div className="settings-status-body">
          {settingsQuery.isLoading ? (
            <>
              <span
                className="settings-status-dot settings-status-dot--loading"
                aria-hidden="true"
              />
              <span className="settings-status-text settings-status-text--muted">
                Loading settings…
              </span>
            </>
          ) : settingsQuery.isError ? (
            <div className="error-banner">
              Could not load settings. {String(settingsQuery.error)}
            </div>
          ) : (
            <>
              <span
                className={`settings-status-dot ${
                  statusTone === "error" ? "settings-status-dot--error" : "settings-status-dot--info"
                }`}
                aria-hidden="true"
              />
              <span
                className={`settings-status-text${
                  statusTone === "error" ? " settings-status-text--error" : ""
                }`}
              >
                {statusMessage ?? "Changes are applied and persisted in the backend."}
              </span>
            </>
          )}
        </div>
        <div className="settings-status-actions">
          <button className="ghost-btn" type="button" onClick={activityClear}>
            Clear activity
          </button>
          <button
            className="primary-btn"
            type="button"
            onClick={handleSave}
            disabled={!isDirty || isMutating || isLoading}
          >
            {isMutating ? "Saving…" : "Save changes"}
          </button>
        </div>
      </section>

      <div className="settings-grid">
        <RootPathSection
          absoluteRoot={settings?.absolute_root}
          rootValue={formRoot}
          disabled={isLoading || browseMutation.isPending}
          onRootChange={setFormRoot}
          onBrowse={() => browseMutation.mutate()}
          browseDisabled={browseMutation.isPending || isMutating || isLoading}
        />

        <BackendUrlSection
          backendUrl={formBackendUrl}
          disabled={isLoading || isMutating}
          onBackendUrlChange={setFormBackendUrl}
        />

        <ExcludeDirsSection
          defaultDirs={DEFAULT_EXCLUDED_DIRS}
          customDirs={customExcludes}
          disabled={isLoading || isMutating}
          onAdd={handleAddExclude}
          onRemove={handleRemoveExclude}
        />

        <section className="settings-card watcher-info-card">
          <h2>Watcher and sync</h2>
          <p>Realtime updates are always enabled to keep your workspace in sync.</p>
          <div className="settings-status-body watcher-info-body">
            <span className="settings-status-dot settings-status-dot--info" aria-hidden="true" />
            <div className="watcher-info-copy">
              <span className="settings-status-text">
                Watcher is active and continuously listens for file system events.
              </span>
              <span className="settings-status-text">
                Significant changes trigger automatic rescans and snapshots persist to{" "}
                <code>.code-map</code> for faster startup.
              </span>
            </div>
          </div>
        </section>

        <DocstringsSection
          includeDocstrings={formDocstrings}
          disabled={isLoading}
          onToggleDocstrings={setFormDocstrings}
        />

        <SupportedExtensionsSection
          capabilities={statusQuery.data?.capabilities ?? []}
          isLoading={statusQuery.isLoading}
        />

        <section className="settings-card">
          <h2>Coming soon</h2>
          <p>Features on the roadmap for future iterations.</p>
          <div className="settings-tags">
            <span className="settings-tag">Integrations</span>
            <span className="settings-tag">Profiles</span>
            <span className="settings-tag">Alerts</span>
            <span className="settings-tag">Permissions</span>
          </div>
          <p>
            We plan to add support for multiple workspaces, language-specific exclusion rules, and
            configurable alerts for critical events.
          </p>
        </section>
      </div>

      <footer className="settings-footer">
        <span>Settings synchronized with the backend</span>
        <span>Last updated: {new Date().toLocaleString()}</span>
      </footer>

      <DirectoryBrowserModal
        isOpen={showDirectoryBrowser}
        currentPath={formRoot}
        onClose={() => setShowDirectoryBrowser(false)}
        onSelect={handleDirectorySelect}
      />
    </div>
  );
}
