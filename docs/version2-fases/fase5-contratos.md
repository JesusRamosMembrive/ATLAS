# Fase 5: Contratos Embebidos en Código

**Objetivo**: Parser y rewriter para contratos dentro de comentarios/docstrings

---

## Documentos de Referencia

Esta fase tiene documentación detallada en anexos separados:

| Anexo | Contenido |
|-------|-----------|
| [version2-anexo-fase5.md](../version2-anexo-fase5.md) | Pipeline de descubrimiento, schema, API |
| [version2-anexo-multilenguaje.md](../version2-anexo-multilenguaje.md) | Patrón Strategy, implementaciones C++/Python |

---

## Resumen Ejecutivo

### Principio: Separar CREAR de DESCUBRIR

| Modo | Confianza | Herramienta |
|------|-----------|-------------|
| **CREAR** | 100% | Usuario define, formato AEGIS |
| **DESCUBRIR** | Variable | Pipeline de 5 niveles |

### Pipeline de Descubrimiento

```
Nivel 1 (100%) → @aegis-contract blocks
Nivel 2 (80%)  → Patrones conocidos (Doxygen, Google style)
Nivel 3 (60%)  → Extracción LLM (Ollama) - fallback aceptable
Nivel 4 (40%)  → Análisis estático (asserts, throws)
Nivel 5 (0%)   → Sin contrato detectado
```

### Formato @aegis-contract

**C++:**
```cpp
// @aegis-contract-begin
// thread_safety: safe_after_start
// invariants:
//   - pipeline must be started before process()
// evidence:
//   - test: tests/module_test.cpp::TestFlow
// @aegis-contract-end
class ProcessingModule : public IModule {
```

**Python:**
```python
class ProcessingModule(IModule):
    """
    @aegis-contract-begin
    thread_safety: safe_after_start
    invariants:
      - pipeline must be started before process()
    @aegis-contract-end

    Docstring normal continúa aquí...
    """
```

---

## Schema del Contrato (MVP)

```yaml
thread_safety: not_safe | safe | safe_after_start | immutable
lifecycle: string           # "stopped -> running -> stopped"
invariants: list[string]
preconditions: list[string]
postconditions: list[string]
errors: list[string]
dependencies: list[string]  # Módulos requeridos
evidence:
  - test: string
    policy: required | optional
  - lint: string
```

---

## Arquitectura: Patrón Strategy

```
code_map/contracts/
├── schema.py              # ContractData, EvidenceItem
├── discovery.py           # Pipeline orquestador
├── rewriter.py            # Escritura de contratos
├── llm/
│   ├── extractor.py      # Nivel 3: Ollama
│   └── prompts.py        # Templates
├── patterns/
│   ├── aegis.py          # Nivel 1
│   ├── doxygen.py        # Nivel 2
│   └── static.py         # Nivel 4
└── languages/
    ├── base.py           # LanguageStrategy (ABC)
    ├── registry.py       # LanguageRegistry
    ├── cpp.py            # CppLanguageStrategy
    └── python.py         # PythonLanguageStrategy
```

Ver [version2-anexo-multilenguaje.md](../version2-anexo-multilenguaje.md) para detalles completos.

---

## Spike Técnico (Pre-implementación)

**Duración**: 2-3 días
**Proyecto de prueba**: `/home/jesusramos/Workspace/Actia Prueba Tecnica/`

### Tareas

```
[ ] Día 1: Parser Nivel 1 y 2 (C++)
    [ ] Parser @aegis-contract
    [ ] Parser Doxygen
    [ ] Test: extraer de IModule.h

[ ] Día 2: Rewriter
    [ ] Insertar bloque nuevo
    [ ] Actualizar bloque existente
    [ ] Test: diff ≤15 líneas

[ ] Día 3: Nivel 3 (LLM)
    [ ] Integrar con ollama_service.py
    [ ] Comparar con Nivel 2
```

### Criterios de Éxito

| Criterio | Métrica |
|----------|---------|
| Parsing Nivel 2 | ≥80% de contratos extraídos |
| Rewriting | Diff ≤15 líneas |
| No rompe código | Archivo compila después |
| LLM accuracy | ≥70% match con Nivel 2 |

---

## API

```yaml
# Descubrir contratos
POST /api/contracts/discover
  body:
    file_path: string
    symbol_name?: string
    levels?: [1,2,3,4]
  response:
    contracts: ContractData[]
    stats: DiscoveryStats

# Escribir contrato
POST /api/contracts/write
  body:
    file_path: string
    symbol_name: string
    contract: ContractData
  response:
    success: bool
    diff: string

# Validar evidencia
POST /api/contracts/validate
  body:
    file_path: string
    symbol_name: string
  response:
    contract: ContractData
    evidence_status: EvidenceResult[]
```

---

## Fases de Implementación

| Sub-fase | Duración | Entregable |
|----------|----------|------------|
| 5.1 Schema | 1 día | `schema.py` con modelos |
| 5.2 Nivel 1 | 1 día | Parser @aegis-contract |
| 5.3 Nivel 2 | 2 días | Doxygen + Google style |
| 5.4 Nivel 3 | 2 días | Extracción LLM |
| 5.5 Nivel 4 | 1 día | Análisis estático |
| 5.6 Discovery | 1 día | Pipeline completo |
| 5.7 Rewriter | 2 días | Inserción + actualización |
| 5.8 API | 1 día | Endpoints REST |

**Total**: ~11 días

---

## Dependencias

### Ollama (Nivel 3)

- **Obligatorio**: No (fallback a Nivel 4)
- **Recomendado**: `llama3.2:3b` o `codellama:7b`
- **Integración**: Reutiliza `code_map/integrations/ollama_service.py`

### AEGIS v1

| Componente | Uso |
|------------|-----|
| `c_analyzer.py` | `_find_leading_comment()` |
| `ollama_service.py` | `chat_with_ollama()` |
| `models.py` | Extender `SymbolInfo` |

---

## Checklist General

```
[ ] Spike técnico completado y validado
[ ] Schema definido
[ ] LanguageStrategy implementado (base + C++ + Python)
[ ] Pipeline de discovery funcional
[ ] Rewriter con diffs mínimos
[ ] API endpoints implementados
[ ] Tests con Actia
[ ] Integración con UI (panel Type)
```

---

## DoD

- [ ] Extraer contratos de IModule.h (Actia)
- [ ] Crear contrato desde UI → diff en código
- [ ] Actualizar contrato → solo cambia bloque AEGIS
- [ ] Nivel 3 funciona con Ollama (o skip graceful)
- [ ] Confianza visible en UI por nivel
