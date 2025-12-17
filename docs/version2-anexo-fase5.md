# Anexo Fase 5: Parser/Rewriter de Contratos

**Documento técnico detallado para la implementación del sistema de contratos embebidos**

---

## 1. Principio Fundamental

> **Separar CREAR de DESCUBRIR**

| Modo | Propósito | Confianza | Complejidad |
|------|-----------|-----------|-------------|
| **CREAR** | Usuario define contratos nuevos | 100% | Baja |
| **DESCUBRIR** | Extraer contratos de código existente | Variable | Alta |

Esta separación es crítica porque:
- CREAR tiene formato controlado y predecible
- DESCUBRIR requiere heurísticas, LLM, y tolerancia a fallos

---

## 2. Modo CREAR: Formato AEGIS-owned

### 2.1 Especificación del Formato

AEGIS "posee" bloques delimitados por marcadores claros. El contenido es YAML estructurado.

**C++ (comentarios):**
```cpp
// @aegis-contract-begin
// thread_safety: safe_after_start
// lifecycle: stopped -> running -> stopped
// invariants:
//   - pipeline must be started before process()
//   - next_ pointer immutable after start()
// preconditions:
//   - input != nullptr
// postconditions:
//   - output forwarded to next module
// errors:
//   - throws runtime_error if next_ not set
// evidence:
//   - test: tests/module_test.cpp::TestProcessFlow
//   - lint: clang-tidy
//   - policy: required
// @aegis-contract-end
class ProcessingModule : public IModule {
```

**Python (docstring):**
```python
class ProcessingModule(IModule):
    """
    @aegis-contract-begin
    thread_safety: safe_after_start
    lifecycle: stopped -> running -> stopped
    invariants:
      - pipeline must be started before process()
    preconditions:
      - input is not None
    evidence:
      - test: tests/test_module.py::test_process_flow
      - policy: required
    @aegis-contract-end

    Documentación normal del usuario continúa aquí...
    """
```

### 2.2 Schema del Contrato (MVP)

```yaml
# Schema mínimo para MVP
contract_schema:
  thread_safety:
    type: enum
    values: [not_safe, safe, safe_after_start, immutable]
    required: false

  lifecycle:
    type: string
    description: "Estado transitions (e.g., stopped -> running -> stopped)"
    required: false

  invariants:
    type: list[string]
    description: "Condiciones que siempre deben cumplirse"
    required: false

  preconditions:
    type: list[string]
    description: "Condiciones requeridas antes de llamar"
    required: false

  postconditions:
    type: list[string]
    description: "Garantías después de ejecutar"
    required: false

  errors:
    type: list[string]
    description: "Errores/excepciones que puede lanzar"
    required: false

  dependencies:
    type: list[string]
    description: "Módulos/componentes requeridos para funcionar"
    required: false

  evidence:
    type: list[evidence_item]
    required: false

  # Sub-schema para evidence
  evidence_item:
    test: string      # path::test_name
    lint: string      # tool name
    policy: enum      # required | optional | warning
```

### 2.3 Reglas de Rewriting

**Principios:**
1. AEGIS solo toca el contenido entre `@aegis-contract-begin` y `@aegis-contract-end`
2. Nunca modifica código fuera del bloque
3. Preserva indentación del contexto
4. Genera diffs mínimos y predecibles

**Ubicación canónica (si no existe bloque):**
- C++: Comentario inmediatamente antes de la declaración de clase/función
- Python: Primera línea del docstring (antes de texto existente)

---

## 3. Modo DESCUBRIR: Pipeline de Confianza Decreciente

### 3.1 Arquitectura del Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  NIVEL 1: Bloques @aegis-contract (100% confianza)          │
│  Parser: Regex + YAML                                        │
│  Resultado: ContractData con confidence=1.0                  │
└─────────────────────────────────────────────────────────────┘
                            ↓ no encontrado
┌─────────────────────────────────────────────────────────────┐
│  NIVEL 2: Patrones conocidos (80% confianza)                │
│  Parser: Regex especializado por formato                     │
│  Formatos soportados:                                        │
│    - Doxygen: @pre, @post, @invariant, @throws              │
│    - JSDoc: @throws, @returns, @param                        │
│    - Google docstring style                                  │
│    - NumPy docstring style                                   │
│  Resultado: ContractData con confidence=0.8                  │
└─────────────────────────────────────────────────────────────┘
                            ↓ no encontrado
