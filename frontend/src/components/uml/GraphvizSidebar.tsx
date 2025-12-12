import {
    GRAPHVIZ_ARROWHEADS,
    GRAPHVIZ_EDGE_STYLES,
    GRAPHVIZ_LAYOUT_ENGINES,
    GRAPHVIZ_NODE_SHAPES,
    GRAPHVIZ_RANKDIRS,
    GRAPHVIZ_SPLINES,
    RELATION_META,
    type GraphvizFormState,
} from "./types";

interface GraphvizSidebarProps {
    formState: GraphvizFormState;
    onChange: (key: keyof GraphvizFormState, value: string) => void;
    onReset: () => void;
}

export function GraphvizSidebar({
    formState,
    onChange,
    onReset,
}: GraphvizSidebarProps): JSX.Element {
    return (
        <aside
            className="graphviz-sidebar"
            role="dialog"
            aria-label="Graphviz layout and styling options"
            aria-modal="false"
        >
            <div className="graphviz-header">
                <div>
                    <h2>Graphviz layout & styling</h2>
                    <p>
                        Adjust the rendering engine, spacing, palette, and edge styles before regenerating the
                        SVG.
                    </p>
                </div>
                <button type="button" className="link-btn" onClick={onReset}>
                    Reset styling
                </button>
            </div>

            <div className="graphviz-groups">
                <div className="graphviz-group">
                    <h3>Layout</h3>
                    <div className="graphviz-grid">
                        <label className="graphviz-field">
                            <span>Engine</span>
                            <select
                                value={formState.layoutEngine}
                                onChange={(event) => onChange("layoutEngine", event.target.value)}
                            >
                                {GRAPHVIZ_LAYOUT_ENGINES.map((engine) => (
                                    <option key={engine} value={engine}>
                                        {engine.toUpperCase()}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label className="graphviz-field">
                            <span>Rank direction</span>
                            <select
                                value={formState.rankdir}
                                onChange={(event) => onChange("rankdir", event.target.value)}
                            >
                                {GRAPHVIZ_RANKDIRS.map((dir) => (
                                    <option key={dir} value={dir}>
                                        {dir}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label className="graphviz-field">
                            <span>Splines</span>
                            <select
                                value={formState.splines}
                                onChange={(event) => onChange("splines", event.target.value)}
                            >
                                {GRAPHVIZ_SPLINES.map((mode) => (
                                    <option key={mode} value={mode}>
                                        {mode}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label className="graphviz-field">
                            <span>Node spacing</span>
                            <input
                                type="number"
                                min={0.1}
                                max={5}
                                step={0.1}
                                value={formState.nodesep}
                                onChange={(event) => onChange("nodesep", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Rank spacing</span>
                            <input
                                type="number"
                                min={0.4}
                                max={8}
                                step={0.1}
                                value={formState.ranksep}
                                onChange={(event) => onChange("ranksep", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Padding</span>
                            <input
                                type="number"
                                min={0}
                                max={5}
                                step={0.1}
                                value={formState.pad}
                                onChange={(event) => onChange("pad", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Margin</span>
                            <input
                                type="number"
                                min={0}
                                max={5}
                                step={0.1}
                                value={formState.margin}
                                onChange={(event) => onChange("margin", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Background</span>
                            <div className="graphviz-color-input">
                                <input
                                    type="color"
                                    value={formState.bgcolor}
                                    aria-label="Pick background color"
                                    onChange={(event) => onChange("bgcolor", event.target.value)}
                                />
                                <input
                                    type="text"
                                    value={formState.bgcolor}
                                    onChange={(event) => onChange("bgcolor", event.target.value)}
                                />
                            </div>
                        </label>

                        <label className="graphviz-field">
                            <span>Graph font</span>
                            <input
                                type="text"
                                value={formState.graphFontname}
                                onChange={(event) => onChange("graphFontname", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Graph font size</span>
                            <input
                                type="number"
                                min={6}
                                max={32}
                                step={1}
                                value={formState.graphFontsize}
                                onChange={(event) => onChange("graphFontsize", event.target.value)}
                            />
                        </label>
                    </div>
                </div>

                <div className="graphviz-group">
                    <h3>Nodes</h3>
                    <div className="graphviz-grid">
                        <label className="graphviz-field">
                            <span>Shape</span>
                            <select
                                value={formState.nodeShape}
                                onChange={(event) => onChange("nodeShape", event.target.value)}
                            >
                                {GRAPHVIZ_NODE_SHAPES.map((shape) => (
                                    <option key={shape} value={shape}>
                                        {shape}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label className="graphviz-field">
                            <span>Style</span>
                            <input
                                type="text"
                                value={formState.nodeStyle}
                                onChange={(event) => onChange("nodeStyle", event.target.value)}
                                placeholder="rounded,filled"
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Fill</span>
                            <div className="graphviz-color-input">
                                <input
                                    type="color"
                                    value={formState.nodeFillcolor}
                                    aria-label="Pick node fill color"
                                    onChange={(event) => onChange("nodeFillcolor", event.target.value)}
                                />
                                <input
                                    type="text"
                                    value={formState.nodeFillcolor}
                                    onChange={(event) => onChange("nodeFillcolor", event.target.value)}
                                />
                            </div>
                        </label>

                        <label className="graphviz-field">
                            <span>Border</span>
                            <div className="graphviz-color-input">
                                <input
                                    type="color"
                                    value={formState.nodeColor}
                                    aria-label="Pick node border color"
                                    onChange={(event) => onChange("nodeColor", event.target.value)}
                                />
                                <input
                                    type="text"
                                    value={formState.nodeColor}
                                    onChange={(event) => onChange("nodeColor", event.target.value)}
                                />
                            </div>
                        </label>

                        <label className="graphviz-field">
                            <span>Text color</span>
                            <div className="graphviz-color-input">
                                <input
                                    type="color"
                                    value={formState.nodeFontcolor}
                                    aria-label="Pick node text color"
                                    onChange={(event) => onChange("nodeFontcolor", event.target.value)}
                                />
                                <input
                                    type="text"
                                    value={formState.nodeFontcolor}
                                    onChange={(event) => onChange("nodeFontcolor", event.target.value)}
                                />
                            </div>
                        </label>

                        <label className="graphviz-field">
                            <span>Node font</span>
                            <input
                                type="text"
                                value={formState.nodeFontname}
                                onChange={(event) => onChange("nodeFontname", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Node font size</span>
                            <input
                                type="number"
                                min={6}
                                max={32}
                                step={1}
                                value={formState.nodeFontsize}
                                onChange={(event) => onChange("nodeFontsize", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Min width</span>
                            <input
                                type="number"
                                min={0.2}
                                max={6}
                                step={0.1}
                                value={formState.nodeWidth}
                                onChange={(event) => onChange("nodeWidth", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Min height</span>
                            <input
                                type="number"
                                min={0.2}
                                max={6}
                                step={0.1}
                                value={formState.nodeHeight}
                                onChange={(event) => onChange("nodeHeight", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Margin X</span>
                            <input
                                type="number"
                                min={0.02}
                                max={1}
                                step={0.01}
                                value={formState.nodeMarginX}
                                onChange={(event) => onChange("nodeMarginX", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Margin Y</span>
                            <input
                                type="number"
                                min={0.02}
                                max={1}
                                step={0.01}
                                value={formState.nodeMarginY}
                                onChange={(event) => onChange("nodeMarginY", event.target.value)}
                            />
                        </label>
                    </div>
                </div>

                <div className="graphviz-group">
                    <h3>Edges & relationships</h3>
                    <div className="graphviz-grid">
                        <label className="graphviz-field">
                            <span>Default edge color</span>
                            <div className="graphviz-color-input">
                                <input
                                    type="color"
                                    value={formState.edgeColor}
                                    aria-label="Pick edge color"
                                    onChange={(event) => onChange("edgeColor", event.target.value)}
                                />
                                <input
                                    type="text"
                                    value={formState.edgeColor}
                                    onChange={(event) => onChange("edgeColor", event.target.value)}
                                />
                            </div>
                        </label>

                        <label className="graphviz-field">
                            <span>Edge font</span>
                            <input
                                type="text"
                                value={formState.edgeFontname}
                                onChange={(event) => onChange("edgeFontname", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Edge font size</span>
                            <input
                                type="number"
                                min={6}
                                max={24}
                                step={1}
                                value={formState.edgeFontsize}
                                onChange={(event) => onChange("edgeFontsize", event.target.value)}
                            />
                        </label>

                        <label className="graphviz-field">
                            <span>Stroke width</span>
                            <input
                                type="number"
                                min={0.5}
                                max={4}
                                step={0.1}
                                value={formState.edgePenwidth}
                                onChange={(event) => onChange("edgePenwidth", event.target.value)}
                            />
                        </label>
                    </div>

                    <div className="graphviz-relations">
                        {RELATION_META.map(({ key, label, helper, colorKey, arrowKey, styleKey }) => (
                            <div key={key} className="graphviz-relation-row">
                                <div className="graphviz-relation-label">
                                    <span>{label}</span>
                                    <small>{helper}</small>
                                </div>
                                <div className="graphviz-relation-controls">
                                    <label>
                                        <span>Color</span>
                                        <div className="graphviz-color-input">
                                            <input
                                                type="color"
                                                value={formState[colorKey]}
                                                aria-label={`Pick ${label} color`}
                                                onChange={(event) => onChange(colorKey, event.target.value)}
                                            />
                                            <input
                                                type="text"
                                                value={formState[colorKey]}
                                                onChange={(event) => onChange(colorKey, event.target.value)}
                                            />
                                        </div>
                                    </label>

                                    <label>
                                        <span>Arrowhead</span>
                                        <select
                                            value={formState[arrowKey]}
                                            onChange={(event) => onChange(arrowKey, event.target.value)}
                                        >
                                            {GRAPHVIZ_ARROWHEADS.map((arrow) => (
                                                <option key={arrow} value={arrow}>
                                                    {arrow}
                                                </option>
                                            ))}
                                        </select>
                                    </label>

                                    <label>
                                        <span>Line style</span>
                                        <select
                                            value={formState[styleKey]}
                                            onChange={(event) => onChange(styleKey, event.target.value)}
                                        >
                                            {GRAPHVIZ_EDGE_STYLES.map((style) => (
                                                <option key={style} value={style}>
                                                    {style}
                                                </option>
                                            ))}
                                        </select>
                                    </label>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>
        </aside>
    );
}
