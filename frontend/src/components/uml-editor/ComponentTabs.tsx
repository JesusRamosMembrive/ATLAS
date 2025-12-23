/**
 * Component Tabs - Navigation between connected components
 *
 * Displays tabs for filtering the UML canvas by connected component.
 * Uses graph analysis to detect groups of related entities.
 */

import { useMemo, useCallback } from "react";
import { useUmlEditorStore } from "../../state/useUmlEditorStore";
import { findConnectedComponents, type ComponentsAnalysis } from "../../utils/graphAnalysis";
import { DESIGN_TOKENS } from "../../theme/designTokens";

const { colors, borders } = DESIGN_TOKENS;

interface TabInfo {
  id: string | null;
  name: string;
  count: number;
  isIsolated?: boolean;
}

export function ComponentTabs(): JSX.Element | null {
  const { getCurrentModule, activeComponentId, setActiveComponentId } = useUmlEditorStore();

  const currentModule = getCurrentModule();

  // Analyze connected components
  const analysis: ComponentsAnalysis | null = useMemo(() => {
    if (!currentModule) return null;
    return findConnectedComponents(currentModule);
  }, [currentModule]);

  // Build tab list
  const tabs: TabInfo[] = useMemo(() => {
    if (!analysis) return [];

    const result: TabInfo[] = [];

    // "All" tab
    result.push({
      id: null,
      name: "All",
      count: analysis.totalEntities,
    });

    // Connected component tabs
    for (const component of analysis.components) {
      result.push({
        id: component.id,
        name: component.name,
        count: component.size,
      });
    }

    // Isolated entities tab (if any)
    if (analysis.isolated && analysis.isolated.size > 0) {
      result.push({
        id: "isolated",
        name: "Isolated",
        count: analysis.isolated.size,
        isIsolated: true,
      });
    }

    return result;
  }, [analysis]);

  const handleTabClick = useCallback(
    (tabId: string | null) => {
      setActiveComponentId(tabId);
    },
    [setActiveComponentId]
  );

  // Don't render if there's only the "All" tab (no meaningful groupings)
  if (tabs.length <= 1) {
    return null;
  }

  // Don't render if total entities is small
  if (analysis && analysis.totalEntities < 3) {
    return null;
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: "4px",
        padding: "8px 16px",
        borderBottom: `1px solid ${borders.default}`,
        backgroundColor: colors.base.card,
        overflowX: "auto",
        flexShrink: 0,
      }}
    >
      <span
        style={{
          fontSize: "11px",
          color: colors.text.muted,
          marginRight: "8px",
          textTransform: "uppercase",
          letterSpacing: "0.5px",
          fontWeight: 500,
        }}
      >
        Components:
      </span>
      {tabs.map((tab) => {
        const isActive = activeComponentId === tab.id;
        return (
          <button
            key={tab.id ?? "all"}
            onClick={() => handleTabClick(tab.id)}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              borderRadius: "16px",
              border: isActive
                ? `1px solid ${colors.primary.main}`
                : `1px solid ${borders.default}`,
              backgroundColor: isActive ? colors.primary.main + "20" : "transparent",
              color: isActive ? colors.primary.main : colors.text.muted,
              fontSize: "12px",
              fontWeight: isActive ? 600 : 400,
              cursor: "pointer",
              transition: "all 0.15s ease",
              whiteSpace: "nowrap",
            }}
            title={
              tab.id === null
                ? "Show all entities"
                : tab.isIsolated
                  ? "Entities with no relationships"
                  : `Show connected group: ${tab.name}`
            }
          >
            <span>{tab.name}</span>
            <span
              style={{
                fontSize: "10px",
                padding: "1px 6px",
                borderRadius: "10px",
                backgroundColor: isActive ? colors.primary.main : borders.default,
                color: isActive ? colors.contrast.light : colors.text.muted,
                fontWeight: 500,
              }}
            >
              {tab.count}
            </span>
          </button>
        );
      })}
    </div>
  );
}