┌─────────────────────────────────────────────────────────────┐
│  NIVEL 3: Extracción LLM (60% confianza)                    │
│  Herramienta: Ollama (OBLIGATORIO en modo discover)          │
│  Prompt: Analizar comentarios/docstrings y extraer           │
│          contratos implícitos                                │
│  Resultado: ContractData con confidence=0.6, needs_review=true│
└─────────────────────────────────────────────────────────────┘
                            ↓ no encontrado
┌─────────────────────────────────────────────────────────────┐
│  NIVEL 4: Análisis estático (40% confianza)                 │
│  Parser: AST analysis                                        │
│  Busca: assert(), throws, null checks, mutex locks           │
│  Resultado: ContractData con confidence=0.4, inferred=true   │
└─────────────────────────────────────────────────────────────┘
                            ↓ no encontrado
┌─────────────────────────────────────────────────────────────┐
│  NIVEL 5: Sin contrato                                       │
│  Resultado: ContractData vacío con confidence=0.0            │
│  UI muestra: "No contract found"                             │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 Nivel 2: Patrones Conocidos

**Doxygen (C++):**
```cpp
/**
 * @brief Process incoming data
 * @pre input must not be null
 * @post data forwarded to next module
 * @invariant thread-safe after start()
 * @throws std::runtime_error if next module not set
 */
void process(const ByteArray& input);
```

Regex patterns:
```python
DOXYGEN_PATTERNS = {
    'preconditions': r'@pre\s+(.+?)(?=@|\*/|$)',
    'postconditions': r'@post\s+(.+?)(?=@|\*/|$)',
    'invariants': r'@invariant\s+(.+?)(?=@|\*/|$)',
    'errors': r'@throws?\s+(\S+)\s+(.+?)(?=@|\*/|$)',
    'thread_safety': r'@threadsafe|@thread[_-]?safe',
}
```

**Google Style (Python):**
```python
def process(self, input: ByteArray) -> None:
    """Process incoming data.

    Args:
        input: Data to process. Must not be None.

    Returns:
        None. Data is forwarded to next module.

    Raises:
        RuntimeError: If next module not set.

    Note:
        Thread-safe after start() is called.
    """
```

### 3.3 Nivel 3: Extracción LLM

**Requisito**: Ollama debe estar disponible y configurado.

**Prompt template:**
```
Analiza el siguiente código y extrae contratos implícitos.
Busca: precondiciones, postcondiciones, invariantes, errores, thread-safety.

CÓDIGO:
{code_block}

COMENTARIOS/DOCSTRING:
{documentation}

Responde SOLO en formato YAML válido con este schema:
```yaml
thread_safety: <not_safe|safe|safe_after_start|immutable|unknown>
invariants:
  - <invariante 1>
preconditions:
  - <precondición 1>
postconditions:
  - <postcondición 1>
errors:
  - <error 1>
confidence_notes: <explicación breve de por qué inferiste esto>
```

Si no puedes inferir algo con confianza, omítelo.
```

**Validación post-LLM:**
1. Parsear YAML resultante
2. Validar contra schema
3. Marcar como `needs_review=true`
4. Almacenar `confidence_notes` para UI

### 3.4 Nivel 4: Análisis Estático

Buscar patrones en el código que implican contratos:

```python
STATIC_PATTERNS = {
    # Precondiciones inferidas
    'preconditions': [
        r'assert\s*\(\s*(.+?)\s*\)',                    # assert(condition)
        r'if\s*\(\s*!?\s*(\w+)\s*\)\s*throw',          # if (!x) throw
        r'if\s*\(\s*(\w+)\s*==\s*nullptr\s*\)',        # if (x == nullptr)
    ],

    # Thread-safety inferida
    'thread_safety': [
        r'std::mutex',
        r'std::lock_guard',
        r'std::atomic',
        r'threading\.Lock',
        r'@synchronized',
    ],

    # Errores inferidos
    'errors': [
        r'throw\s+(\w+)',                              # throw Exception
        r'raise\s+(\w+)',                              # raise Exception (Python)
    ],
}
```

---

## 4. Integración con AEGIS v1

### 4.1 Reutilización de Componentes Existentes

