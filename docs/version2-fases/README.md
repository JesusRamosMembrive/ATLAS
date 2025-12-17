# AEGIS v2: Plan de Implementación por Fases

**Instance Map + Class Truth: Arquitectura visual con contratos verificables**

---

## Estructura de Documentación

```
docs/
├── version2-plan.md                    # Plan general (overview)
├── version2-anexo-fase5.md             # Anexo: Pipeline de descubrimiento
├── version2-anexo-multilenguaje.md     # Anexo: Patrón Strategy
└── version2-fases/
    ├── README.md                       # Este archivo (índice)
    ├── fase0-alignment.md              # Principios y constraints
    ├── fase1-composition-root.md       # Extracción de roots
    ├── fase2-modelo-grafo.md           # InstanceNode, WiringEdge
    ├── fase3-react-flow.md             # UI del grafo
    ├── fase4-panel-lateral.md          # Instancia vs Tipo
    ├── fase5-contratos.md              # Parser/Rewriter (resumen)
    ├── fase6-evidencia-gates.md        # Tests como gates
    ├── fase7-drift.md                  # Detección de desalineaciones
    ├── fase8-agente.md                 # Control del agente
    └── fase9-10-scale-docs.md          # Escalabilidad y docs
```

---

## Resumen de Fases

| Fase | Nombre | Duración Est. | Dependencias |
|------|--------|---------------|--------------|
| 0 | Alineación técnica | 1 día | - |
| 1 | Composition roots | 3-4 días | Fase 0 |
| 2 | Modelo del grafo | 2-3 días | Fase 1 |
| 3 | React Flow UI | 3-4 días | Fase 2 |
| 4 | Panel lateral | 2-3 días | Fase 3 |
| 5 | Contratos embebidos | 11 días | Fase 4 |
| 6 | Evidencia y gates | 4-5 días | Fase 5 |
| 7 | Drift detection | 3-4 días | Fase 5, 6 |
| 8 | Control del agente | 5-6 días | Fase 6, 7 |
| 9-10 | Escalabilidad y docs | 4-5 días | Todas |

**Total estimado**: ~40-45 días de desarrollo

---

## Dependencias entre Fases

```
Fase 0 (Alignment)
    ↓
Fase 1 (Composition Root)
    ↓
Fase 2 (Modelo Grafo)
    ↓
Fase 3 (React Flow) ←──────────────┐
    ↓                              │
Fase 4 (Panel Lateral)             │
    ↓                              │
Fase 5 (Contratos) ─────────────→ Fase 6 (Gates)
    │                              │
    ↓                              ↓
Fase 7 (Drift) ←───────────────────┘
    ↓
Fase 8 (Agente)
    ↓
Fase 9-10 (Scale + Docs)
```

---

## Orden de Lectura Recomendado

### Para entender el concepto
1. [version2-plan.md](../version2-plan.md) - Visión general
2. [fase0-alignment.md](fase0-alignment.md) - Principios

### Para implementar
1. [fase1-composition-root.md](fase1-composition-root.md)
2. [fase2-modelo-grafo.md](fase2-modelo-grafo.md)
3. [fase3-react-flow.md](fase3-react-flow.md)
4. [fase4-panel-lateral.md](fase4-panel-lateral.md)
5. [fase5-contratos.md](fase5-contratos.md) + anexos
6. [fase6-evidencia-gates.md](fase6-evidencia-gates.md)
7. [fase7-drift.md](fase7-drift.md)
8. [fase8-agente.md](fase8-agente.md)
9. [fase9-10-scale-docs.md](fase9-10-scale-docs.md)

### Anexos técnicos
- [version2-anexo-fase5.md](../version2-anexo-fase5.md) - Pipeline de contratos
- [version2-anexo-multilenguaje.md](../version2-anexo-multilenguaje.md) - Patrón Strategy

---

## Proyecto de Prueba

```
/home/jesusramos/Workspace/Actia Prueba Tecnica/
```

Pipeline C++ con:
- 3 módulos (Generator, Filter, Printer)
- Chain of Responsibility pattern
- Contratos documentados en Doxygen
- Tests unitarios e integración

---

## Decisiones Clave

| Decisión | Valor | Razón |
|----------|-------|-------|
| Código como fuente de verdad | Sí | Evita drift código↔modelo |
| Formato de contrato | YAML en bloques delimitados | Parseable y legible |
| Soporte multi-lenguaje | Strategy pattern | Extensible |
| Ollama para discovery | Fallback aceptable | No bloquear si no está |
| Schema inicial | Sin performance/observability | MVP mínimo |

---

## Quick Start para Desarrollo

```bash
# 1. Leer principios
cat docs/version2-fases/fase0-alignment.md

# 2. Entender el proyecto de prueba
ls "/home/jesusramos/Workspace/Actia Prueba Tecnica/"

# 3. Comenzar con Fase 1
# Ver docs/version2-fases/fase1-composition-root.md
```

---

## Contacto y Contribución

Preguntas o sugerencias: abrir issue en el repo o discutir en la documentación.
