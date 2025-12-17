# Call Flow Graph - Especificación Técnica (v2)

## Resumen ejecutivo

El **Call Flow Graph** construye un **árbol de llamadas** a partir de un *entry point* elegido por el usuario (por ejemplo, un handler de GUI, un endpoint web, un callback, etc.). El objetivo es representar el flujo real de ejecución en aplicaciones event‑driven, donde el “Instance Graph” queda corto porque normalmente solo ve `main() → App → Window`, pero no el encadenado de handlers y servicios.

Esta versión (v2) **se salta la limitación de v1** y apunta a **resolver al máximo las llamadas dentro del código del proyecto**, incluyendo llamadas a métodos vía atributos (`obj.method()` / `self.attr.method()`), y siguiendo imports **multi‑archivo** dentro del `root_path`.

---

## Problema que resuelve

### Limitación del Instance Graph

En aplicaciones GUI/web/event‑driven, el flujo importante ocurre en callbacks/handlers/endpoints, no en `main()`.

### Ejemplo mental del problema

- El usuario hace click → handler → loader → parser → storage  
- El Instance Graph suele mostrar solo el wiring inicial  
- El Call Flow debe mostrar el flujo real: handler → funciones/métodos → funciones/métodos …

---

## Concepto del Call Flow Graph

### Definición

Dado:
- `root_path` (raíz del proyecto)
- un `entry_point_id` (símbolo seleccionado)
- `max_depth` (profundidad)

Construimos un **árbol** donde:
- Cada nodo representa una *invocación* (un “call‑site”) a un símbolo destino.
- El árbol duplica nodos si el mismo símbolo aparece en ramas distintas (porque el objetivo es el **flujo por rutas**, no un grafo deduplicado).
- Las llamadas fuera del proyecto se pueden **incluir como hojas** (para contexto), pero por defecto **no se expanden**.

---

## Objetivos de resolución

### Qué significa “resolverlo todo”

“Resolverlo todo” en la práctica significa:

1. **Resolver todas las llamadas que apunten a símbolos del proyecto** (dentro de `root_path`), siempre que exista evidencia estática suficiente.
2. Para lo no resoluble de forma estática (Python dinámico), devolver un nodo con estado **UNRESOLVED** y un **motivo** (no esconderlo como “external”).
3. Identificar y clasificar llamadas fuera del proyecto como:
   - **BUILTIN / STDLIB / THIRD_PARTY** (hojas ignoradas por scope, no por incapacidad)

### Principio de diseño

- **Preferir ser correcto a ser “creativo”**: si hay ambigüedad real, marcar **AMBIGUOUS** con candidatos.
- **No mezclar “IGNORED” con “UNRESOLVED”**: ignorar librerías es una decisión de producto; no resolver es una limitación técnica.

---

## Alcance

### Scope del proyecto

- **Project code** = cualquier símbolo cuya definición se resuelva a un archivo *dentro* de `root_path` (resolviendo symlinks a su ruta real).
- Todo lo que salga de `root_path` es “fuera de proyecto” y se clasifica (builtin/stdlib/third‑party) cuando sea posible.

### Multi‑archivo

Se siguen imports dentro del proyecto:
- `import pkg.mod as m` → `m.func()`
- `from pkg.mod import func as f` → `f()`
- imports relativos (`from .sub import x`)
- símbolos expuestos en `__init__.py` (cuando se pueda resolver a archivo y símbolo)

---

## Estados de resolución

Cada nodo/edge debe poder llevar un `resolution_status`:

- **RESOLVED_PROJECT**: símbolo destino encontrado dentro de `root_path`
- **IGNORED_BUILTIN**
- **IGNORED_STDLIB**
- **IGNORED_THIRD_PARTY**
- **UNRESOLVED**: no se pudo determinar destino (dinamismo, falta de tipo, etc.)
- **AMBIGUOUS**: múltiples destinos plausibles (se incluyen candidatos)

---

## Modelo de datos (backend)

### Identificadores

#### Symbol ID (estable)

Identificador único de un símbolo definido en el proyecto. Recomendación:
- `symbol_id = "{rel_path}:{start_line}:{start_col}:{kind}:{qualified_name}"`

Debe ser estable ante:
- colisiones de nombres entre módulos
- múltiples clases con el mismo método
- funciones con mismo nombre en distintos archivos

#### Tree Node ID (por aparición en árbol)

Nodo del árbol (instancia de llamada), no el símbolo:
- `tree_node_id = "{parent_tree_node_id}/{call_site_id}"` (o equivalente)

Esto permite duplicar el mismo símbolo en ramas distintas.

### Estructuras principales

- **Symbol**
  - `symbol_id`, `qualified_name`, `kind` (function/method/class), `module`, `file`, `range`
  - metadatos opcionales: firma, docstring resumen

- **CallSite**
  - ubicación exacta del call (archivo + rango/posición)
  - expresión resumida (p. ej. `self.loader.load_file(...)`)
  - `call_type` (direct, method, constructor, module_attr, function_var, etc.)
  - `resolution_status`
  - `targets`:
    - si RESOLVED → 1 target (Symbol)
    - si AMBIGUOUS → N targets (Symbols)
    - si IGNORED_* → target “externo” con nombre + categoría
    - si UNRESOLVED → motivo + hints

- **CallFlowTree**
  - `entry_point_symbol_id`
  - `root_tree_node_id`
  - `nodes` (tree nodes)
  - `edges` (parent → child)
  - `symbol_table` (map symbol_id → Symbol)
  - `diagnostics` (presupuesto, truncados, contadores, etc.)