| Componente v1 | Uso en Fase 5 |
|---------------|---------------|
| `c_analyzer.py` | Base para `_find_leading_comment()` - ya extrae comentarios |
| `ts_analyzer.py` | Patrón para extensión JS/TS |
| `ollama_service.py` | `chat_with_ollama()` para Nivel 3 |
| `models.py` | Extender `SymbolInfo` con `contract` field |
| `analyzer_registry.py` | Registrar contract parser por lenguaje |

### 4.2 Estructura de Módulos Propuesta

```
code_map/
├── contracts/                    # NUEVO: Sistema de contratos
│   ├── __init__.py
│   ├── schema.py                # Definición del schema ContractData
│   ├── parser.py                # Orquestador del pipeline
│   ├── rewriter.py              # Escritura/actualización de contratos
│   ├── discovery.py             # Pipeline de confianza (Niveles 1-5)
│   ├── patterns/                # Patrones por formato
│   │   ├── aegis.py            # Nivel 1: @aegis-contract
│   │   ├── doxygen.py          # Nivel 2: Doxygen
│   │   ├── google_style.py     # Nivel 2: Google docstring
│   │   └── static.py           # Nivel 4: Análisis estático
│   ├── llm/                     # Integración LLM
│   │   ├── extractor.py        # Nivel 3: Ollama extraction
│   │   └── prompts.py          # Templates de prompts
│   └── languages/               # Reglas por lenguaje
│       ├── base.py             # Interfaz común
│       ├── cpp.py              # Reglas C++
│       └── python.py           # Reglas Python
```

### 4.3 Modelos de Datos

```python
# code_map/contracts/schema.py

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional
from pathlib import Path

class ThreadSafety(Enum):
    NOT_SAFE = "not_safe"
    SAFE = "safe"
    SAFE_AFTER_START = "safe_after_start"
    IMMUTABLE = "immutable"
    UNKNOWN = "unknown"

class EvidencePolicy(Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    WARNING = "warning"

@dataclass
class EvidenceItem:
    """Referencia a evidencia que respalda el contrato."""
    type: str  # 'test', 'lint', 'typecheck'
    reference: str  # path::test_name o tool_name
    policy: EvidencePolicy = EvidencePolicy.OPTIONAL
    last_result: Optional[bool] = None
    last_run: Optional[str] = None

@dataclass
class ContractData:
    """Contrato extraído o definido para un símbolo."""
    # Contenido del contrato
    thread_safety: Optional[ThreadSafety] = None
    lifecycle: Optional[str] = None
    invariants: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    evidence: List[EvidenceItem] = field(default_factory=list)

    # Metadatos de extracción
    confidence: float = 1.0  # 0.0 - 1.0
    source_level: int = 0    # 1-5 (nivel del pipeline que lo encontró)
    needs_review: bool = False
    inferred: bool = False
    confidence_notes: Optional[str] = None

    # Ubicación en código
    file_path: Optional[Path] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    def is_empty(self) -> bool:
        """Retorna True si no hay contenido significativo."""
        return not any([
            self.thread_safety,
            self.lifecycle,
            self.invariants,
            self.preconditions,
            self.postconditions,
            self.errors,
            self.evidence,
        ])

    def has_required_evidence(self) -> bool:
        """Retorna True si toda la evidencia requerida está presente."""
        required = [e for e in self.evidence if e.policy == EvidencePolicy.REQUIRED]
        return all(e.last_result is True for e in required)
```

---

## 5. Spike Técnico (Validación Pre-Implementación)

### 5.1 Objetivo

Validar el approach antes de comprometer la Fase 5 completa.

### 5.2 Proyecto de Prueba

```
/home/jesusramos/Workspace/Actia Prueba Tecnica/
```

Este proyecto C++ tiene:
- Documentación JSDoc-style con contratos explícitos
- Thread-safety documentada en `IModule.h`
- Assertions (`assert()`) para precondiciones
- Excepciones documentadas
- Composition root claro en `main.cpp`

### 5.3 Tareas del Spike (2-3 días)

```
[ ] Día 1: Parser básico
    [ ] Implementar Nivel 1 (bloques @aegis-contract) - aunque no existan aún
    [ ] Implementar Nivel 2 (Doxygen/JSDoc) - el proyecto usa este formato
    [ ] Test: Extraer contratos de IModule.h

[ ] Día 2: Rewriter
    [ ] Implementar inserción de bloque @aegis-contract
    [ ] Implementar actualización de bloque existente
    [ ] Test: Crear contrato → diff muestra SOLO el bloque

[ ] Día 3: Integración LLM
    [ ] Implementar Nivel 3 con Ollama
    [ ] Test: Extraer contratos de GeneratorModule.cpp
    [ ] Comparar resultado LLM vs Nivel 2
```

