import { Link } from "react-router-dom";

interface TopOffendersProps {
  files: string[];
  maxItems?: number;
}

function getFileName(path: string): string {
  const parts = path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || path;
}

function getFileIcon(path: string): string {
  if (path.endsWith(".py")) return "py";
  if (path.endsWith(".ts") || path.endsWith(".tsx")) return "ts";
  if (path.endsWith(".js") || path.endsWith(".jsx")) return "js";
  if (path.endsWith(".html")) return "html";
  if (path.endsWith(".css")) return "css";
  return "file";
}

export function TopOffenders({
  files,
  maxItems = 5,
}: TopOffendersProps): JSX.Element {
  const visibleFiles = files.slice(0, maxItems);

  if (visibleFiles.length === 0) {
    return (
      <div className="top-offenders top-offenders--empty">
        <span className="top-offenders__empty">No problem files</span>
      </div>
    );
  }

  return (
    <div className="top-offenders">
      <div className="top-offenders__header">
        <span className="top-offenders__title">Top Offenders</span>
        <Link to="/linters" className="top-offenders__link">
          Details
        </Link>
      </div>
      <ul className="top-offenders__list">
        {visibleFiles.map((file, index) => (
          <li key={file} className="top-offenders__item">
            <span className="top-offenders__rank">#{index + 1}</span>
            <span className={`top-offenders__icon top-offenders__icon--${getFileIcon(file)}`} />
            <span className="top-offenders__name" title={file}>
              {getFileName(file)}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
