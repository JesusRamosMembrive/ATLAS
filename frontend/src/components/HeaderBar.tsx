import { useState, useEffect } from "react";
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
  const [collapsed, setCollapsed] = useState(false);
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  // Close mobile nav when route changes
  useEffect(() => {
    setMobileNavOpen(false);
  }, [currentPath]);

  // Close mobile nav when clicking outside
  useEffect(() => {
    if (!mobileNavOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest('.header-nav') && !target.closest('.mobile-menu-toggle')) {
        setMobileNavOpen(false);
      }
    };

    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, [mobileNavOpen]);

  const rootLabel = rootPath ?? "AEGIS_ROOT";
  const description = lastFullScan
    ? `Last scan: ${new Date(lastFullScan).toLocaleString()} · ${filesIndexed ?? 0} files`
    : `${filesIndexed ?? 0} indexed files`;

  const navLinks = [
    { to: "/", label: "Home" },
    { to: "/stage-toolkit", label: "Stage Toolkit" },
    { to: "/code-map", label: "Analysis" },
    { to: "/docs", label: "Docs" },
    { to: "/class-uml", label: "UML" },
    { to: "/call-flow", label: "Call Flow" },
    { to: "/linters", label: "Linters" },
    { to: "/similarity", label: "Similarity" },
    { to: "/terminal", label: "Terminal" },
    { to: "/agent", label: "Agent" },
    { to: "/timeline", label: "Timeline" },
    { to: "/ollama", label: "AI Insights" },
    { to: "/overview", label: "Overview" },
    { to: "/prompts", label: "Prompts" },
  ];

  return (
    <header className={`header-bar${collapsed ? " header-collapsed" : ""}`}>
      <div className="header-top-row">
        <div className="header-left">
          <div className="brand-logo">&lt;/&gt;</div>
          {!collapsed && (
            <div className="brand-copy">
              <h1>{title ?? "AEGIS"}</h1>
              <p>{description}</p>
            </div>
          )}
        </div>

        <div className="header-actions">
          <button
            className="mobile-menu-toggle"
            onClick={() => setMobileNavOpen(!mobileNavOpen)}
            aria-label={mobileNavOpen ? "Close navigation menu" : "Open navigation menu"}
            aria-expanded={mobileNavOpen}
          >
            {mobileNavOpen ? "✕" : "☰"}
          </button>
          <nav className={`header-nav${mobileNavOpen ? " mobile-nav-open" : ""}`}>
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
          <button
            className="header-collapse-btn"
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? "Expand header" : "Collapse header"}
            aria-label={collapsed ? "Expand header" : "Collapse header"}
          >
            {collapsed ? "▼" : "▲"}
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="header-bottom-row">
          <div className="status-indicator" title={`Root: ${rootLabel}`}>
            <span className="status-dot" style={{ opacity: watcherActive ? 1 : 0.4 }} />
            {watcherActive ? "Watcher active" : "Watcher inactive"}
          </div>
          <div className="header-controls">
            <Link className="secondary-btn" to="/settings">
              Settings
            </Link>
            <RescanButton />
          </div>
        </div>
      )}
    </header>
  );
}
