# Call Flow Graph - Especificación Técnica


## Resumen Ejecutivo


El **Call Flow Graph** es una visualización que muestra la cadena de llamadas a funciones desde un punto de entrada seleccionado por el usuario. A diferencia del Instance Graph (que muestra qué objetos se crean en `main()`), el Call Flow muestra **qué funciones llama cada función**.


## Problema que Resuelve


### Limitación del Instance Graph


El Instance Graph analiza "composition roots" - objetos instanciados en el punto de entrada (`main()`, `if __name__ == "__main__"`). Esto funciona bien para:


- Pipelines de datos lineales
- Scripts de procesamiento batch
- CLIs simples


**Pero NO funciona para:**


- Aplicaciones GUI (PyQt, Tkinter, etc.) donde el flujo real está en los **event handlers**
- Aplicaciones web donde el flujo está en los **endpoints/routes**
- Sistemas event-driven donde el comportamiento depende de eventos, no de código secuencial


### Ejemplo del Problema


```python
# main.py de una app PyQt
def main():
   app = QApplication(sys.argv)
   window = MainWindow()  # <- Instance Graph solo ve esto
   window.show()
   app.exec()


# Pero el flujo REAL está aquí:
class MainWindow:
   def on_btn_load_json(self):  # <- Cuando usuario hace click
       data = self.loader.load_file()
       processed = self.processor.transform(data)
       self.storage.save(processed)
```


El Instance Graph muestra: `main() → MainWindow`


El Call Flow debería mostrar:
```
on_btn_load_json → loader.load_file → read_content
                → processor.transform → validate → normalize
                → storage.save → write_to_db
```


## Concepto del Call Flow Graph


### Definición


Un **Call Flow Graph** es un grafo dirigido donde:
- **Nodos**: Funciones o métodos
- **Aristas**: Llamadas de una función a otra
- **Entry Point**: El nodo raíz seleccionado por el usuario


### Características Clave


1. **Selección de Entry Point**: El usuario elige qué función analizar (no se asume `main()`)
2. **Profundidad Configurable**: Límite de cuántos niveles de llamadas seguir (default: 5)
3. **Scope del Proyecto**: Solo sigue llamadas a código del proyecto (no stdlib ni third-party)
4. **Resolución de Llamadas**: Intenta resolver `self.method()`, `obj.func()`, constructores


### Tipos de Llamadas a Resolver


| Tipo | Ejemplo | Complejidad |
|------|---------|-------------|
| Llamada directa | `helper()` | Fácil - buscar en mismo archivo/imports |
| Llamada a método self | `self.process()` | Media - buscar en misma clase |
| Llamada a atributo | `self.loader.load()` | Difícil - requiere tracking de tipos |
| Constructor | `DataHandler()` | Media - buscar clase y seguir `__init__` |
| Import | `from module import func` | Media - seguir a otro archivo |


### Limitaciones Aceptables (v1)


- **No resolver tipos dinámicos**: `getattr()`, duck typing, etc.
- **No seguir código externo**: stdlib, third-party → marcar como "external"
- **Solo Python inicialmente**: Otros lenguajes en futuras versiones
- **No análisis de control flow**: No distinguir `if/else` branches


## Arquitectura Propuesta


### Modelo de Datos


```python
@dataclass
class CallNode:
   id: str                      # Identificador único
   name: str                    # "process_data"
   qualified_name: str          # "DataHandler.process_data"
   file_path: Optional[Path]    # Ruta al archivo (None si external)
   line: int                    # Línea de definición
   kind: str                    # "function" | "method" | "external" | "builtin"
   is_entry_point: bool         # True solo para el nodo raíz
   depth: int                   # Distancia desde entry point
   docstring: Optional[str]     # Docstring de la función


@dataclass
class CallEdge:
   source_id: str               # ID del nodo que llama
   target_id: str               # ID del nodo llamado
   call_site_line: int          # Línea donde ocurre la llamada
   call_type: str               # "direct" | "method" | "constructor"


@dataclass
class CallGraph:
   entry_point: str             # Qualified name del entry point
   source_file: Path            # Archivo analizado
   nodes: Dict[str, CallNode]   # Nodos por ID
   edges: List[CallEdge]        # Conexiones
   max_depth: int               # Profundidad máxima configurada
   max_depth_reached: bool      # True si se truncó por profundidad
   external_calls: List[str]    # Llamadas no seguidas (external)
```


### API Endpoints