### 5.4 Criterios de Éxito

| Criterio | Métrica |
|----------|---------|
| Parsing Nivel 2 | Extrae ≥80% de contratos de IModule.h |
| Rewriting | Diff de ≤15 líneas al crear/actualizar contrato |
| No rompe código | Archivo sigue compilando después de rewrite |
| LLM accuracy | Resultado LLM coincide ≥70% con Nivel 2 |

### 5.5 Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Formatos de comentario muy variados | Alta | Medio | Nivel 3 (LLM) como fallback |
| Rewriter rompe indentación | Media | Alto | Tests exhaustivos con ejemplos reales |
| LLM genera YAML inválido | Media | Bajo | Validación estricta + retry con prompt corregido |
| Performance con archivos grandes | Baja | Medio | Procesar solo símbolos solicitados, no todo el archivo |

---

## 6. API Propuesta

### 6.1 Endpoints REST

```yaml
# Extracción de contratos
POST /api/contracts/discover
  body:
    file_path: string
    symbol_name: string (opcional, si no se da analiza todo el archivo)
    levels: [1,2,3,4] (opcional, default todos)
    require_ollama: bool (default false)
  response:
    contracts: List[ContractData]
    discovery_stats:
      level_1_found: int
      level_2_found: int
      level_3_found: int
      level_4_found: int
      total_symbols: int

# Escritura de contratos
POST /api/contracts/write
  body:
    file_path: string
    symbol_name: string
    contract: ContractData
  response:
    success: bool
    diff: string (unified diff)
    warnings: List[string]

# Validación de contratos
POST /api/contracts/validate
  body:
    file_path: string
    symbol_name: string
  response:
    contract: ContractData
    evidence_status:
      - evidence: EvidenceItem
        status: pass|fail|not_run
        last_output: string
    drift_warnings: List[string]
```

### 6.2 CLI Commands

```bash
# Descubrir contratos en un archivo
python -m code_map.cli contracts discover /path/to/file.cpp

# Descubrir contratos en un proyecto
python -m code_map.cli contracts discover /path/to/project --recursive

# Crear/actualizar contrato
python -m code_map.cli contracts write /path/to/file.cpp ClassName --thread-safety safe

# Validar contratos
python -m code_map.cli contracts validate /path/to/file.cpp
```

---

## 7. UI Integration (Preview)

### 7.1 Panel Lateral - Pestaña "Tipo"

```
┌─────────────────────────────────────────────┐
│ ProcessingModule                            │
│ /src/ProcessingModule.h:15                  │
├─────────────────────────────────────────────┤
│ CONTRACT                          [Edit] 🟢 │
├─────────────────────────────────────────────┤
│ Thread Safety: safe_after_start             │
│ Lifecycle: stopped → running → stopped      │
│                                             │
│ Invariants:                                 │
│  • pipeline must be started before process  │
│  • next_ pointer immutable after start      │
│                                             │
│ Preconditions:                              │
│  • input != nullptr                         │
│                                             │
│ Evidence:                          Status   │
│  • tests/module_test.cpp::Test... ✅ PASS  │
│  • clang-tidy                     ✅ PASS  │
├─────────────────────────────────────────────┤
│ Confidence: 100% (AEGIS-owned)              │
│ Source: Level 1 (@aegis-contract)           │
└─────────────────────────────────────────────┘
```

### 7.2 Indicadores de Confianza

| Nivel | Badge | Color | Significado |
|-------|-------|-------|-------------|
| 1 | ✅ AEGIS | Verde | Contrato verificado, owned by AEGIS |
| 2 | 📋 Pattern | Azul | Extraído de patrón conocido |
| 3 | 🤖 Inferred | Amarillo | Inferido por LLM, requiere revisión |
| 4 | ⚡ Static | Gris | Inferido de código, muy heurístico |
| 5 | ❓ None | Rojo | Sin contrato detectado |

---

## 8. Dependencias y Requisitos

### 8.1 Ollama (Obligatorio para Nivel 3)

