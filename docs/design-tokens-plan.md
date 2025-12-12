# Design Token Implementation Plan

## Goal
Replace hardcoded "magic" hex color values in the Frontend and styles with a centralized Design Token system. This will ensure consistency and make theming easier.

## Strategy
1.  **Define Tokens (TypeScript)**: Create a single source of truth for the color palette in TypeScript. This is necessary because the Graphviz types in `types.ts` require Hex strings (for `<input type="color">` binding), so we cannot solely rely on CSS variables there.
2.  **Define Tokens (CSS)**: Map these same colors to CSS Custom Properties (Variables) in `base.css` for use in stylesheets.
3.  **Refactor Code**: Update `types.ts`, `UmlControls.tsx`, `UmlLegend.tsx`, `UmlStats` (in `ClassUMLView.tsx` logic) to use the TS tokens.
4.  **Refactor CSS**: Update `uml.css` to use the CSS variables.

## Token Structure (`designTokens.ts`)
```typescript
export const TOKENS = {
  colors: {
    primary: "#3b82f6", // blue-500
    background: "#0b1120", // slate-950
    text: {
      main: "#f8fafc", // slate-50
      muted: "#94a3b8", // slate-400
    },
    relationships: {
      inheritance: "#60a5fa", // blue-400
      association: "#f97316", // orange-500
      instantiation: "#10b981", // emerald-500
      reference: "#a855f7",   // purple-500
    },
    // ... others extracted from UML file
  }
}
```

## CSS Mapping (`base.css`)
```css
:root {
  --color-primary: #3b82f6;
  --color-rel-inheritance: #60a5fa;
  /* ... */
}
```

## Files to Modify
- `frontend/src/theme/designTokens.ts` (NEW)
- `frontend/src/styles/base.css` (Update)
- `frontend/src/components/uml/types.ts` (Refactor)
- `frontend/src/components/uml/UmlControls.tsx` (Refactor)
- `frontend/src/components/uml/UmlLegend.tsx` (Refactor)
- `frontend/src/components/ClassUMLView.tsx` (Refactor - for stats colors)
- `frontend/src/styles/uml.css` (Refactor)