```
GET /api/call-flow/entry-points/{file_path}
```
Lista funciones/métodos disponibles en un archivo para usar como entry points.


**Response:**
```json
{
 "file_path": "/path/to/file.py",
 "entry_points": [
   {"name": "main", "qualified_name": "main", "line": 52, "kind": "function"},
   {"name": "handle", "qualified_name": "DataHandler.handle", "line": 37, "kind": "method", "class_name": "DataHandler"}
 ]
}
```


```
GET /api/call-flow/{file_path}?function=X&max_depth=N&class_name=Y
```
Extrae el grafo de llamadas desde una función.


**Parámetros:**
- `function`: Nombre de la función (required)
- `max_depth`: Profundidad máxima, 1-20 (default: 5)
- `class_name`: Nombre de clase si es un método (optional)


**Response:**
```json
{
 "nodes": [
   {
     "id": "node_1",
     "type": "callFlowNode",
     "position": {"x": 0, "y": 0},
     "data": {
       "label": "on_button_click",
       "qualifiedName": "MainWindow.on_button_click",
       "filePath": "/path/to/file.py",
       "line": 44,
       "kind": "method",
       "isEntryPoint": true,
       "depth": 0
     }
   }
 ],
 "edges": [
   {
     "id": "edge_1",
     "source": "node_1",
     "target": "node_2",
     "data": {"callSiteLine": 46, "callType": "method"}
   }
 ],
 "metadata": {
   "entry_point": "MainWindow.on_button_click",
   "source_file": "/path/to/file.py",
   "max_depth": 5,
   "max_depth_reached": false,
   "node_count": 8,
   "edge_count": 7,
   "external_calls": ["print", "json.loads"],
   "external_calls_count": 2
 }
}
```


### Algoritmo de Extracción (Pseudocódigo)


```python
def extract_call_flow(file_path, function_name, max_depth=5):
   # 1. Parsear archivo con tree-sitter
   tree = parse_file(file_path)


   # 2. Encontrar la función entry point
   entry_func = find_function(tree, function_name)
   if not entry_func:
       return None


   # 3. Crear nodo raíz
   graph = CallGraph(entry_point=function_name)
   root_node = create_node(entry_func, is_entry_point=True, depth=0)
   graph.add_node(root_node)


   # 4. BFS para seguir llamadas
   queue = [(root_node, 0)]  # (nodo, profundidad)
   visited = {root_node.qualified_name}


   while queue:
       current_node, depth = queue.pop(0)


       if depth >= max_depth:
           graph.max_depth_reached = True
           continue


       # 5. Encontrar llamadas en el cuerpo de la función
       calls = find_calls_in_function(current_node)


       for call in calls:
           # 6. Intentar resolver la llamada
           resolved = resolve_call(call, tree, file_path)


           if resolved is None:
               # No se pudo resolver → marcar como external
               graph.external_calls.append(call.name)
               continue


           if resolved.qualified_name in visited:
               # Ya visitado → solo añadir edge (evitar ciclos infinitos)
               graph.add_edge(current_node, resolved, call.line)
               continue


           # 7. Crear nodo y edge
           new_node = create_node(resolved, depth=depth+1)
           graph.add_node(new_node)
           graph.add_edge(current_node, new_node, call.line)


           visited.add(resolved.qualified_name)
           queue.append((new_node, depth + 1))


   return graph
```


### Resolución de Llamadas


La parte más compleja es resolver qué función se está llamando:


```python
def resolve_call(call_node, tree, file_path):
   call_text = get_call_text(call_node)  # ej: "self.loader.load()"


   # Caso 1: Llamada directa - "helper()"
   if is_simple_call(call_text):
       name = extract_name(call_text)  # "helper"
       # Buscar en mismo archivo
       func = find_function_in_file(tree, name)
       if func:
           return func
       # Buscar en imports
       return resolve_from_imports(name, file_path)


   # Caso 2: Llamada a self - "self.process()"
   if call_text.startswith("self."):
       method_name = extract_method_name(call_text)  # "process"
       current_class = get_enclosing_class(call_node)
       return find_method_in_class(tree, current_class, method_name)


   # Caso 3: Constructor - "DataHandler()"
   if is_constructor_call(call_text):
       class_name = extract_class_name(call_text)  # "DataHandler"
       cls = find_class_in_file(tree, class_name)
       if cls:
           return find_method_in_class(tree, class_name, "__init__")
       return resolve_from_imports(class_name, file_path)


   # Caso 4: Llamada a atributo - "self.loader.load()"
   # Esto es difícil sin type inference → marcar como external por ahora
   return None
```


