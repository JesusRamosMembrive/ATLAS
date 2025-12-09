import { useState, useMemo } from "react";

interface ProblematicFunction {
    name: string;
    complexity: number;
    path: string;
    lineno: number;
}

interface ComplexityListModalProps {
    functions: ProblematicFunction[];
    onClose: () => void;
    onNavigate: (path: string) => void;
}

export function ComplexityListModal({ functions, onClose, onNavigate }: ComplexityListModalProps): JSX.Element {
    const [sortField, setSortField] = useState<keyof ProblematicFunction>("complexity");
    const [sortDesc, setSortDesc] = useState(true);
    const [filter, setFilter] = useState("");

    const sortedFunctions = useMemo(() => {
        let result = [...functions];

        if (filter) {
            const term = filter.toLowerCase();
            result = result.filter(fn =>
                fn.name.toLowerCase().includes(term) ||
                fn.path.toLowerCase().includes(term)
            );
        }

        result.sort((a, b) => {
            const valA = a[sortField];
            const valB = b[sortField];

            if (valA < valB) return sortDesc ? 1 : -1;
            if (valA > valB) return sortDesc ? -1 : 1;
            return 0;
        });

        return result;
    }, [functions, sortField, sortDesc, filter]);

    const handleSort = (field: keyof ProblematicFunction) => {
        if (sortField === field) {
            setSortDesc(!sortDesc);
        } else {
            setSortField(field);
            setSortDesc(true);
        }
    };

    const getComplexityColor = (c: number) => {
        if (c <= 10) return "#facc15"; // Medium
        if (c <= 25) return "#fb923c"; // High
        return "#f87171"; // Extreme
    };

    return (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0, 0, 0, 0.7)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000 }} onClick={onClose}>
            <div style={{ width: "1100px", maxWidth: "95vw", maxHeight: "85vh", display: "flex", flexDirection: "column", background: "#1e293b", borderRadius: "8px", border: "1px solid #334155", boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)" }} onClick={e => e.stopPropagation()}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "16px", borderBottom: "1px solid #334155", background: "#1e293b" }}>
                    <h3 style={{ margin: 0, color: "#e2e8f0" }}>Complexity Hotspots ({functions.length})</h3>
                    <button type="button" onClick={onClose} style={{ background: "none", border: "none", color: "#94a3b8", fontSize: "24px", cursor: "pointer", padding: "0 4px" }}>×</button>
                </div>

                <div style={{ padding: "16px", borderBottom: "1px solid #334155", background: "#1e293b" }}>
                    <input
                        type="search"
                        placeholder="Filter functions..."
                        value={filter}
                        onChange={e => setFilter(e.target.value)}
                        style={{
                            width: "100%",
                            padding: "8px 12px",
                            background: "#0f172a",
                            border: "1px solid #334155",
                            borderRadius: "4px",
                            color: "#e2e8f0"
                        }}
                    />
                </div>

                <div style={{ overflow: "auto", flex: 1, padding: 0, background: "#1e293b" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", background: "#1e293b" }}>
                        <thead style={{ position: "sticky", top: 0, background: "#1e293b", zIndex: 1 }}>
                            <tr>
                                <th style={{ padding: "12px", textAlign: "left", cursor: "pointer", width: "10%" }} onClick={() => handleSort("complexity")}>
                                    Level {sortField === "complexity" && (sortDesc ? "↓" : "↑")}
                                </th>
                                <th style={{ padding: "12px", textAlign: "left", cursor: "pointer", width: "25%" }} onClick={() => handleSort("name")}>
                                    Function {sortField === "name" && (sortDesc ? "↓" : "↑")}
                                </th>
                                <th style={{ padding: "12px", textAlign: "left", cursor: "pointer", width: "65%" }} onClick={() => handleSort("path")}>
                                    Location {sortField === "path" && (sortDesc ? "↓" : "↑")}
                                </th>
                            </tr>
                        </thead>
                        <tbody>
                            {sortedFunctions.map((fn, i) => (
                                <tr key={i} style={{ borderBottom: "1px solid #1e293b" }}>
                                    <td style={{ padding: "10px 12px" }}>
                                        <span style={{
                                            display: "inline-block",
                                            padding: "2px 8px",
                                            borderRadius: "4px",
                                            background: getComplexityColor(fn.complexity) + "20",
                                            color: getComplexityColor(fn.complexity),
                                            fontWeight: 600,
                                            fontSize: "13px"
                                        }}>
                                            CCN {fn.complexity}
                                        </span>
                                    </td>
                                    <td style={{ padding: "10px 12px", fontSize: "14px", fontWeight: 500, color: "#e2e8f0", wordBreak: "break-word" }}>
                                        {fn.name}
                                    </td>
                                    <td style={{ padding: "10px 12px" }}>
                                        <button
                                            onClick={() => onNavigate(fn.path)}
                                            style={{
                                                background: "none",
                                                border: "none",
                                                color: "#60a5fa",
                                                cursor: "pointer",
                                                fontSize: "13px",
                                                textAlign: "left",
                                                padding: 0
                                            }}
                                        >
                                            {fn.path.split("/").pop()}:{fn.lineno}
                                        </button>
                                        <div style={{ fontSize: "11px", color: "#64748b", wordBreak: "break-all" }}>{fn.path}</div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {sortedFunctions.length === 0 && (
                        <div style={{ padding: "32px", textAlign: "center", color: "#64748b" }}>
                            No matches found
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
