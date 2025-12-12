export const DESIGN_TOKENS = {
    colors: {
        base: {
            background: "#0b1120", // The main bg color found in DEFAULT_GRAPHVIZ_FORM
            dark: "#0c0e15", // Body bg
            panel: "#0f172a", // 'slate-900' equivalent often used
        },
        text: {
            main: "#f8fafc", // 'slate-50'
            muted: "#94a3b8", // 'slate-400'
            header: "#cbd5f5",
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
    },
} as const;
