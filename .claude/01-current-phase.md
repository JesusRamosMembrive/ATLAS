# Estado Actual del Proyecto

**Última actualización**: 2025-12-23
**Etapa detectada**: Stage 3 (High Confidence)
**Versión**: AEGIS v2

---

## 📍 ESTADO ACTUAL

**En progreso:**
- **UML Editor (AEGIS v2)** - Phase 5 pendiente (Agent Loop integration)

**Completado recientemente:**
- **Ollama XML Guide** (2025-12-23)
  - `docs/ollama/UML_XML_FORMAT_GUIDE.md` - Guía completa del formato XML
  - Pensado para que Ollama genere UML válido desde descripciones en lenguaje natural
  - Incluye: estructura XML, ejemplos, tipos por lenguaje, patrones de diseño

- **C++ Analysis Support** (2025-12-23)
  - Nuevo analizador `code_map/uml/cpp_analyzer.py` usando tree-sitter
  - Soporte para clases, structs, métodos, atributos C++
  - Detección de visibilidad, virtual, pure virtual, static
  - Integración en converter.py con layout automático
  - Frontend actualizado con contador de structs

- **Reverse Engineering: Code → UML** (2025-12-23)
  - Backend: Análisis Python + TypeScript + C++ con visibility, decoradores, async
  - Nuevo endpoint: `GET /api/graph/uml/project`
  - Conversor a UmlProjectDef con layout grid automático
  - Frontend: ImportFromCodeDialog para escanear e importar código
  - Botón "From Code" en toolbar del UML Editor

- **UML Editor Phases 1-4** - Editor visual completo con export XML
  - Canvas interactivo con React Flow
  - Soporte multi-lenguaje (Python, TypeScript, C++)
  - Entidades: Class, Interface, Enum, Struct
  - Relaciones: inheritance, implementation, composition, aggregation, association, dependency
  - Validación en tiempo real
  - Export XML con clipboard y archivo
  - Persistencia en localStorage
  - Eliminación de entidades y relaciones

**Bloqueado/Pendiente:**
- Ninguno

---

## 🎯 PRÓXIMOS PASOS

1. **Inmediato** (Próxima sesión):
   - **Phase 5: Agent Loop** - Integración con Claude para generación de código
     - Backend endpoint: `POST /uml-editor/generate`
     - UI de generación en ExportDialog
     - Mostrar código generado

2. **Corto plazo** (Próximas 1-3 sesiones):
   - Mejorar UX del canvas (zoom, pan, grid snap)
   - Atajos de teclado (Delete para eliminar, Ctrl+S para guardar)
   - Mejorar análisis TypeScript (tree-sitter más completo)

3. **Mediano plazo**:
   - Phase 8: Agent integration (plan→patch→gates workflow)
   - Integrar drift detection con frontend UI

---

## 📝 DECISIONES RECIENTES

### UML Editor Multi-Language (2025-12-22)
**Qué**: Soporte para Python, TypeScript y C++ con nombres específicos
**Config**: `frontend/src/config/languageConfig.ts`
**Mapeo**:
- Python: Class, Protocol (interface), Enum, Dataclass (struct)
- TypeScript: Class, Interface, Enum, Type (struct)
- C++: Class, Abstract Class (interface), Enum, Struct

### Persistencia con Zustand (2025-12-22)
**Qué**: Auto-guardado en localStorage con middleware `persist`
**Key**: `aegis-uml-editor-project`
**Partialize**: Solo project y currentModuleId (no UI state)

### Eliminación de Entidades (2025-12-22)
**Qué**: Botón Delete en InspectorPanel con confirmación
**Cascade**: Al eliminar entidad, se eliminan sus relaciones asociadas
**Hook fix**: useCallback movido antes de returns tempranos

---

## 🚨 CONTEXTO CRÍTICO

**Restricciones UML Editor:**
- React Flow requiere ReactFlowProvider como wrapper
- Hooks deben ejecutarse antes de cualquier return condicional
- El store usa Zustand con persist middleware para localStorage
- Las relaciones usan `from/to` (IDs de entidades)

