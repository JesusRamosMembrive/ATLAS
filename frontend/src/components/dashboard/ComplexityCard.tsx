import { useNavigate } from "react-router-dom";
import { useState } from "react";
import type { StageDetectionStatus } from "../../api/types";
import { ComplexityListModal } from "./ComplexityListModal";

interface ComplexityCardProps {
  detection: StageDetectionStatus;
  variant?: "full" | "sidebar";
}

export function ComplexityCard({ detection, variant = "full" }: ComplexityCardProps): JSX.Element {
  const metrics = detection.metrics;
  const complexity = metrics?.complexity as { total: number; max: number; avg: number } | undefined;
  const distribution = metrics?.complexity_distribution as Record<string, number> | undefined;
  const topOffenders = metrics?.top_complex_functions as Array<{
    name: string;
    complexity: number;
    path: string;
    lineno: number;
  }> | undefined;

  const [showModal, setShowModal] = useState(false);
  const navigate = useNavigate();

  if (!complexity) {
    return (
      <article className="compact-card">
        <header className="compact-card__header">
          <h4 className="compact-card__title">Complexity Analysis</h4>
        </header>
        <div className="compact-card__content">
          <p style={{ color: "#7f869d", fontSize: "13px" }}>No data available.</p>
        </div>
      </article>
    );
  }

  // Distribution chart helper
  const distKeys = ["low", "medium", "high", "extreme"];
  const distLabels = ["Low (1-5)", "Medium (6-10)", "High (11-25)", "Extreme (25+)"];
  const distColors = ["#4ade80", "#facc15", "#fb923c", "#f87171"];
  const maxDistVal = distribution
    ? Math.max(...Object.values(distribution))
    : 0;

  const isSidebar = variant === "sidebar";

  // Use problematic list if available, otherwise just use top offenders
  const problematicFunctions = (metrics?.problematic_functions as Array<{
    name: string;
    complexity: number;
    path: string;
    lineno: number;
  }> | undefined) || topOffenders || [];

  return (
    <>
      <article className="compact-card" style={isSidebar ? { marginBottom: "16px" } : { padding: "24px" }}>
        <header className="compact-card__header" style={isSidebar ? {} : { marginBottom: "24px" }}>
          <div className="compact-card__title-row">
            <span style={{ fontSize: "16px", marginRight: "8px" }}>⚡</span>
            <h4 className="compact-card__title">Complexity Overview</h4>
          </div>
          {!isSidebar && (
            <div style={{ display: "flex", gap: "24px", alignItems: "center" }}>
              <MetricItem label="Avg Complexity" value={complexity.avg} color={getComplexityColor(complexity.avg)} />
              <MetricItem label="Max Complexity" value={complexity.max} />
              <MetricItem label="Total Complexity" value={formatNumber(complexity.total)} />
              {problematicFunctions.length > 0 && (
                <button
                  onClick={() => setShowModal(true)}
                  style={{
                    marginLeft: "24px",
                    background: "#252b3a",
                    border: "1px solid #334155",
                    color: "#94a3b8",
                    padding: "6px 12px",
                    borderRadius: "4px",
                    cursor: "pointer",
                    fontSize: "12px",
                    fontWeight: 500
                  }}>
                  View List ({problematicFunctions.length})
                </button>
              )}
            </div>
          )}
        </header>

        <div className="compact-card__content">
          {isSidebar && (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "8px", marginBottom: "16px" }}>
              <SidebarMetric label="Avg" value={complexity.avg} color={getComplexityColor(complexity.avg)} />
              <SidebarMetric label="Max" value={complexity.max} />
              <SidebarMetric label="Total" value={formatNumber(complexity.total)} />
            </div>
          )}

          <div style={{ display: "grid", gridTemplateColumns: isSidebar ? "1fr" : "1fr 1fr", gap: "32px", overflow: "hidden" }}>
            {/* Distribution Chart */}
            <div style={{ minWidth: 0, overflow: "hidden" }}>
              <h4 style={{ fontSize: "12px", color: "#94a3b8", marginBottom: "12px", textTransform: "uppercase", letterSpacing: "0.05em" }}>Distribution</h4>
              {distribution ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                  {distKeys.map((key, i) => {
                    const val = distribution[key] || 0;
                    const pct = maxDistVal > 0 ? (val / maxDistVal) * 100 : 0;
                    return (
                      <div key={key} style={{ display: "grid", gridTemplateColumns: isSidebar ? "70px 1fr 30px" : "100px 1fr 40px", alignItems: "center", gap: "8px" }}>
                        <span style={{ fontSize: "12px", color: "#cbd5e1", whiteSpace: "nowrap" }}>
                          {isSidebar ? distLabels[i].split(" ")[0] : distLabels[i]}
                        </span>
                        <div style={{ height: "6px", background: "#1e293b", borderRadius: "3px", overflow: "hidden" }}>
                          <div style={{ width: `${pct}%`, height: "100%", background: distColors[i], borderRadius: "3px" }} />
                        </div>
                        <span style={{ fontSize: "12px", color: "#94a3b8", textAlign: "right" }}>{val}</span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p style={{ color: "#64748b", fontSize: "13px" }}>No distribution data</p>
              )}
            </div>

            {/* Top Offenders Table */}
            <div style={{ minWidth: 0, overflow: "hidden" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
                <h4 style={{ fontSize: "12px", color: "#94a3b8", margin: 0, textTransform: "uppercase", letterSpacing: "0.05em" }}>Most Complex</h4>
                {isSidebar && problematicFunctions.length > 0 && (
                  <button
                    onClick={() => setShowModal(true)}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#60a5fa",
                      padding: 0,
                      cursor: "pointer",
                      fontSize: "11px",
                    }}>
                    See all ({problematicFunctions.length})
                  </button>
                )}
              </div>

              {topOffenders && topOffenders.length > 0 ? (
                <div style={{ display: "flex", flexDirection: "column", gap: "8px", overflow: "hidden" }}>
                  {topOffenders.slice(0, isSidebar ? 3 : 5).map((fn, i) => (
                    <div key={i} style={{
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                      padding: "6px 10px",
                      background: "#1e293b",
                      borderRadius: "4px",
                      minWidth: 0,
                    }}>
                      <div style={{ overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis", marginRight: "12px", flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: "13px", fontWeight: 500, color: "#e2e8f0", overflow: "hidden", textOverflow: "ellipsis" }}>{fn.name}</div>
                        <div style={{ fontSize: "11px", color: "#64748b", overflow: "hidden", textOverflow: "ellipsis" }}>
                          {getFileName(fn.path)}
                        </div>
                      </div>
                      <div style={{
                        background: getComplexityColor(fn.complexity) + "20",
                        color: getComplexityColor(fn.complexity),
                        padding: "2px 6px",
                        borderRadius: "3px",
                        fontWeight: 600,
                        fontSize: "12px",
                        flexShrink: 0,
                      }}>
                        {fn.complexity}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p style={{ color: "#64748b", fontSize: "13px" }}>None found</p>
              )}
            </div>
          </div>
        </div>
      </article>

      {showModal && (
        <ComplexityListModal
          functions={problematicFunctions}
          onClose={() => setShowModal(false)}
          onNavigate={(path) => {
            setShowModal(false);
            // Navigate to code-map with the file path as state
            navigate("/code-map", { state: { selectPath: path } });
          }}
        />
      )}
    </>
  );
}

function MetricItem({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ textAlign: "right" }}>
      <div style={{ fontSize: "12px", color: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
      <div style={{ fontSize: "24px", fontWeight: 700, color: color || "#f8fafc" }}>{value}</div>
    </div>
  );
}

function SidebarMetric({ label, value, color }: { label: string; value: string | number; color?: string }) {
  return (
    <div style={{ textAlign: "center", background: "#1e293b", padding: "8px", borderRadius: "4px" }}>
      <div style={{ fontSize: "11px", color: "#94a3b8", marginBottom: "2px" }}>{label}</div>
      <div style={{ fontSize: "15px", fontWeight: 700, color: color || "#f8fafc" }}>{value}</div>
    </div>
  );
}

function getComplexityColor(value: number): string {
  if (value <= 5) return "#4ade80"; // Green
  if (value <= 10) return "#facc15"; // Yellow
  if (value <= 25) return "#fb923c"; // Orange
  return "#f87171"; // Red
}

function formatNumber(value: number): string {
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return value.toString();
}

/**
 * Extract filename from a path, handling both Windows and Unix paths
 */
function getFileName(path: string): string {
  // Handle both Windows (\) and Unix (/) separators
  const parts = path.split(/[/\\]/);
  return parts[parts.length - 1] || path;
}
