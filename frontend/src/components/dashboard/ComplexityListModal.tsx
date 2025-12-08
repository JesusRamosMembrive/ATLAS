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
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal" style={{ width: "800px", maxWidth: "90vw", maxHeight: "85vh", display: "flex", flexDirection: "column" }} onClick={e => e.stopPropagation()}>
                <div className="modal-header">
                    <h3>Complexity Hotspots ({functions.length})</h3>
                    <button type="button" className="close-button" onClick={onClose}>×</button>
                </div>

                <div style={{ padding: "16px", borderBottom: "1px solid #1e293b" }}>
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

                <div className="modal-content" style={{ overflow: "auto", flex: 1, padding: 0 }}>
                    <table style={{ width: "100%", borderCollapse: "collapse" }}>
                        <thead style={{ position: "sticky", top: 0, background: "#1e293b", zIndex: 1 }}>
                            <tr>
                                <th style={{ padding: "12px", textAlign: "left", cursor: "pointer" }} onClick={() => handleSort("complexity")}>
                                    Level {sortField === "complexity" && (sortDesc ? "↓" : "↑")}
                                </th>
                                <th style={{ padding: "12px", textAlign: "left", cursor: "pointer" }} onClick={() => handleSort("name")}>
                                    Function {sortField === "name" && (sortDesc ? "↓" : "↑")}
                                </th>
                                <th style={{ padding: "12px", textAlign: "left", cursor: "pointer" }} onClick={() => handleSort("path")}>
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
                                    <td style={{ padding: "10px 12px", fontSize: "14px", fontWeight: 500, color: "#e2e8f0" }}>
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
                                        <div style={{ fontSize: "11px", color: "#64748b" }}>{fn.path}</div>
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
