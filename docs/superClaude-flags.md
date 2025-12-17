# SuperClaude Flags Reference

Referencia completa de flags disponibles en el framework SuperClaude.

---

## Flags de Profundidad de Análisis

| Flag | Tokens | Descripción |
|------|--------|-------------|
| `--think` | ~4K | Análisis estructurado estándar, activa Sequential MCP |
| `--think-hard` | ~10K | Análisis profundo, activa Sequential + Context7 |
| `--ultrathink` | ~32K | Máxima profundidad, activa todos los MCP servers |

---

## Flags de MCP Servers

| Flag | Servidor | Cuándo usar |
|------|----------|-------------|
| `--c7` / `--context7` | Context7 | Documentación oficial de librerías/frameworks |
| `--seq` / `--sequential` | Sequential | Razonamiento multi-paso, debugging complejo |
| `--magic` | Magic (21st.dev) | Componentes UI, diseño frontend |
| `--morph` / `--morphllm` | Morphllm | Bulk edits, transformaciones de código |
| `--serena` | Serena | Operaciones de símbolos, memoria de proyecto |
| `--play` / `--playwright` | Playwright | Testing E2E, automatización browser |
| `--chrome` / `--devtools` | Chrome DevTools | Performance, debugging, network analysis |
| `--tavily` | Tavily | Web search, investigación en tiempo real |
| `--frontend-verify` | Playwright + DevTools + Serena | Verificación completa de frontend |
| `--all-mcp` | Todos | Máxima capacidad (escenarios muy complejos) |
| `--no-mcp` | Ninguno | Solo herramientas nativas |

---

## Flags de Ejecución

| Flag | Descripción |
|------|-------------|
| `--delegate [auto\|files\|folders]` | Habilita sub-agentes para procesamiento paralelo |
| `--concurrency [n]` | Control de operaciones concurrentes (1-15) |
| `--loop` | Ciclos iterativos de mejora (polish, refine) |
| `--iterations [n]` | Número de ciclos de mejora (1-10) |
| `--validate` | Pre-validación y gates antes de ejecutar |
| `--safe-mode` | Máxima validación, ejecución conservadora |

---

## Flags de Output

| Flag | Descripción |
|------|-------------|
| `--uc` / `--ultracompressed` | Modo token-eficiente, símbolos en lugar de texto |
| `--scope [file\|module\|project\|system]` | Define el alcance del análisis |
| `--focus [área]` | Foco específico (ver áreas abajo) |

### Áreas para `--focus`

- `performance` - Optimización de rendimiento
- `security` - Seguridad y vulnerabilidades
- `quality` - Calidad de código
- `architecture` - Diseño arquitectónico
- `accessibility` - Accesibilidad
- `testing` - Tests y cobertura

---

## Flags de Modo

| Flag | Descripción |
|------|-------------|
| `--brainstorm` / `--bs` | Modo descubrimiento colaborativo |
| `--introspect` | Meta-cognición, auto-análisis |
| `--task-manage` | Gestión jerárquica de tareas con memoria |
| `--research` | Investigación profunda con Tavily |

---

## Reglas de Prioridad

```
Seguridad:     --safe-mode > --validate > otros
Profundidad:   --ultrathink > --think-hard > --think
MCP:           --no-mcp anula todos los MCP individuales
Scope:         system > project > module > file
```

---

## Ejemplos de Uso

### Implementación con validación
```
--think-hard --validate
```

### Debugging complejo
```
--ultrathink --seq
```

### Refactoring de UI
```
--think --magic --loop
```

### Investigación web
```
--research --tavily
```

### Máxima seguridad en producción
```
--safe-mode --validate
```

### Edición masiva de código
```
--morph --delegate
```

### Análisis de performance frontend
```
--frontend-verify --focus performance
```

### Análisis arquitectónico profundo
```
--ultrathink --focus architecture --scope system
```

### Revisión de seguridad
```
--think-hard --focus security --validate
```

---

## Combinaciones Recomendadas por Tarea

| Tarea | Flags recomendados |
|-------|-------------------|
| Nueva feature | `--think-hard --validate` |
| Bug fix complejo | `--ultrathink --seq` |
| Refactoring | `--think --loop --iterations 3` |
| Code review | `--think --focus quality` |
| UI components | `--think --magic` |
| Performance tuning | `--think-hard --focus performance` |
| Security audit | `--ultrathink --focus security --validate` |
| Documentación | `--think --c7` |
| Testing E2E | `--play --frontend-verify` |
| Investigación | `--research --tavily` |