```yaml
ollama_requirements:
  minimum_version: "0.1.0"
  recommended_models:
    - "llama3.2:3b"      # Rápido, suficiente para extracción
    - "codellama:7b"     # Mejor para código, más lento
    - "deepseek-coder"   # Alternativa especializada

  configuration:
    timeout: 30s         # Nivel 3 puede ser lento
    retry_on_timeout: 2  # Reintentos antes de fallar
    fallback_to_level_4: true  # Si Ollama falla, continuar
```

### 8.2 Dependencias Python

```
# Existentes (ya en requirements.txt)
pyyaml>=6.0           # Parsing de contratos
tree-sitter>=0.20     # AST para análisis estático
httpx>=0.27           # Comunicación con Ollama

# Nuevas (si necesarias)
# Ninguna - reutilizamos infraestructura existente
```

---

## 9. Plan de Implementación

### 9.1 Fases Detalladas

```
Fase 5.1: Schema y modelos (1 día)
├── [ ] Crear code_map/contracts/schema.py
├── [ ] Definir ContractData, EvidenceItem, enums
└── [ ] Tests unitarios para serialización YAML

Fase 5.2: Parser Nivel 1 - AEGIS format (1 día)
├── [ ] Crear code_map/contracts/patterns/aegis.py
├── [ ] Implementar detección de bloques @aegis-contract
├── [ ] Implementar parsing YAML del contenido
└── [ ] Tests con ejemplos sintéticos

Fase 5.3: Parser Nivel 2 - Patrones conocidos (2 días)
├── [ ] Crear code_map/contracts/patterns/doxygen.py
├── [ ] Crear code_map/contracts/patterns/google_style.py
├── [ ] Implementar regex patterns
├── [ ] Tests con "Actia Prueba Tecnica"
└── [ ] Mapeo de formatos a ContractData

Fase 5.4: Parser Nivel 3 - LLM (2 días)
├── [ ] Crear code_map/contracts/llm/extractor.py
├── [ ] Crear code_map/contracts/llm/prompts.py
├── [ ] Integrar con ollama_service.py existente
├── [ ] Validación y sanitización de output
└── [ ] Tests comparativos Nivel 2 vs Nivel 3

Fase 5.5: Parser Nivel 4 - Estático (1 día)
├── [ ] Crear code_map/contracts/patterns/static.py
├── [ ] Implementar detección de asserts, throws, mutex
└── [ ] Tests con código real

Fase 5.6: Discovery Pipeline (1 día)
├── [ ] Crear code_map/contracts/discovery.py
├── [ ] Orquestar niveles 1-5
├── [ ] Agregar resultados con confidence scores
└── [ ] Tests end-to-end

Fase 5.7: Rewriter (2 días)
├── [ ] Crear code_map/contracts/rewriter.py
├── [ ] Implementar inserción en ubicación canónica
├── [ ] Implementar actualización de bloque existente
├── [ ] Preservación de indentación y formato
└── [ ] Tests de diff mínimo

Fase 5.8: API y CLI (1 día)
├── [ ] Crear code_map/api/contracts.py
├── [ ] Añadir comandos CLI
└── [ ] Tests de integración

Total estimado: 11 días de desarrollo
```

### 9.2 Entregables por Fase

| Fase | Entregable | Verificación |
|------|------------|--------------|
| 5.1 | `schema.py` con modelos | Tests pasan |
| 5.2 | Parser @aegis funcional | Extrae contratos sintéticos |
| 5.3 | Parser Doxygen/Google | Extrae contratos de Actia |
| 5.4 | Parser LLM | Compara con Nivel 2, ≥70% match |
| 5.5 | Parser estático | Detecta asserts en código real |
| 5.6 | Pipeline completo | Analiza proyecto entero |
| 5.7 | Rewriter | Diffs ≤15 líneas |
| 5.8 | API lista | Endpoints funcionan |

---

## 10. Preguntas para Decisión

Antes de comenzar implementación:

1. **Formato exacto del bloque AEGIS**: ¿El schema YAML propuesto es suficiente o necesitas campos adicionales?

2. **Prioridad de lenguajes**: ¿Empezamos con C++ (por Actia) o Python (más simple)?

3. **Nivel 3 obligatorio**: ¿Ollama debe ser obligatorio para el modo DESCUBRIR o es aceptable que falle gracefully al Nivel 4?

4. **Versión Python del proyecto de prueba**: Mencionaste que hay versión Python - ¿dónde está? Sería útil para validar el parser Python también.
