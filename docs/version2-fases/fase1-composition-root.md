# Fase 1: Extracción de Composition Roots

**Objetivo**: Detectar puntos de entrada donde se arma el programa (wiring)

---

## Concepto

Un **Composition Root** es el lugar donde:
- Se instancian componentes de larga vida
- Se conectan entre sí (wiring)
- Se gestiona el lifecycle (start/stop)

**Ejemplo típico**: función `main()` en C++/Python

---

## Detección MVP

### Por convención (automático)

| Lenguaje | Archivos | Funciones |
|----------|----------|-----------|
| C++ | `main.cpp`, `main.cc` | `main()` |
| Python | `main.py`, `__main__.py`, `app.py` | `main()`, `if __name__` |

### Marcado manual (UI)

```python
# @aegis-composition-root
def create_pipeline():
    ...
```

---

## Extracción de Instancias

### C++ - Patrones a detectar

```cpp
// Patrón 1: unique_ptr con factory
const auto m1 = createGeneratorModule();

// Patrón 2: unique_ptr directo
auto m2 = std::make_unique<FilterModule>(config);

// Patrón 3: Variables locales de larga vida
GeneratorModule generator;
```

**AST nodes a buscar** (tree-sitter):
- `variable_declaration` con tipo `unique_ptr`, `shared_ptr`, o clase conocida
- Llamadas a funciones `create*`, `make_*`

### Python - Patrones a detectar

```python
# Patrón 1: Instanciación directa
generator = GeneratorModule()

# Patrón 2: Factory
pipeline = create_pipeline(config)

# Patrón 3: Context manager
with Pipeline() as p:
    ...
```

---

## Extracción de Wiring

### C++ - Patrones

```cpp
// Patrón: setNext / connect / add
m1->setNext(m2.get());
pipeline.connect(source, sink);
```

**Detectar**:
- Llamadas a métodos `setNext`, `connect`, `add`, `link`, `pipe`
- Argumentos que referencian otras instancias

### Python - Patrones

```python
# Patrón: métodos de conexión
m1.set_next(m2)
pipeline.add_stage(processor)
source | filter | sink  # Operador pipe
```

---

## Modelo de Salida

```python
@dataclass
class InstanceInfo:
    name: str              # "m1", "generator"
    type_name: str         # "GeneratorModule"
    location: Location     # Archivo:línea
    creation_pattern: str  # "factory", "direct", "make_unique"
    args: List[str]        # Argumentos de construcción

@dataclass
class WiringInfo:
    source: str            # Nombre instancia origen
    target: str            # Nombre instancia destino
    method: str            # "setNext", "connect"
    location: Location     # Call-site exacto

@dataclass
class CompositionRoot:
    file_path: Path
    function_name: str
    instances: List[InstanceInfo]
    wiring: List[WiringInfo]
```

---

## Límites MVP

### Soportado
- Wiring explícito en composition root
- Factories que retornan tipo conocido
- Variables locales nombradas

### NO soportado (futuro)
- DI containers (Spring, Guice)
- Config-based wiring (YAML/JSON)
- Wiring dinámico en runtime
- Reflection-based instantiation

---

## Integración con AEGIS v1

Reutilizar:
- `c_analyzer.py` → AST de C++
- `analyzer.py` → AST de Python
- `models.py` → `SymbolInfo` para tipos

---

## Checklist

```
[ ] Implementar detección de composition root por convención
[ ] Implementar detección de instancias (C++)
[ ] Implementar detección de instancias (Python)
[ ] Implementar detección de wiring (C++)
[ ] Implementar detección de wiring (Python)
[ ] Tests con proyecto Actia
```

---

## DoD

- [ ] Dado `main.cpp` de Actia, extraer: m1, m2, m3
- [ ] Detectar wiring: m1→m2, m2→m3
- [ ] Cada instancia tiene location exacta
- [ ] Cada wiring tiene call-site exacto
