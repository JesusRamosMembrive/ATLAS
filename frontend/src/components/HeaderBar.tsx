import { Link, useLocation } from "react-router-dom";
import { RescanButton } from "./RescanButton";

export interface HeaderBarProps {
  watcherActive?: boolean;
  rootPath?: string;
  lastFullScan?: string | null;
  filesIndexed?: number;
  title?: string;
}

export function HeaderBar({
  watcherActive = true,
  rootPath,
  lastFullScan,
  filesIndexed,
  title,
}: HeaderBarProps): JSX.Element {
  const location = useLocation();
  const currentPath = location.pathname;

  const rootLabel = rootPath ?? "ATLAS_ROOT";
  const description = lastFullScan
    ? `Last scan: ${new Date(lastFullScan).toLocaleString()} · ${filesIndexed ?? 0} files`
    : `${filesIndexed ?? 0} indexed files`;

  const navLinks = [
    { to: "/", label: "Home" },
    { to: "/stage-toolkit", label: "Stage Toolkit" },
    { to: "/code-map", label: "Analysis" },
    { to: "/docs", label: "Docs" },
    { to: "/class-uml", label: "UML" },
    { to: "/linters", label: "Linters" },
    { to: "/terminal", label: "Terminal" },
    { to: "/timeline", label: "Timeline" },
    { to: "/ollama", label: "AI Insights" },
    { to: "/overview", label: "Overview" },
    { to: "/prompts", label: "Prompts" },
  ];

  return (
    <header className="header-bar">
      <div className="header-left">
        <div className="brand-logo">&lt;/&gt;</div>
        <div className="brand-copy">
          <h1>{title ?? "ATLAS"}</h1>
          <p>{description}</p>
        </div>
      </div>

      <div className="header-actions">
        <nav className="header-nav">
          {navLinks.map((link) => (
            <Link
              key={link.to}
              className={`secondary-btn${currentPath === link.to ? " active" : ""}`}
              to={link.to}
            >
              {link.label}
            </Link>
          ))}
        </nav>
        <div className="status-indicator" title={`Root: ${rootLabel}`}>
          <span className="status-dot" style={{ opacity: watcherActive ? 1 : 0.4 }} />
          {watcherActive ? "Watcher active" : "Watcher inactive"}
        </div>
        <Link className="secondary-btn" to="/settings">
          Settings
        </Link>
        <RescanButton />
      </div>
    </header>
  );
}
