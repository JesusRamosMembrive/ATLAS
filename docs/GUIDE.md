# Claude Prompt Library - Guía Completa

## 🎯 Propósito

Esta herramienta resuelve un problema real: **perder el control al desarrollar con AI agents**.

**Solución**: Estructura y metodología que mantiene al humano en control mediante:
- Desarrollo incremental por fases
- Aprobación explícita antes de implementar
- Balance entre simplicidad y estructura
- Tests end-to-end continuos

---

## 📁 Qué contiene este proyecto

### 1. **Templates reutilizables** (`templates/basic/.claude/`)
Archivos que se copian a proyectos nuevos:
- `00-project-brief.md` - Define qué construyes y qué NO
- `01-current-phase.md` - Tracking de progreso y decisiones
- `02-stage1-rules.md` - Reglas para prototipado
- `02-stage2-rules.md` - Reglas para estructuración
- `02-stage3-rules.md` - Reglas para escalado

### 2. **Biblioteca de prompts** (`PROMPT_LIBRARY.md`)
Prompts probados para situaciones comunes:
- Debugging
- Refactoring
- Architecture decisions
- Testing strategy
- Feature planning
- Emergency situations

### 3. **Script de inicialización** (`init_project.py` - Phase 1)
Copia templates a proyectos nuevos con placeholders personalizados.

### 4. **Metodología probada** (`.claude/` de ESTE proyecto)
Ejemplo vivo de cómo aplicar la metodología a un proyecto real.

---

## 🚀 Cómo usar

### Escenario A: Inicializar proyecto nuevo

**Cuando esté implementado Phase 1:**
```bash
python init_project.py my-awesome-project
cd my-awesome-project
# Listo - tienes .claude/ configurado
```

**Mientras tanto (manual):**
```bash
mkdir my-project
cp -r templates/basic/.claude my-project/
cd my-project
# Edita los templates manualmente
```

### Escenario B: Consultar biblioteca de prompts

1. Abre `PROMPT_LIBRARY.md`
2. Encuentra el prompt relevante (debugging, refactoring, etc.)
3. Cópialo y personalízalo
4. Úsalo en tu conversación con Claude Code

### Escenario C: Aprender la metodología

1. Lee este proyecto como ejemplo
2. Observa cómo `.claude/` guía el desarrollo
3. Sigue `QUICK_START.md` para desarrollar Phase 1
4. Aplica lo aprendido a tus proyectos

---

## 🧠 La Metodología en 5 Minutos

### Principio Core
**Control mediante estructura, no restricción**

No es "no uses IA", es "usa IA de forma que mantengas el control".

### Las 3 Etapas

#### ETAPA 1: Prototipado (días 1-3)
- **Objetivo**: Probar que la idea funciona
- **Regla de oro**: Lo MÁS SIMPLE que funciona
- **Output**: 1-2 archivos, hardcoded, cero abstracciones
- **Señal de éxito**: Funciona en <5 minutos

#### ETAPA 2: Estructuración (días 4-10)
- **Objetivo**: Añadir estructura para mantener
- **Regla de oro**: Estructura SOLO para dolor real
- **Output**: Módulos claros, 5-7 archivos, patterns justificados
- **Señal de éxito**: Cambios localizados a 1-3 archivos

#### ETAPA 3: Escalado (semanas 2+)
- **Objetivo**: Preparar para crecimiento real
- **Regla de oro**: Cada decisión basada en evidencia
- **Output**: Arquitectura robusta, extensible, documentada
- **Señal de éxito**: Múltiples usuarios/equipos lo usan

### El Workflow