---

## Arquitectura propuesta

### Componentes (backend)

1. **ProjectIndexer**
   - Recorre `root_path`
   - Parse AST de cada archivo Python
   - Construye:
     - tabla de módulos (path ↔ module name)
     - tabla de símbolos (defs de funciones, clases, métodos)
     - tabla de exports básicos (para `__init__.py` cuando aplique)
   - Mantiene caché por `mtime`/hash

2. **ImportResolver**
   - Resuelve nombres importados a:
     - módulo/archivo del proyecto
     - símbolo concreto si es `from x import y`
   - Soporta alias y relativos

3. **TypeResolver (inferencia estática “pragmática”)**
   - Objetivo: resolver `obj.method()` y `self.attr.method()` cuando el tipo es deducible.
   - Fuentes de verdad (de mayor a menor confianza):
     1. **Anotaciones de tipo** (PEP 484): `x: SomeType`, `self.attr: SomeType`
     2. **Asignación directa a constructor**:
        - `x = SomeType(...)`
        - `self.attr = SomeType(...)` (especialmente en `__init__`)
     3. **Factories obvias** (configurables): `make_service()` que retorna `Service` (solo si hay type hints)
     4. **Patrones simples de propagación**:
        - `y = x` (y hereda tipo de x)
   - Si no hay evidencia, marcar UNRESOLVED (no inventar).

4. **CallResolver**
   - Dado un AST de una función/método y su contexto (imports + scope + tipos conocidos),
     extrae calls y produce CallSites con destinos:
     - direct call: `func()`
     - method call: `self.method()`, `obj.method()`
     - module attr: `m.func()`
     - constructor: `ClassName(...)` (opcional: seguir a `__init__` como sub‑calls, no como “call normal”)
     - función en variable: `f()` si `f = some_func` es resoluble
   - Maneja herencia/mro para métodos cuando el tipo se resuelve a una clase.

5. **TreeBuilder**
   - Construye el árbol por BFS/DFS con:
     - `max_depth`
     - presupuestos (`max_nodes`, `max_edges`, `timeout_ms`)
   - Detección de ciclos **por rama** (stack de `symbol_id`), no `visited` global.
   - Produce `diagnostics` cuando trunca.

---

## Reglas de truncado y seguridad

### Seguridad de rutas

- Normalizar rutas (realpath) y asegurar `resolved_path` ∈ `root_path`.
- No seguir imports que salgan de `root_path` (se clasifican como IGNORED_*).

### Presupuestos

- `max_depth` (default 5)
- `max_nodes` (default 1000)
- `max_edges` (default 2000)
- `timeout_ms` (default 2000–5000, configurable)

Cuando se alcance un presupuesto:
- marcar rama como `TRUNCATED` con razón en diagnostics (no fallar silenciosamente).

---

## API endpoints (backend)

### 1) Listar entry points

`GET /call-flow/entry-points`

Parámetros:
- `root_path` (obligatorio)
- filtros opcionales: `file`, `query`, `kinds` (function/method), `include_tests`

Respuesta:
- lista de entry points con:
  - `entry_point_id` (= symbol_id)
  - nombre para UI (qualified)
  - archivo + línea
  - kind

### 2) Generar árbol de call flow

`POST /call-flow/tree`

Body:
- `root_path`
- `entry_point_id`
- `max_depth`
- `scope`:
  - `expand_project_only` (true por defecto)
  - `include_ignored_leaves` (true por defecto; se muestran como hojas)
  - `expand_third_party` (false por defecto)
- presupuestos: `max_nodes`, `max_edges`, `timeout_ms`

Respuesta:
- `CallFlowTree` (nodes/edges + symbol_table + diagnostics)

---

## Frontend (React Flow)

### Objetivo UX

- Visualizar un **árbol** (flow top‑down).
- Click en nodo:
  - navegar a archivo + rango
  - mostrar metadatos (status, expresión, targets, motivos de unresolved)

### Controles recomendados

- Slider de profundidad (`max_depth`)
- Toggle:
  - mostrar/ocultar IGNORED_* (builtin/stdlib/third‑party)
  - mostrar/ocultar UNRESOLVED
  - colapsar subárboles repetidos (opcional)
- Búsqueda de nodo (por qualified name)

### Layout

- El backend no debe “poner posiciones” como verdad.
- El frontend calcula layout (tree layout) a partir de edges.

---

## Test cases (mínimos para v2)

Crear fixtures que cubran obligatoriamente:

1. Llamadas directas (mismo archivo)
2. Imports con alias (import / from import)
3. `self.method()` dentro de clase
4. `obj.method()` con:
   - `obj = ClassName()`
   - `self.attr = ClassName()` en `__init__`
   - `obj: ClassName` (type hint)
5. Herencia:
   - método definido en base y llamado desde instancia de derived
6. Recursión / ciclos:
   - cortar por rama con marca de ciclo
7. Casos dinámicos:
   - `getattr`, `globals()`, monkey patch → UNRESOLVED con razón

La expectativa del test debe verificar:
- que lo “ignorado” esté clasificado (no UNRESOLVED)
- que UNRESOLVED venga con motivo y callsite
- que el árbol duplique nodos cuando el mismo símbolo se llame por rutas distintas

---

## Evolución futura (después de v2)

- Expansión opcional a third‑party (solo si el usuario lo pide)
- Soporte incremental (watcher) para indexado rápido en proyectos grandes
- Call graph híbrido (árbol + “referencias cruzadas”)
- Multi‑lenguaje (Qt/C++ como siguiente candidato si el repo lo requiere)
