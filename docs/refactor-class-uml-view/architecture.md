# Architecture Plan: ClassUMLView Refactor

## Context & Requirements
**Goal**: Deconstruct the "God Component" `ClassUMLView.tsx` (1500+ lines) into manageable, single-purpose sub-components to improve maintainability and readability.
**Problem**: The current component handles UI rendering, complex state management, graph algorithm parameters, and styling constants in a single file.

## Stage Assessment
**Current Stage**: 2 (Prototype/Production mix)
**Refactor Type**: Structural Cleanup (No logical changes intended).

## Component Structure
We will create a new directory `frontend/src/components/uml/` to house the extracted components.

### 1. New File Structure
```
frontend/src/components/uml/
├── types.ts                # Shared types (GraphvizFormState) and constants
├── UmlSearch.tsx           # Search bar specific to UML
├── UmlControls.tsx         # Toolbar (Zoom, Filters, Prefixes)
├── UmlLegend.tsx           # Static SVG Legend
├── GraphvizSidebar.tsx     # The complex settings sidebar
└── UmlCanvas.tsx           # Wrapper for the SVG display
```

### 2. Component Responsibility
- **`types.ts`**:
    - `GraphvizFormState` definition.
    - `DEFAULT_GRAPHVIZ_FORM`.
    - `RELATION_META` and other constants.
- **`UmlSearch.tsx`**:
    - Props: `searchTerm`, `onSearchChange`, `results`, `onSelect`.
- **`UmlControls.tsx`**:
    - Props: `prefixInput`, `onPrefixChange`, `includeExternal`, `onToggleExternal`, `edgeTypes`, `onToggleEdgeType`, `zoom`, `onZoomChange`.
- **`UmlLegend.tsx`**:
    - Stateless (or simple props if we make it dynamic later).
- **`GraphvizSidebar.tsx`**:
    - Props: `formState`, `onChange`, `onReset`, `isOpen`, `onToggle`.
    - Handles the rendering of all the settings inputs.
- **`ClassUMLView.tsx` (Main)**:
    - Retains the "Smart" container role.
    - Manages `useState` and `useQuery`.
    - Passes state down to the dumb components.

## Testing Strategy
- **Manual Verification**: Since this is a refactor without logic changes, the primary test is to ensure the UI behaves exactly as before.
- **Regression Testing**: Check that:
    1. The graph generates correctly.
    2. Filters work.
    3. The sidebar updates the graph style.
    4. Search finds classes.

## Execution Plan
1. Create `frontend/src/components/uml/types.ts` and move types/constants.
2. Create `GraphvizSidebar.tsx` (largest chunk).
3. Create `UmlLegend.tsx` and `UmlSearch.tsx`.
4. Create `UmlControls.tsx`.
5. Create `UmlCanvas.tsx`.
6. Update `ClassUMLView.tsx` to import and usage these new components.
7. Verify application runs without errors.
