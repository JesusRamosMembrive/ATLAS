import { DESIGN_TOKENS } from "../../theme/designTokens";
import { UML_ZOOM_MAX, UML_ZOOM_MIN, UML_ZOOM_STEP } from "./types";

interface UmlControlsProps {
    prefixInput: string;
    onPrefixChange: (value: string) => void;
    includeExternal: boolean;
    onToggleExternal: () => void;
    edgeTypes: Set<string>;
    onToggleEdgeType: (type: string) => void;
    zoom: number;
    onZoomChange: (value: number) => void;
    onResetZoom: () => void;
    canResetZoom: boolean;
    onRegenerate: () => void;
    isRegenerating: boolean;
    isSidebarOpen: boolean;
    onToggleSidebar: () => void;
}

export function UmlControls({
    prefixInput,
    onPrefixChange,
    includeExternal,
    onToggleExternal,
    edgeTypes,
    onToggleEdgeType,
    zoom,
    onZoomChange,
    onResetZoom,
    canResetZoom,
    onRegenerate,
    isRegenerating,
    isSidebarOpen,
    onToggleSidebar,
}: UmlControlsProps): JSX.Element {
    const clamp = (value: number, min: number, max: number) => Math.min(max, Math.max(min, value));

    return (
        <section className="uml-controls">
            <div className="control-block">
                <h2>Module prefixes</h2>
                <input
                    type="text"
                    className="uml-filter-input"
                    value={prefixInput}
                    onChange={(event) => onPrefixChange(event.target.value)}
                    placeholder="E.g. api, src"
                    aria-label="Filter by module prefixes (comma separated)"
                />
            </div>

            <label className="control-checkbox">
                <input type="checkbox" checked={includeExternal} onChange={onToggleExternal} />
                <span>Include external classes</span>
            </label>

            <div className="control-block">
                <h2>Relationship types</h2>
                <div className="control-row">
                    <label className="control-checkbox">
                        <input
                            type="checkbox"
                            checked={edgeTypes.has("inheritance")}
                            onChange={() => onToggleEdgeType("inheritance")}
                        />
                        <span style={{ color: DESIGN_TOKENS.colors.relationships.inheritance }}>Inheritance</span>
                    </label>
                    <label className="control-checkbox">
                        <input
                            type="checkbox"
                            checked={edgeTypes.has("association")}
                            onChange={() => onToggleEdgeType("association")}
                        />
                        <span style={{ color: DESIGN_TOKENS.colors.relationships.association }}>Association</span>
                    </label>
                    <label className="control-checkbox">
                        <input
                            type="checkbox"
                            checked={edgeTypes.has("instantiation")}
                            onChange={() => onToggleEdgeType("instantiation")}
                        />
                        <span style={{ color: DESIGN_TOKENS.colors.relationships.instantiation }}>Instantiation</span>
                    </label>
                    <label className="control-checkbox">
                        <input
                            type="checkbox"
                            checked={edgeTypes.has("reference")}
                            onChange={() => onToggleEdgeType("reference")}
                        />
                        <span style={{ color: DESIGN_TOKENS.colors.relationships.reference }}>References</span>
                    </label>
                </div>
            </div>

            <div className="uml-zoom-control">
                <label htmlFor="uml-zoom-slider">Zoom</label>
                <input
                    id="uml-zoom-slider"
                    type="range"
                    min={UML_ZOOM_MIN}
                    max={UML_ZOOM_MAX}
                    step={UML_ZOOM_STEP}
                    value={zoom}
                    onChange={(event) => {
                        const value = clamp(Number(event.target.value), UML_ZOOM_MIN, UML_ZOOM_MAX);
                        onZoomChange(value);
                    }}
                />
                <div className="uml-zoom-indicator">
                    <span>{Math.round(zoom * 100)}%</span>
                    <button
                        type="button"
                        className="link-btn"
                        onClick={onResetZoom}
                        disabled={!canResetZoom}
                    >
                        Reset
                    </button>
                </div>
            </div>

            <button
                className="secondary-btn"
                type="button"
                onClick={onRegenerate}
                disabled={isRegenerating}
            >
                {isRegenerating ? "Refreshing…" : "Regenerate"}
            </button>

            <button
                className="secondary-btn"
                type="button"
                onClick={onToggleSidebar}
                aria-label={isSidebarOpen ? "Hide Graphviz options" : "Show Graphviz options"}
            >
                {isSidebarOpen ? "Hide Options" : "Show Options"}
            </button>
        </section>
    );
}