**Patrones establecidos:**
- Nodos custom: ClassNode, InterfaceNode, EnumNode, StructNode
- Inspectors por tipo: ClassInspector, InterfaceInspector, etc.
- Validación centralizada en umlValidator.ts
- Export XML en umlXmlExporter.ts

---

## 📚 RECURSOS

**UML Editor:**
- **Componentes**: frontend/src/components/uml-editor/
- **Store**: frontend/src/state/useUmlEditorStore.ts
- **Config**: frontend/src/config/languageConfig.ts
- **Tipos**: frontend/src/api/types.ts (UmlProjectDef, etc.)
- **Validador**: frontend/src/utils/umlValidator.ts
- **Exporter**: frontend/src/utils/umlXmlExporter.ts
- **Spec**: docs/AEGIS_V2_SPECIFICATION_UML_2_XML.md
- **Ollama Guide**: docs/ollama/UML_XML_FORMAT_GUIDE.md

**Plan original**: .claude/plans/velvet-leaping-pine.md

---

## 🔄 Sesión: 2025-12-22 (UML Editor Phases 1-4)

**Implementado (33 archivos, ~7700 líneas):**

### Infraestructura (Phase 1)
- Tipos TypeScript en api/types.ts
- Store Zustand con persist middleware
- Ruta /uml-editor en App.tsx
- Tarjeta en HomeView + enlace en HeaderBar

### Canvas Interactivo (Phase 2)
- UmlEditorCanvas.tsx con React Flow
- Nodos: ClassNode, InterfaceNode, EnumNode, StructNode
- Edges: RelationshipEdge con estilos por tipo
- Minimap y controles

### Panel Inspector (Phase 3)
- InspectorPanel.tsx con tabs dinámicos
- ClassInspector, InterfaceInspector, EnumInspector, StructInspector
- RelationshipInspector para editar relaciones
- AttributeEditor, MethodEditor completos
- XmlPreview para previsualización

### Validación y Export (Phase 4)
- umlValidator.ts con 10+ reglas
- ValidationPanel con errores/warnings/info
- ExportDialog con preview, clipboard y download
- umlXmlExporter.ts genera XML según spec

### Refinamientos adicionales
- Multi-language support (Python, TypeScript, C++)
- Nombres de entidades según lenguaje
- Diálogo de confirmación al cambiar lenguaje
- Eliminación de entidades con confirmación
- Eliminación de relaciones
- Persistencia automática en localStorage

**Commit**: `27114e6` - "Add UML Editor for Model-Driven Development (AEGIS v2)"

---

## 🔄 Sesión: 2025-12-23 (Reverse Engineering: Code → UML)

**Implementado:**

### Backend - Análisis de Código
- `code_map/uml/models.py` - Extendido con visibility, is_static, is_async, docstring
- `code_map/uml/analyzer.py` - Detección de decoradores, visibilidad Python
- `code_map/uml/ts_analyzer.py` - **NUEVO**: Analizador TypeScript/TSX con tree-sitter
- `code_map/uml/converter.py` - **NUEVO**: Conversor a UmlProjectDef + layout grid

### Backend - API
- `code_map/api/graph.py` - Nuevo endpoint `GET /api/graph/uml/project`
- `code_map/api/schemas.py` - Schemas Pydantic para UmlProjectDef

### Frontend
- `frontend/src/api/client.ts` - Función `getCodeAsUmlProject()`
- `frontend/src/components/uml-editor/toolbar/ImportFromCodeDialog.tsx` - **NUEVO**
- `frontend/src/components/uml-editor/UmlEditorView.tsx` - Integración del botón "From Code"

**Características:**
- Escanea Python (.py) y TypeScript (.ts, .tsx)
- Detecta: clases, interfaces, métodos, atributos, herencia
- Infiere visibilidad desde convenciones Python (_, __)
- Detecta decoradores (@staticmethod, @abstractmethod, @classmethod)
- Layout automático en grid por módulo
- Preview de resultados antes de importar
- Merge con proyecto existente via mergeProject()

---

## 🎯 Detected Stage: Stage 3 (High Confidence)

**Auto-detected on:** 2025-12-09 18:18

**Metrics:**
- Files: 770+
- LOC: ~206000+
- Patterns: Adapter, Factory Pattern, Repository, Service Layer
