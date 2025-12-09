import { useState } from "react";
import { useSimilarityDashboard } from "../../hooks/useSimilarityData";
import type { SimilarityAnalyzePayload } from "../../api/similarityTypes";
import { SummaryCard } from "./SummaryCard";
import { PerformanceCard } from "./PerformanceCard";
import { HotspotsCard } from "./HotspotsCard";
import { ClonesCard } from "./ClonesCard";
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
  } = useSimilarityDashboard();

  // Analysis options state
  const [extensions, setExtensions] = useState<string[]>([".py"]);
  const [type3Enabled, setType3Enabled] = useState(false);

  const handleAnalyze = () => {
    const payload: SimilarityAnalyzePayload = {
      extensions,
      type3: type3Enabled,
    };
    analyze(payload);
  };

  const toggleExtension = (ext: string) => {
    setExtensions((prev) =>
      prev.includes(ext) ? prev.filter((e) => e !== ext) : [...prev, ext]
    );
  };

  const availableExtensions = [".py", ".js", ".ts", ".jsx", ".tsx"];

  return (
    <div className="similarity-dashboard">
      {/* Controls Section */}
      <section className="similarity-controls">
        <div className="similarity-controls__row">
          <div className="similarity-controls__group">
            <label className="similarity-controls__label">File Extensions</label>
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
      </section>

      {/* Error State */}
      {isError && !report && (
        <div className="similarity-error">
          Failed to load similarity data: {String(error)}
        </div>
      )}

      {/* Dashboard Grid */}
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
