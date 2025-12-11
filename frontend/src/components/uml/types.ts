import type { GraphvizOptionsPayload } from "../../api/types";

export const DEFAULT_PREFIXES = "";
export const UML_ZOOM_MIN = 0.05;
export const UML_ZOOM_MAX = 4;
export const UML_ZOOM_STEP = 0.05;

export type GraphvizFormState = {
    layoutEngine: string;
    rankdir: string;
    splines: string;
    nodesep: string;
    ranksep: string;
    pad: string;
    margin: string;
    bgcolor: string;
    graphFontname: string;
    graphFontsize: string;
    nodeShape: string;
    nodeStyle: string;
    nodeFillcolor: string;
    nodeColor: string;
    nodeFontcolor: string;
    nodeFontname: string;
    nodeFontsize: string;
    nodeWidth: string;
    nodeHeight: string;
    nodeMarginX: string;
    nodeMarginY: string;
    edgeColor: string;
    edgeFontname: string;
    edgeFontsize: string;
    edgePenwidth: string;
    inheritanceStyle: string;
    inheritanceColor: string;
    associationColor: string;
    instantiationColor: string;
    referenceColor: string;
    inheritanceArrowhead: string;
    associationArrowhead: string;
    instantiationArrowhead: string;
    referenceArrowhead: string;
    associationStyle: string;
    instantiationStyle: string;
    referenceStyle: string;
};

export const DEFAULT_GRAPHVIZ_FORM: GraphvizFormState = {
    layoutEngine: "dot",
    rankdir: "LR",
    splines: "true",
    nodesep: "0.6",
    ranksep: "1.1",
    pad: "0.3",
    margin: "0",
    bgcolor: "#0b1120",
    graphFontname: "Inter",
    graphFontsize: "11",
    nodeShape: "box",
    nodeStyle: "rounded,filled",
    nodeFillcolor: "#111827",
    nodeColor: "#1f2937",
    nodeFontcolor: "#e2e8f0",
    nodeFontname: "Inter",
    nodeFontsize: "11",
    nodeWidth: "1.6",
    nodeHeight: "0.6",
    nodeMarginX: "0.12",
    nodeMarginY: "0.06",
    edgeColor: "#475569",
    edgeFontname: "Inter",
    edgeFontsize: "9",
    edgePenwidth: "1",
    inheritanceStyle: "solid",
    inheritanceColor: "#60a5fa",
    associationColor: "#f97316",
    instantiationColor: "#10b981",
    referenceColor: "#a855f7",
    inheritanceArrowhead: "empty",
    associationArrowhead: "normal",
    instantiationArrowhead: "diamond",
    referenceArrowhead: "vee",
    associationStyle: "dashed",
    instantiationStyle: "dashed",
    referenceStyle: "dotted",
};

export const GRAPHVIZ_LAYOUT_ENGINES = ["dot", "neato", "fdp", "sfdp", "circo", "twopi"];
export const GRAPHVIZ_RANKDIRS = ["LR", "RL", "TB", "BT"];
export const GRAPHVIZ_SPLINES = ["true", "false", "polyline", "line", "spline", "curved", "ortho"];
export const GRAPHVIZ_NODE_SHAPES = ["box", "rect", "ellipse", "record", "plaintext", "component", "cylinder", "tab"];
export const GRAPHVIZ_ARROWHEADS = ["normal", "empty", "vee", "diamond", "dot", "obox"];
export const GRAPHVIZ_EDGE_STYLES = ["solid", "dashed", "dotted", "bold", "invis"];

export const RELATION_META = [
    {
        key: "inheritance",
        label: "Inheritance",
        helper: "Extends",
        colorKey: "inheritanceColor",
        arrowKey: "inheritanceArrowhead",
        styleKey: "inheritanceStyle",
    },
    {
        key: "association",
        label: "Association",
        helper: "Uses",
        colorKey: "associationColor",
        arrowKey: "associationArrowhead",
        styleKey: "associationStyle",
    },
    {
        key: "instantiation",
        label: "Instantiation",
        helper: "Creates",
        colorKey: "instantiationColor",
        arrowKey: "instantiationArrowhead",
        styleKey: "instantiationStyle",
    },
    {
        key: "reference",
        label: "Reference",
        helper: "Type hints",
        colorKey: "referenceColor",
        arrowKey: "referenceArrowhead",
        styleKey: "referenceStyle",
    },
] as const satisfies ReadonlyArray<{
    key: "inheritance" | "association" | "instantiation" | "reference";
    label: string;
    helper: string;
    colorKey: keyof GraphvizFormState;
    arrowKey: keyof GraphvizFormState;
    styleKey: keyof GraphvizFormState;
}>;

export interface UmlSvgHandle {
    setZoom: (value: number) => void;
    resetView: () => void;
}

export interface UmlViewState {
    zoom: number;
}

export function graphvizFormToPayload(form: GraphvizFormState): GraphvizOptionsPayload {
    return {
        layoutEngine: form.layoutEngine,
        rankdir: form.rankdir,
        splines: form.splines,
        nodesep: parseFloat(form.nodesep),
        ranksep: parseFloat(form.ranksep),
        pad: parseFloat(form.pad),
        margin: parseFloat(form.margin),
        bgcolor: form.bgcolor,
        graphFontname: form.graphFontname,
        graphFontsize: parseFloat(form.graphFontsize),
        nodeShape: form.nodeShape,
        nodeStyle: form.nodeStyle,
        nodeFillcolor: form.nodeFillcolor,
        nodeColor: form.nodeColor,
        nodeFontcolor: form.nodeFontcolor,
        nodeFontname: form.nodeFontname,
        nodeFontsize: parseFloat(form.nodeFontsize),
        nodeWidth: parseFloat(form.nodeWidth),
        nodeHeight: parseFloat(form.nodeHeight),
        nodeMarginX: parseFloat(form.nodeMarginX),
        nodeMarginY: parseFloat(form.nodeMarginY),
        edgeColor: form.edgeColor,
        edgeFontname: form.edgeFontname,
        edgeFontsize: parseFloat(form.edgeFontsize),
        edgePenwidth: parseFloat(form.edgePenwidth),
        inheritanceStyle: form.inheritanceStyle,
        inheritanceColor: form.inheritanceColor,
        inheritanceArrowhead: form.inheritanceArrowhead,
        associationStyle: form.associationStyle,
        associationColor: form.associationColor,
        associationArrowhead: form.associationArrowhead,
        instantiationStyle: form.instantiationStyle,
        instantiationColor: form.instantiationColor,
        instantiationArrowhead: form.instantiationArrowhead,
        referenceStyle: form.referenceStyle,
        referenceColor: form.referenceColor,
        referenceArrowhead: form.referenceArrowhead,
    };
}
