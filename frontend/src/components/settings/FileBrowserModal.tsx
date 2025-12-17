import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { listFiles, type ListFilesResponse } from "../../api/client";

interface FileBrowserModalProps {
  isOpen: boolean;
  currentPath: string;
  extensions?: string;
  onClose: () => void;
  onSelect: (path: string) => void;
}

export function FileBrowserModal({
  isOpen,
  currentPath,
  extensions = ".py",
  onClose,
  onSelect,
}: FileBrowserModalProps): JSX.Element | null {
  const getInitialPath = (path: string | undefined): string => {
    if (path && path.length > 1) return path;
    return "/home";
  };

  const initialPath = getInitialPath(currentPath);
  const [browsePath, setBrowsePath] = useState(initialPath);

  useEffect(() => {
    if (isOpen) {
      setBrowsePath(getInitialPath(currentPath));
    }
  }, [isOpen, currentPath]);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["listFiles", browsePath, extensions],
    queryFn: () => listFiles(browsePath, extensions),
    enabled: isOpen,
  });

  const handleDirectoryClick = (path: string) => {
    setBrowsePath(path);
    refetch();
  };

  const handleFileClick = (path: string) => {
    onSelect(path);
    onClose();
  };

  if (!isOpen) {
    return null;
  }

  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "600px" }}>
        <div className="modal-header">
          <h2>Select Python File</h2>
          <button className="modal-close-btn" onClick={onClose} aria-label="Close">
            &times;
          </button>
        </div>

        <div className="modal-body">
          <div className="directory-browser">
            <div className="directory-current-path">
              <strong>Current path:</strong>
              <code>{data?.current_path ?? browsePath}</code>
            </div>

            {isLoading && (
              <div className="directory-loading">
                <span className="loading-spinner" />
                <span>Loading...</span>
              </div>
            )}

            {error && (
              <div className="directory-error">
                <span className="error-icon">⚠️</span>
                <span>Error: {error instanceof Error ? error.message : "Failed to load"}</span>
              </div>
            )}

            {data && (
              <div style={{ maxHeight: "400px", overflow: "auto" }}>
                {/* Directories */}
                {data.directories.length > 0 && (
                  <ul className="directory-list" style={{ marginBottom: "8px" }}>
                    {data.directories.map((dir) => (
                      <li
                        key={dir.path}
                        className={`directory-item ${dir.is_parent ? "directory-item--parent" : ""}`}
                        onClick={() => handleDirectoryClick(dir.path)}
                        style={{ cursor: "pointer" }}
                      >
                        <span className="directory-icon">
                          {dir.is_parent ? "⬆️" : "📁"}
                        </span>
                        <span className="directory-name">{dir.name}</span>
                      </li>
                    ))}
                  </ul>
                )}

                {/* Files */}
                {data.files.length > 0 && (
                  <ul className="directory-list">
                    {data.files.map((file) => (
                      <li
                        key={file.path}
                        className="directory-item"
                        onClick={() => handleFileClick(file.path)}
                        style={{
                          cursor: "pointer",
                          backgroundColor: "#1e3a5f",
                          borderRadius: "4px",
                          marginBottom: "2px",
                        }}
                      >
                        <span className="directory-icon">🐍</span>
                        <span className="directory-name" style={{ flex: 1 }}>{file.name}</span>
                        <span style={{ fontSize: "11px", color: "#64748b", marginLeft: "8px" }}>
                          {formatSize(file.size_bytes)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}

                {data.directories.length === 0 && data.files.length === 0 && (
                  <div className="directory-empty">
                    <span>📂</span>
                    <span>No Python files found in this directory</span>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="modal-footer">
          <button className="ghost-btn" onClick={onClose}>
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
