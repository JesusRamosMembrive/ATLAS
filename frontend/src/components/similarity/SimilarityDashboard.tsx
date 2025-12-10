import { useState, useEffect } from "react";
import { useSimilarityDashboard } from "../../hooks/useSimilarityData";
import type { SimilarityAnalyzePayload } from "../../api/similarityTypes";
import { SummaryCard } from "./SummaryCard";
import { PerformanceCard } from "./PerformanceCard";
import { HotspotsCard } from "./HotspotsCard";
import { ClonesCard } from "./ClonesCard";
import { LegendCard } from "./LegendCard";
import "../../styles/similarity.css";

export function SimilarityDashboard(): JSX.Element {
  const {
    report,
    isLoading,
    isError,
    error,
    analyze,
    isAnalyzing,
    analyzeError,
    defaultPatterns,
  } = useSimilarityDashboard();

  // Analysis options state
  const [extensions, setExtensions] = useState<string[]>([".py"]);
  const [type3Enabled, setType3Enabled] = useState(false);
  const [excludePatterns, setExcludePatterns] = useState<string[]>([]);
  const [showExcludePatterns, setShowExcludePatterns] = useState(false);
  const [newPattern, setNewPattern] = useState("");

  // Initialize exclude patterns from defaults when loaded
  useEffect(() => {
    if (defaultPatterns.length > 0 && excludePatterns.length === 0) {
      setExcludePatterns(defaultPatterns);
    }
  }, [defaultPatterns, excludePatterns.length]);

  const handleAnalyze = () => {
    const payload: SimilarityAnalyzePayload = {
      extensions,
      type3: type3Enabled,
      exclude_patterns: excludePatterns.length > 0 ? excludePatterns : null,
    };
    analyze(payload);
  };

  const toggleExtension = (ext: string) => {
    setExtensions((prev) =>
      prev.includes(ext) ? prev.filter((e) => e !== ext) : [...prev, ext]
    );
  };

  const toggleAllExtensions = () => {
    if (extensions.length === availableExtensions.length) {
      setExtensions([]);
    } else {
      setExtensions([...availableExtensions]);
    }
  };

  const removePattern = (pattern: string) => {
    setExcludePatterns((prev) => prev.filter((p) => p !== pattern));
  };

  const addPattern = () => {
    const trimmed = newPattern.trim();
    if (trimmed && !excludePatterns.includes(trimmed)) {
      setExcludePatterns((prev) => [...prev, trimmed]);
      setNewPattern("");
    }
  };

  const resetPatterns = () => {
    setExcludePatterns(defaultPatterns);
  };

  const availableExtensions = [".py", ".js", ".ts", ".jsx", ".tsx", ".c", ".cpp", ".h", ".hpp"];

  return (
    <div className="similarity-dashboard">
      {/* Controls Section */}
      <section className="similarity-controls">
        <div className="similarity-controls__row">
          <div className="similarity-controls__group">
            <div className="similarity-controls__label-row">
              <label className="similarity-controls__label">File Extensions</label>
              <button
                className="similarity-select-all-btn"
                onClick={toggleAllExtensions}
                title={extensions.length === availableExtensions.length ? "Deselect all" : "Select all"}
              >
                {extensions.length === availableExtensions.length ? "None" : "All"}
              </button>
            </div>
            <div className="similarity-controls__extensions">
              {availableExtensions.map((ext) => (
                <button
                  key={ext}
                  className={`similarity-ext-btn ${extensions.includes(ext) ? "active" : ""}`}
                  onClick={() => toggleExtension(ext)}
                >
                  {ext}
                </button>
              ))}
            </div>
          </div>

          <div className="similarity-controls__group">
            <label className="similarity-controls__checkbox">
              <input
                type="checkbox"
                checked={type3Enabled}
                onChange={(e) => setType3Enabled(e.target.checked)}
              />
              <span>Enable Type-3 Detection</span>
            </label>
            <span className="similarity-controls__hint">
              Detect modified clones (slower)
            </span>
          </div>

          <button
            className="similarity-analyze-btn"
            onClick={handleAnalyze}
            disabled={isAnalyzing || extensions.length === 0}
          >
            {isAnalyzing ? "Analyzing..." : "Run Analysis"}
          </button>
        </div>

        {analyzeError && (
          <div className="similarity-error">
            Analysis failed: {String(analyzeError)}
          </div>
        )}

        {/* Exclude Patterns Section */}
        <div className="similarity-exclude-section">
          <button
            className="similarity-exclude-toggle"
            onClick={() => setShowExcludePatterns(!showExcludePatterns)}
            title="Configure which folders/files to exclude from analysis"
          >
            {showExcludePatterns ? "▼" : "▶"} Exclude Patterns ({excludePatterns.length})
          </button>

          {showExcludePatterns && (
            <div className="similarity-exclude-content">
              <div className="similarity-exclude-header">
                <span className="similarity-exclude-hint">
                  Glob patterns to exclude from analysis (e.g., **/tests/**, **/venv/**)
                </span>
                <button
                  className="similarity-exclude-reset"
                  onClick={resetPatterns}
                  title="Reset to default patterns"
                >
                  Reset to Defaults
                </button>
              </div>

              <div className="similarity-exclude-add">
                <input
                  type="text"
                  value={newPattern}
                  onChange={(e) => setNewPattern(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addPattern()}
                  placeholder="Add pattern (e.g., **/docs/**)"
                  className="similarity-exclude-input"
                />
                <button
                  className="similarity-exclude-add-btn"
                  onClick={addPattern}
                  disabled={!newPattern.trim()}
                >
                  Add
                </button>
              </div>

              <div className="similarity-exclude-list">
                {excludePatterns.map((pattern) => (
                  <div key={pattern} className="similarity-exclude-item">
                    <span className="similarity-exclude-pattern">{pattern}</span>
                    <button
                      className="similarity-exclude-remove"
                      onClick={() => removePattern(pattern)}
                      title="Remove this pattern"
                    >
                      ×
                    </button>
                  </div>
                ))}
                {excludePatterns.length === 0 && (
                  <div className="similarity-exclude-empty">
                    No exclude patterns configured. All files will be analyzed.
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Error State */}
      {isError && !report && (
        <div className="similarity-error">
          Failed to load similarity data: {String(error)}
        </div>
      )}

      {/* Two-Column Layout: Legend + Dashboard */}
      <div className="similarity-layout">
        {/* Left Column: Legend */}
        <aside className="similarity-layout__legend">
          <LegendCard />
        </aside>

        {/* Right Column: Dashboard Grid */}
        <div className="similarity-layout__main">
          <div className="similarity-grid">
            {/* Top Row: Summary + Performance */}
            <div className="similarity-grid__row similarity-grid__row--top">
              <SummaryCard
                summary={report?.summary ?? null}
                isLoading={isLoading || isAnalyzing}
              />
              <PerformanceCard
                performance={report?.performance ?? null}
                timing={report?.timing ?? null}
                isLoading={isLoading || isAnalyzing}
              />
            </div>

            {/* Hotspots Section */}
            <HotspotsCard
              hotspots={report?.hotspots ?? []}
              isLoading={isLoading || isAnalyzing}
            />

            {/* Clones Section */}
            <ClonesCard
              clones={report?.clones ?? []}
              isLoading={isLoading || isAnalyzing}
            />
          </div>
        </div>
      </div>

      {/* Metrics Summary (if available) */}
      {report?.metrics && (
        <section className="similarity-metrics-summary">
          <h3 className="similarity-metrics-summary__title">Clone Distribution</h3>
          <div className="similarity-metrics-summary__content">
            {Object.entries(report.metrics.by_type).length > 0 && (
              <div className="similarity-metrics-group">
                <h4>By Type</h4>
                <div className="similarity-metrics-list">
                  {Object.entries(report.metrics.by_type).map(([type, count]) => (
                    <div key={type} className="similarity-metric-item">
                      <span className="similarity-metric-item__label">{type}</span>
                      <span className="similarity-metric-item__value">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            {Object.entries(report.metrics.by_language).length > 0 && (
              <div className="similarity-metrics-group">
                <h4>By Language</h4>
                <div className="similarity-metrics-list">
                  {Object.entries(report.metrics.by_language).map(([lang, count]) => (
                    <div key={lang} className="similarity-metric-item">
                      <span className="similarity-metric-item__label">{lang}</span>
                      <span className="similarity-metric-item__value">{count}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
