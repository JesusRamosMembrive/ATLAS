import { DESIGN_TOKENS } from "../../theme/designTokens";

export function UmlLegend(): JSX.Element {
    return (
        <section className="uml-legend" aria-label="Relationship legend">
            <h3>Legend</h3>
            <div className="legend-items">
                <div className="legend-item">
                    <svg width="40" height="20" viewBox="0 0 40 20">
                        <line
                            x1="0"
                            y1="10"
                            x2="40"
                            y2="10"
                            stroke={DESIGN_TOKENS.colors.relationships.inheritance}
                            strokeWidth="2"
                            markerEnd="url(#arrow-inheritance)"
                        />
                        <defs>
                            <marker
                                id="arrow-inheritance"
                                markerWidth="10"
                                markerHeight="10"
                                refX="9"
                                refY="3"
                                orient="auto"
                            >
                                <path d="M0,0 L0,6 L9,3 z" fill={DESIGN_TOKENS.colors.relationships.inheritance} />
                            </marker>
                        </defs>
                    </svg>
                    <span>Inheritance (extends)</span>
                </div>
                <div className="legend-item">
                    <svg width="40" height="20" viewBox="0 0 40 20">
                        <line
                            x1="0"
                            y1="10"
                            x2="40"
                            y2="10"
                            stroke={DESIGN_TOKENS.colors.relationships.association}
                            strokeWidth="2"
                            strokeDasharray="5,3"
                        />
                    </svg>
                    <span>Association (uses)</span>
                </div>
                <div className="legend-item">
                    <svg width="40" height="20" viewBox="0 0 40 20">
                        <line
                            x1="0"
                            y1="10"
                            x2="40"
                            y2="10"
                            stroke={DESIGN_TOKENS.colors.relationships.instantiation}
                            strokeWidth="2"
                            strokeDasharray="5,3"
                        />
                    </svg>
                    <span>Instantiation (creates)</span>
                </div>
                <div className="legend-item">
                    <svg width="40" height="20" viewBox="0 0 40 20">
                        <line
                            x1="0"
                            y1="10"
                            x2="40"
                            y2="10"
                            stroke={DESIGN_TOKENS.colors.relationships.reference}
                            strokeWidth="1.5"
                            strokeDasharray="2,2"
                        />
                    </svg>
                    <span>References (refers)</span>
                </div>
            </div>
        </section>
    );
}