```
1. Define fase → 2. Propón plan → 3. APRUEBA → 4. Implementa → 5. Review → 6. Test → 7. Actualiza docs → 8. Repite
        ↑                                                                                                        ↓
        └────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

**Clave**: El humano aprueba ANTES de implementar, no después.

---

## 📋 Estructura de archivos `.claude/`

### `00-project-brief.md` - El Norte
Define:
- ¿Qué construyes?
- ¿Cuál es el caso mínimo de éxito?
- ¿Qué NO harás? (scope)

**Actualizas**: Solo si el proyecto cambia de dirección.

### `01-current-phase.md` - El Diario
Registra:
- En qué etapa estás
- Qué estás haciendo hoy
- Decisiones tomadas
- Próximos pasos

**Actualizas**: Al final de CADA sesión.

### `02-stageN-rules.md` - Las Reglas
Definen:
- Qué está permitido en esta etapa
- Qué está prohibido
- Señales para cambiar de etapa

**Actualizas**: Nunca (son fijos por etapa).

---

## 🎓 Filosofía de Uso con Claude Code

### ✅ DO

**Inicio de sesión:**
```
Lee .claude/00-project-brief.md y .claude/01-current-phase.md
Resume: ¿qué construimos? ¿en qué fase estamos?
```

**Planificación:**
```
Propón el plan para [feature].
NO implementes. Espera mi aprobación.
```

**Implementación iterativa:**
```
Implementa [archivo X].
Muéstrame el código completo.
Espera mi review antes del siguiente archivo.
```

**Checkpoints frecuentes:**
```
Review contra .claude/02-stage1-rules.md:
¿Cumplimos las reglas? ¿Algo que sobra o falta?
```

### ❌ DON'T

- ❌ No dejar que Claude implemente sin aprobar plan
- ❌ No saltar la fase de planificación
- ❌ No implementar múltiples archivos a la vez
- ❌ No olvidar actualizar `01-current-phase.md`
- ❌ No avanzar sin tests pasando

---

## 🔧 Desarrollo de ESTE Proyecto

### Estado Actual
- **Phase**: 0 (Setup completo) ✅
- **Siguiente**: Phase 1 (Implementar init_project.py)

### Para contribuir
1. Lee `.claude/` de este proyecto
2. Sigue `QUICK_START.md`
3. Respeta `02-stage1-rules.md`
4. Actualiza `01-current-phase.md` al terminar

### Roadmap
- [ ] Phase 1: Script básico de copia de templates
- [ ] Phase 2: Biblioteca de prompts organizada
- [ ] Phase 3: Múltiples tipos de templates
- [ ] Phase 4: Init interactivo
- [ ] Phase 5: Inserción de prompts en proyecto

---

## 🎯 Casos de Uso Reales

### Caso 1: Developer experimentando con IA
**Problema**: "Pierdo el control, el código se vuelve un desastre"
**Solución**: Usa templates → Define fases claras → Aprueba antes de implementar

### Caso 2: Startup construyendo MVP
**Problema**: "La IA hace todo muy complejo muy rápido"
**Solución**: Etapa 1 forzada → Simplicidad extrema → Evoluciona con dolor real

### Caso 3: Equipo adoptando IA
**Problema**: "Cada dev usa IA diferente, código inconsistente"
**Solución**: Templates compartidos → Metodología única → Reviews consistentes

### Caso 4: Proyecto maduro añadiendo features
**Problema**: "No sabemos cuándo añadir estructura vs mantener simple"
**Solución**: Etapas claras → Criterios explícitos → Decisiones basadas en evidencia

---

## 🧰 Herramientas Complementarias

### Durante Desarrollo
- **Claude Code**: Para implementación
- `test_full_flow.sh`: Para validar que todo funciona
- `.claude/01-current-phase.md`: Para tracking
- `PROMPT_LIBRARY.md`: Para situaciones comunes

### Review y Refactoring
- Prompts de simplification
- Checklist de code smells
- Pattern validation prompts

### Transiciones de Etapa
- Criterios en `02-stageN-rules.md`
- Phase transition check prompt
- Retrospectiva en `01-current-phase.md`

---

## 🎓 Aprende Más

### Orden recomendado:
1. **`README.md`** - Overview rápido
2. **Este archivo** - Guía completa
3. **`.claude/00-project-brief.md`** - Ver ejemplo de brief
4. **`.claude/01-current-phase.md`** - Ver tracking en acción
5. **`QUICK_START.md`** - Empezar a desarrollar
6. **`PROMPT_LIBRARY.md`** - Explorar prompts útiles

### Documentos por situación:
- "Voy a empezar un proyecto nuevo" → `QUICK_START.md`
- "Necesito un prompt para X" → `PROMPT_LIBRARY.md`
- "¿En qué etapa debería estar?" → `.claude/02-stageN-rules.md`
- "¿Cómo funciona todo esto?" → Este archivo
- "¿Qué hace este proyecto?" → `README.md`

---

## 💡 Consejos Prácticos

### Para Mantener Control
1. **Nunca** dejes que Claude implemente sin ver el plan primero
2. **Siempre** revisa código generado antes de aprobar el siguiente paso
3. **Actualiza** `01-current-phase.md` religiosamente
4. **Corre** `test_full_flow.sh` frecuentemente

### Para Evitar Over-Engineering
1. Pregúntate: "¿Esto resuelve dolor ACTUAL?"
2. Si la respuesta incluye "podría" o "futuro" → NO
3. Usa simplification prompts regularmente
4. Cuestiona cada abstracción

### Para Evitar Under-Engineering
1. Si copias código 3+ veces → extrae
2. Si cambios requieren tocar 5+ archivos → añade capa
3. Si tests son frágiles → añade boundaries
4. Pero solo DESPUÉS de sentir el dolor

### Para Transiciones de Etapa
1. No cambies de etapa "porque sí"
2. Requiere evidencia clara de dolor
3. Revisa criterios explícitos en rules
4. Documenta por qué cambias en `01-current-phase.md`

---

## 🤝 Filosofía Final

Este proyecto no es sobre "hacer las cosas bien" o "seguir best practices".

Es sobre **mantener el control mientras usas herramientas poderosas**.

La metodología es una guía, no una camisa de fuerza:
- Adáptala a tu contexto
- Modifícala si necesitas
- Pero mantén el principio core: **tú decides, la IA ejecuta**

---

## ❓ FAQ

**P: ¿Tengo que seguir esto religiosamente?**
R: No. Es una guía. Toma lo que te sirva, adapta el resto.

**P: ¿Qué pasa si mi proyecto no cabe en las 3 etapas?**
R: Las etapas son aproximadas. Ajústalas a tu realidad.

**P: ¿Puedo usar esto con otros AI tools además de Claude Code?**
R: Sí. Los principios aplican a cualquier herramienta.

**P: ¿Es esto overkill para proyectos pequeños?**
R: Para proyectos de 1 día, tal vez. Para cualquier cosa >3 días, vale la pena.

**P: ¿Necesito todos los archivos .claude/?**
R: Mínimo `00-project-brief.md` y `01-current-phase.md`. El resto ayuda pero no es obligatorio.

**P: ¿Qué hago si pierdo el control del proyecto?**
R: Vuelve a Etapa 1. Simplifica agresivamente. Rebuild incremental.

---

## 📞 Próximos Pasos

1. **Si quieres usar los templates**: Copia `templates/basic/.claude/` a tu proyecto
2. **Si quieres contribuir**: Lee `.claude/` de este proyecto y sigue `QUICK_START.md`
3. **Si quieres entender mejor**: Estudia este proyecto como ejemplo vivo
4. **Si tienes ideas**: Documenta en Issues (cuando exista el repo)

---

**Versión**: 0.1.0 (Phase 0 - Setup)  
**Última actualización**: 2025-10-16  
**Estado**: En desarrollo activo
