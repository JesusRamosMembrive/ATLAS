import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

import { getDocsListing, getPreview } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import type { DocFileInfo } from "../api/types";
import "../styles/docs.css";

export function DocsLibraryView(): JSX.Element {
  const docsQuery = useQuery({
    queryKey: queryKeys.docs,
    queryFn: getDocsListing,
    staleTime: 60_000,
  });

  const [selectedPath, setSelectedPath] = useState<string | null>(null);

  useEffect(() => {
    const files = docsQuery.data?.files ?? [];
    if (files.length === 0) {
      setSelectedPath(null);
      return;
    }
    setSelectedPath((current) => {
      if (current && files.some((file) => file.path === current)) {
        return current;
      }
      return files[0]?.path ?? null;
    });
  }, [docsQuery.data]);

  const previewQuery = useQuery({
    queryKey: queryKeys.docPreview(selectedPath ?? ""),
    queryFn: () => getPreview(selectedPath!),
    enabled: Boolean(selectedPath),
  });

  const markdownComponents = useMemo<Components>(() => ({
    a: ({ node, ...props }) => (
      <a {...props} target="_blank" rel="noreferrer" />
    ),
  }), []);

  const files = docsQuery.data?.files ?? [];
  const hasDocsDir = docsQuery.data?.exists ?? false;
  const docsPathLabel = docsQuery.data?.docs_path ?? "docs";

  const selectedDoc = useMemo<DocFileInfo | undefined>(() => {
    if (!selectedPath) {
      return undefined;
    }
    return files.find((file) => file.path === selectedPath);
  }, [files, selectedPath]);

  return (
    <div className="docs-view">
      <section className="docs-panel docs-panel--list">
        <header className="docs-panel__header">
          <div>
            <h2>Documentation</h2>
            <p className="docs-panel__subtitle">{docsPathLabel}</p>
          </div>
          <button type="button" onClick={() => docsQuery.refetch()}>
            Refresh
          </button>
        </header>

        {docsQuery.isPending ? (
          <p className="docs-hint">Searching for docs/…</p>
        ) : docsQuery.isError ? (
          <p className="docs-error">
            {(docsQuery.error as Error)?.message ?? "Unable to inspect docs directory."}
          </p>
        ) : !hasDocsDir ? (
          <p className="docs-hint">No docs/ directory detected in the current workspace.</p>
        ) : files.length === 0 ? (
          <p className="docs-hint">Docs directory found, but no markdown files (.md) are present.</p>
        ) : (
          <ul className="docs-file-list">
            {files.map((file) => (
              <li key={file.path}>
                <button
                  type="button"
                  className={`docs-file${file.path === selectedPath ? " docs-file--active" : ""}`}
                  onClick={() => setSelectedPath(file.path)}
                >
                  <div>
                    <strong>{file.name}</strong>
                    <span className="docs-file__path">{file.path}</span>
                  </div>
                  <div className="docs-file__meta">
                    <span>{formatFileSize(file.size_bytes)}</span>
                    <span>{formatDate(file.modified_at)}</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="docs-panel docs-panel--preview">
        {selectedDoc ? (
          <div className="docs-preview">
            <header className="docs-preview__header">
              <div>
                <p className="docs-preview__eyebrow">Selected file</p>
                <h3>{selectedDoc.name}</h3>
                <span className="docs-preview__path">{selectedDoc.path}</span>
              </div>
              <div className="docs-preview__meta">
                <span>{formatFileSize(selectedDoc.size_bytes)}</span>
                <span>{formatDate(selectedDoc.modified_at)}</span>
              </div>
            </header>

            {previewQuery.isPending && <p className="docs-hint">Loading preview…</p>}
            {previewQuery.isError && (
              <p className="docs-error">
                {(previewQuery.error as Error)?.message ?? "Unable to load preview."}
              </p>
            )}
            {previewQuery.data && (
              <article className="docs-preview__content docs-preview__content--markdown">
                <ReactMarkdown
                  className="markdown-body"
                  remarkPlugins={[remarkGfm]}
                  components={markdownComponents}
                >
                  {previewQuery.data.content}
                </ReactMarkdown>
              </article>
            )}
          </div>
        ) : (
          <div className="docs-preview__empty">
            <p>Select a markdown file to preview its contents.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function formatFileSize(size: number | undefined): string {
  if (typeof size !== "number" || size < 0) {
    return "—";
  }
  if (size < 1024) {
    return `${size} B`;
  }
  const kb = size / 1024;
  if (kb < 1024) {
    return `${kb.toFixed(1)} KB`;
  }
  const mb = kb / 1024;
  return `${mb.toFixed(2)} MB`;
}

function formatDate(value?: string | null): string {
  if (!value) {
    return "—";
  }
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}
