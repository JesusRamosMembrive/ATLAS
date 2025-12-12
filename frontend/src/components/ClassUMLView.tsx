import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useClassUmlQuery, buildGraphvizSignature } from "../hooks/useClassUmlQuery";
import { DESIGN_TOKENS } from "../theme/designTokens";
import { GraphvizSidebar } from "./uml/GraphvizSidebar";
import { UmlCanvas } from "./uml/UmlCanvas";
import { UmlControls } from "./uml/UmlControls";
import { UmlLegend } from "./uml/UmlLegend";
import { UmlSearch } from "./uml/UmlSearch";
import {
  DEFAULT_GRAPHVIZ_FORM,
  DEFAULT_PREFIXES,
  type GraphvizFormState,
  type UmlSvgHandle,
  type UmlViewState,
  graphvizFormToPayload,
} from "./uml/types";

export function ClassUMLView(): JSX.Element {
  const [includeExternal, setIncludeExternal] = useState(false);
  const [prefixInput, setPrefixInput] = useState(DEFAULT_PREFIXES);
  const [zoom, setZoom] = useState(1);
  const svgHandleRef = useRef<UmlSvgHandle | null>(null);
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");
  const [graphvizForm, setGraphvizForm] = useState<GraphvizFormState>(() => ({
    ...DEFAULT_GRAPHVIZ_FORM,
  }));
  const [isGraphvizSidebarOpen, setIsGraphvizSidebarOpen] = useState(true);

  // Edge type filters - default to inheritance + association only (no clutter)
  const [edgeTypes, setEdgeTypes] = useState<Set<string>>(
    new Set(["inheritance", "association"]),
  );

  const toggleEdgeType = useCallback((type: string) => {
    setEdgeTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) {
        next.delete(type);
      } else {
        next.add(type);
      }
      return next;
    });
  }, []);

  const handleCanvasStateChange = useCallback((state: UmlViewState) => {
    setZoom((prev) => (Math.abs(prev - state.zoom) < 0.001 ? prev : state.zoom));
  }, []);

  const modulePrefixes = useMemo(
    () =>
      prefixInput
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean),
    [prefixInput],
  );

  const edgeTypesArray = useMemo(() => Array.from(edgeTypes), [edgeTypes]);
  const graphvizOptions = useMemo(() => graphvizFormToPayload(graphvizForm), [graphvizForm]);
  const graphvizSignature = useMemo(
    () => buildGraphvizSignature(graphvizOptions),
    [graphvizOptions],
  );

  const query = useClassUmlQuery({
    includeExternal,
    modulePrefixes,
    edgeTypes: edgeTypesArray,
    graphvizOptions,
    graphvizSignature,
  });
  const data = query.data;
  const classCount = data?.classCount ?? 0;
  const svgMarkup = data?.svg ?? null;
  const stats = data?.stats;
  const classes = useMemo(() => data?.classes ?? [], [data?.classes]);

  const selectedClass = useMemo(() => {
    if (!selectedClassId) return null;
    return classes.find((c) => c.id === selectedClassId) ?? null;
  }, [selectedClassId, classes]);

  // Filter classes based on search term
  const filteredClasses = useMemo(() => {
    if (!searchTerm.trim()) return [];
    const term = searchTerm.toLowerCase();
    return classes.filter(
      (c) =>
        c.name.toLowerCase().includes(term) ||
        c.module.toLowerCase().includes(term) ||
        c.file.toLowerCase().includes(term),
    );
  }, [searchTerm, classes]);

  const handleSearchSelect = useCallback((classId: string) => {
    setSelectedClassId(classId);
    setSearchTerm(""); // Clear search after selection
  }, []);

  // Handle keyboard events for accessibility
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Close panel on Escape key
      if (e.key === "Escape" && selectedClassId) {
        setSelectedClassId(null);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [selectedClassId]);

  const handleGraphvizInputChange = useCallback(
    (key: keyof GraphvizFormState, value: string) => {
      setGraphvizForm((prev) => ({ ...prev, [key]: value }));
    },
    [],
  );

  const resetGraphvizOptions = useCallback(() => {
    setGraphvizForm({ ...DEFAULT_GRAPHVIZ_FORM });
  }, []);

  const handleZoomChange = useCallback((value: number) => {
    setZoom(value);
    svgHandleRef.current?.setZoom(value);
  }, []);

  const handleResetZoom = useCallback(() => {
    svgHandleRef.current?.resetView();
    setZoom(1);
  }, []);

  return (
    <div className={`uml-view ${isGraphvizSidebarOpen ? "sidebar-open" : ""}`}>
      <div className="uml-content">
        <UmlSearch
          searchTerm={searchTerm}
          onSearchChange={setSearchTerm}
          filteredClasses={filteredClasses}
          onSelectClass={handleSearchSelect}
        />

        <UmlControls
          prefixInput={prefixInput}
          onPrefixChange={setPrefixInput}
          includeExternal={includeExternal}
          onToggleExternal={() => setIncludeExternal((prev) => !prev)}
          edgeTypes={edgeTypes}
          onToggleEdgeType={toggleEdgeType}
          zoom={zoom}
          onZoomChange={handleZoomChange}
          onResetZoom={handleResetZoom}
          canResetZoom={!!svgMarkup}
          onRegenerate={() => query.refetch()}
          isRegenerating={query.isFetching}
          isSidebarOpen={isGraphvizSidebarOpen}
          onToggleSidebar={() => setIsGraphvizSidebarOpen((prev) => !prev)}
        />

        {!query.isLoading && !query.isError && classCount > 0 && <UmlLegend />}

        {stats && !query.isLoading && !query.isError && (
          <section className="uml-stats" aria-label="UML model summary">
            <div className="uml-stat">
              <span className="uml-stat-label">Classes</span>
              <strong className="uml-stat-value">{stats.classes ?? classCount}</strong>
            </div>
            <div className="uml-stat">
              <span className="uml-stat-label">Inheritance</span>
              <strong
                className="uml-stat-value"
                style={{ color: DESIGN_TOKENS.colors.relationships.inheritance }}
              >
                {stats.inheritance_edges ?? 0}
              </strong>
            </div>
            <div className="uml-stat">
              <span className="uml-stat-label">Associations</span>
              <strong
                className="uml-stat-value"
                style={{ color: DESIGN_TOKENS.colors.relationships.association }}
              >
                {stats.association_edges ?? 0}
              </strong>
            </div>
            <div className="uml-stat">
              <span className="uml-stat-label">Instantiations</span>
              <strong
                className="uml-stat-value"
                style={{ color: DESIGN_TOKENS.colors.relationships.instantiation }}
              >
                {stats.instantiation_edges ?? 0}
              </strong>
            </div>
            <div className="uml-stat">
              <span className="uml-stat-label">References</span>
              <strong
                className="uml-stat-value"
                style={{ color: DESIGN_TOKENS.colors.relationships.reference }}
              >
                {stats.reference_edges ?? 0}
              </strong>
            </div>
          </section>
        )}

        <UmlCanvas
          isLoading={query.isLoading}
          isError={query.isError}
          error={query.error}
          classCount={classCount}
          svgMarkup={svgMarkup}
          svgHandleRef={svgHandleRef}
          onCanvasStateChange={handleCanvasStateChange}
          selectedClassId={selectedClassId}
          onNodeClick={setSelectedClassId}
          selectedClass={selectedClass}
          onCloseDetails={() => setSelectedClassId(null)}
        />
      </div>

      {isGraphvizSidebarOpen && (
        <GraphvizSidebar
          formState={graphvizForm}
          onChange={handleGraphvizInputChange}
          onReset={resetGraphvizOptions}
        />
      )}
    </div>
  );
}