## Frontend (React Flow)


### Componentes


1. **CallFlowView**: Página principal con:
  - Input para seleccionar archivo
  - Sidebar con entry points disponibles
  - Slider para max_depth
  - Panel de metadatos


2. **CallFlowGraph**: Canvas de React Flow con:
  - Nodos custom con colores por tipo
  - Edges animados con label de línea
  - MiniMap y controles de zoom


3. **CallFlowNode**: Nodo custom mostrando:
  - Nombre de función
  - Badge "ENTRY POINT" si es raíz
  - Badge de tipo (Function/Method/External)
  - Línea de definición


### Colores Sugeridos


| Tipo | Color | Hex |
|------|-------|-----|
| Entry Point | Amber | #f59e0b |
| Function | Blue | #3b82f6 |
| Method | Green | #10b981 |
| External | Gray | #6b7280 |
| Class/Constructor | Purple | #a855f7 |


## Estructura de Archivos


```
code_map/
├── v2/
│   └── call_flow/
│       ├── __init__.py
│       ├── models.py        # CallNode, CallEdge, CallGraph
│       ├── extractor.py     # PythonCallFlowExtractor (tree-sitter)
│       └── resolver.py      # Resolución de imports y símbolos
├── api/
│   ├── call_flow.py         # Endpoints REST
│   └── schemas.py           # Schemas Pydantic (añadir CallFlow*)


frontend/src/
├── api/
│   ├── client.ts            # getCallFlowEntryPoints, getCallFlow
│   ├── types.ts             # CallFlowResponse, etc.
│   └── queryKeys.ts         # callFlowEntryPoints, callFlow
├── hooks/
│   └── useCallFlowQuery.ts  # React Query hooks
├── components/
│   ├── CallFlowView.tsx     # Página principal
│   └── call-flow/
│       ├── CallFlowNode.tsx
│       ├── CallFlowEdge.tsx
│       └── CallFlowGraph.tsx
```


## Dependencias


### Backend
- `tree-sitter` + `tree-sitter-languages`: Parsing de AST
- `fastapi`: API REST


### Frontend
- `reactflow`: Visualización de grafos
- `@tanstack/react-query`: Estado del servidor


## Test Cases


### Archivo de Prueba Sugerido


```python
# tests/fixtures/call_flow_sample.py


def helper_function():
   """A helper function."""
   return "helper result"


def process_data(data):
   """Process data using helper."""
   result = helper_function()
   return f"processed: {data} with {result}"


def load_content():
   """Load content from somewhere."""
   return {"key": "value"}


class DataHandler:
   """Handler class for data operations."""


   def __init__(self):
       self.data = None


   def load(self):
       """Load data using load_content."""
       self.data = load_content()
       return self.data


   def process(self):
       """Process the loaded data."""
       if self.data:
           return process_data(self.data)
       return None


   def handle(self):
       """Handle the full workflow."""
       self.load()
       result = self.process()
       return result


def on_button_click():
   """Event handler simulating a button click."""
   handler = DataHandler()
   result = handler.handle()
   print(result)
   return result


def main():
   """Main entry point."""
   on_button_click()


if __name__ == "__main__":
   main()
```


### Resultados Esperados


**Entry Point: `on_button_click`**


```
on_button_click (depth 0)
├── DataHandler.__init__ (depth 1)
├── DataHandler.handle (depth 1)
│   ├── DataHandler.load (depth 2)
│   │   └── load_content (depth 3)
│   └── DataHandler.process (depth 2)
│       └── process_data (depth 3)
│           └── helper_function (depth 4)
└── print [EXTERNAL]
```


**Entry Point: `DataHandler.handle`**


```
DataHandler.handle (depth 0)
├── DataHandler.load (depth 1)
│   └── load_content (depth 2)
└── DataHandler.process (depth 1)
   └── process_data (depth 2)
       └── helper_function (depth 3)
```


## Evolución Futura


### Fase 2
- Soporte para TypeScript/JavaScript
- Resolución de `self.attribute.method()` con tracking de tipos
- Cache de grafos calculados


### Fase 3
- Cross-file analysis (seguir imports entre archivos)
- Detección de ciclos con visualización especial
- Filtros por tipo de llamada


### Fase 4
- Integración con debugger (breakpoints en call flow)
- Diff de call flows entre commits
- Análisis de impacto (qué cambia si modifico X)


---


*Documento generado para AEGIS v2 - Call Flow Graph Feature*
