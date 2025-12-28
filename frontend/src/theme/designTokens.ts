export const DESIGN_TOKENS = {
    colors: {
        base: {
            background: "#0b1120", // The main bg color found in DEFAULT_GRAPHVIZ_FORM
            dark: "#0c0e15", // Body bg
            panel: "#0f172a", // 'slate-900' equivalent often used
            card: "#1e293b", // Card/sidebar background
        },
        text: {
            main: "#f8fafc", // 'slate-50'
            muted: "#94a3b8", // 'slate-400'
            header: "#cbd5f5",
            secondary: "#f1f5f9", // slate-100
        },
        primary: {
            main: "#3b82f6", // 'blue-500'
            light: "#60a5fa", // 'blue-400'
            dark: "#1d4ed8", // 'blue-700'
        },
        gray: {
            300: "#e2e8f0",
            400: "#94a3b8",
            500: "#64748b",
            600: "#475569",
            700: "#334155",
            800: "#1f2937",
            900: "#111827",
        },
        relationships: {
            inheritance: "#60a5fa", // blue-400
            association: "#f97316", // orange-500
            instantiation: "#10b981", // emerald-500
            reference: "#a855f7", // purple-500
        },
        // Call Flow specific colors
        callFlow: {
            // Node kinds
            function: "#3b82f6", // blue-500
            method: "#10b981", // emerald-500
            external: "#6b7280", // gray-500
            builtin: "#f59e0b", // amber-500
            class: "#a855f7", // purple-500
            // Edge/call types
            direct: "#3b82f6", // blue-500
            methodCall: "#10b981", // emerald-500
            superCall: "#f59e0b", // amber-500
            staticCall: "#a855f7", // purple-500
            // UI elements
            entryPoint: "#f59e0b", // amber-500
            edgeLabel: "#94a3b8", // gray-400
            // Decision nodes
            decision: "#ec4899", // pink-500
            decisionBorder: "#f472b6", // pink-400
            // Branch types
            branchTrue: "#10b981", // emerald-500
            branchFalse: "#ef4444", // red-500
            branchCase: "#8b5cf6", // violet-500
            branchExcept: "#f97316", // orange-500
            branchExpanded: "#22c55e", // green-500
            branchUnexpanded: "#6b7280", // gray-500
        },
        // Complexity thresholds (same as ComplexityCard)
        complexity: {
            low: "#4ade80", // green-400
            medium: "#facc15", // yellow-400
            high: "#fb923c", // orange-400
            extreme: "#f87171", // red-400
        },
        // Severity colors for badges
        severity: {
            info: "#3b82f6", // blue-500
            warning: "#f59e0b", // amber-500
            danger: "#dc2626", // red-600
        },
        // Contrast colors for text on colored backgrounds
        contrast: {
            light: "#fff", // white text on dark backgrounds
            dark: "#000", // black text on light backgrounds
        },
    },
    borders: {
        default: "#334155", // gray-700
    },
} as const;

// Type exports for consuming components
export type DesignTokens = typeof DESIGN_TOKENS;
export type CallFlowKind = keyof typeof DESIGN_TOKENS.colors.callFlow;
