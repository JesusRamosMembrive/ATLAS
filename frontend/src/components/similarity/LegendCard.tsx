/**
 * LegendCard - Explanations for similarity analysis concepts
 */

export function LegendCard(): JSX.Element {
  return (
    <div className="similarity-card similarity-legend">
      <div className="similarity-card__header">
        <h3 className="similarity-card__title">Legend</h3>
      </div>

      <div className="similarity-legend__content">
        {/* Clone Types */}
        <section className="similarity-legend__section">
          <h4 className="similarity-legend__section-title">Clone Types</h4>

          <div className="similarity-legend__item">
            <span className="similarity-clone-badge similarity-clone-badge--exact">Type-1</span>
            <p className="similarity-legend__desc">
              <strong>Exact clones.</strong> Identical code fragments, differing only in whitespace or comments.
            </p>
          </div>

          <div className="similarity-legend__item">
            <span className="similarity-clone-badge similarity-clone-badge--renamed">Type-2</span>
            <p className="similarity-legend__desc">
              <strong>Renamed clones.</strong> Identical structure but with renamed variables, types, or literals.
            </p>
          </div>

          <div className="similarity-legend__item">
            <span className="similarity-clone-badge similarity-clone-badge--modified">Type-3</span>
            <p className="similarity-legend__desc">
              <strong>Modified clones.</strong> Similar code with added, removed, or modified statements. Requires "Enable Type-3 Detection".
            </p>
          </div>
        </section>

        {/* Metrics Explanation */}
        <section className="similarity-legend__section">
          <h4 className="similarity-legend__section-title">Metrics</h4>

          <div className="similarity-legend__item">
            <span className="similarity-legend__term">Duplication %</span>
            <p className="similarity-legend__desc">
              Percentage of total code lines that appear in at least one clone pair.
            </p>
          </div>

          <div className="similarity-legend__item">
            <span className="similarity-legend__term">Clone Pairs</span>
            <p className="similarity-legend__desc">
              Number of detected duplicate code regions. Each pair links two similar code fragments.
            </p>
          </div>

          <div className="similarity-legend__item">
            <span className="similarity-legend__term">Similarity</span>
            <p className="similarity-legend__desc">
              How similar two code fragments are (0-100%). Higher values indicate more identical code.
            </p>
          </div>
        </section>

        {/* Hotspots Explanation */}
        <section className="similarity-legend__section">
          <h4 className="similarity-legend__section-title">Duplication Hotspots</h4>
          <p className="similarity-legend__desc">
            Files ranked by their <strong>duplication score</strong> — a combination of how many clones they contain and the size of those clones.
          </p>
          <p className="similarity-legend__desc similarity-legend__desc--secondary">
            High-score files are candidates for refactoring to reduce code duplication.
          </p>
        </section>

        {/* Clone Pairs Explanation */}
        <section className="similarity-legend__section">
          <h4 className="similarity-legend__section-title">Clone Pairs</h4>
          <p className="similarity-legend__desc">
            Each entry shows two code locations with similar content. Click to expand and see the actual code snippets.
          </p>
          <p className="similarity-legend__desc similarity-legend__desc--secondary">
            Consider extracting duplicated code into shared functions or modules.
          </p>
        </section>

        {/* Performance */}
        <section className="similarity-legend__section">
          <h4 className="similarity-legend__section-title">Performance</h4>

          <div className="similarity-legend__item">
            <span className="similarity-legend__term">LOC/sec</span>
            <p className="similarity-legend__desc">
              Lines of code processed per second. Higher is faster.
            </p>
          </div>

          <div className="similarity-legend__item">
            <span className="similarity-legend__term">Tokens/sec</span>
            <p className="similarity-legend__desc">
              Normalized tokens analyzed per second. Reflects actual parsing speed.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
