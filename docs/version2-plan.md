# Feature: Instance Map, Class Truth

**Arquitectura visual + contratos verificables embebidos en el código**

## Resumen

Esta feature añade una vista de **arquitectura ejecutable** basada en un grafo (estilo pipeline) donde:

* El **mapa** del sistema se construye **por instancias** (runtime composition / wiring).
* La **verdad** del comportamiento se define **por clases/métodos** (contratos y reglas), embebida en el **propio código**.

Principio rector:

> **Instancias para el mapa, clases para la verdad.**

El objetivo es dar **control real** al programador cuando usa agentes: el agente puede tocar lo que quiera, pero el usuario debe saber **qué tocó, por qué, y qué impacto tuvo**, con una UI clara y con gates verificables (tests/linters/etc.).

---

## Motivación

Los agentes CLI son eficaces, pero fallan en control humano por:

* Sobrecarga de logs/salida.
* Cambios demasiado amplios y difíciles de auditar.
* Tendencia a “dejarlo hacer” y arreglar después.

La solución propuesta:

* Un **mapa visual** (React Flow) que explique “cómo se arma” el programa (instancias + conexiones).
* Un sistema de **contratos y evidencia** embebido en el código, para que el control sea verificable y no “texto bonito”.
* Un flujo agente→patch→gates donde la UI sea el “centro de control”.

---

## Alcance del MVP

### Sí (MVP)

* Grafo de pipeline **por instancia** extraído de un “composition root” (por ejemplo `main` en C++).
* Selección de nodos/aristas con navegación al código (jump to source).
* Panel lateral con:

  * **Instancia**: wiring, parámetros (args), configuración efectiva.
  * **Tipo (clase/método)**: contrato estructurado embebido en comentarios/docstrings.
* **Evidencia obligatoria** para contratos marcados como “requeridos” (tests, linters, etc.).
* Integración de agente en modo **patch/auditable**:

  * plan → diff → gates → aplicar.

### No (por ahora)

* UML completo (clases, secuencias, estados generalista con edición completa).
* Import/export de modelos externos.
* Inferencia “mágica” de wiring indirecto (DI/config compleja) fuera de composition roots.

---

## Ejemplo base (pipeline)

En el ejemplo, el pipeline se arma creando instancias `m1/m2/m3`, conectando con `setNext`, y arrancando en orden “sink→source” y parando “source→sink”. 

El contrato de concurrencia y ciclo de vida está en el interfaz `IModule` (thread-safety, idempotencia, restricciones de llamadas). 

Esto es ideal para el MVP: wiring explícito y contrato centralizado.

---

## Modelo conceptual

### 1) Composition Root

Archivo(s)/función(es) donde el programa:

* instancia componentes “de larga vida”
* los conecta (wiring)
* gestiona start/stop/lifecycle

En el MVP: detectar `main` y/o archivos marcados como composition root.

### 2) Grafo por instancia

* **Nodo (InstanceNode)**: una instancia concreta (p. ej. `m2`).
* **Arista (WiringEdge)**: una conexión concreta (p. ej. `m1.setNext(m2)`), con referencia al call-site exacto en código.
* **Tipo asociado**: cada instancia apunta a un símbolo de tipo (clase concreta/resuelta).

### 3) Contrato por clase/método (Class Truth)

Contratos (invariantes, pre/post, errores, concurrencia, observabilidad, límites, rendimiento, etc.) se definen **por símbolo** (clase/método) y viven **dentro del código** como un bloque estructurado.

Regla: el contrato es “verdad” solo si está respaldado por **evidencia** (tests/linters/etc.) cuando se marca como requerido.

### 4) Evidencia y Gates

Cada contrato requerido debe tener:

* referencia a evidencia (tests/targets/linters/jobs)
* estado de ejecución (última pasada, última falla, logs)
* política (bloqueante / warning)

---

## Decisiones tomadas (y consecuencias)

### Código como fuente de verdad

* No existe un “archivo modelo” paralelo.
* La UI edita bloques de contrato embebidos en comentarios/docstrings.
* AEGIS es propietario de esos bloques (delimitados con marcadores) para evitar roturas y diffs caóticos.

Consecuencia: necesitas un **parser + rewriter** robusto y estable.

### Instancia vs clase

* Instancia = wiring, configuración efectiva, “cómo se arma”.
* Clase/método = comportamiento, contratos, semántica verificable.

Consecuencia: el grafo principal será por instancia, pero el panel de verdad será por tipo.

### Control del agente

* El agente puede tocar lo que quiera, pero:

  * siempre genera plan antes de editar
  * siempre entrega patch/diff
  * siempre pasa gates antes de aplicar
  * la UI pinta qué nodos/aristas/símbolos tocó

Consecuencia: diseño diff-first + auditoría.

---

## UI/UX (React Flow)

### React Flow como canvas (no UML)

React Flow se usa para representar **grafos de arquitectura**:

* Nodes: instancias y su tipo/rol.
* Edges: wiring (con call-site).
* Badges: estado (gates, drift, riesgo).

Evita construir un editor UML generalista. La UI se centra en control, navegación y verificación.

### Interacciones mínimas (MVP)

* Click nodo → panel lateral con pestañas **Instancia / Tipo**.
* Click arista → muestra wiring + salto al call-site.
* Search/filter:

  * por nombre de instancia
  * por tipo (clase)
  * por rol (SOURCE/PROCESSING/SINK)
  * por estado (rojo: falta evidencia, warning: drift)

---

## Plan para Codex

**Implementación por fases y pasos (checklist)**

### Fase 0 — Alineación técnica y constraints (no negociables)

* [ ] Documentar en `docs/` el principio: **instancias para el mapa, clases para la verdad**
* [ ] Definir explícitamente “no second model file”: contratos embebidos en código (comentarios/docstrings)
* [ ] Definir qué se considera “evidencia” y qué gates son bloqueantes en MVP (mínimo: lint + tests)

---

### Fase 1 — Extracción de composition roots (MVP: C++ `main`)

* [ ] Implementar detección de composition root:

  * [ ] Por convención: `main.cpp` / función `main`
  * [ ] (Opcional) Marcado manual desde UI: “Add composition root”
* [ ] Extraer “instanciaciones de larga vida” dentro del composition root:

  * [ ] `auto mX = ...` / `unique_ptr` / factory functions
* [ ] Extraer wiring explícito:

  * [ ] Detectar llamadas `setNext(A, B)` y construir aristas A→B con referencia a call-site
* [ ] Resolver tipo concreto (mínimo viable):

  * [ ] Si se usa factoría, mapear `createX()` → `XModule` cuando sea directo
* [ ] Definir límites MVP:

  * [ ] No soportar DI/config indirecta en esta fase

**DoD Fase 1**

* [ ] Dado un ejemplo como el aportado, se obtiene lista de instancias + aristas y sus ubicaciones

---

### Fase 2 — Modelo interno del grafo (runtime only, sin archivo externo)

* [ ] Definir estructuras internas:

  * [ ] `InstanceNode` (id, nombre instancia, tipo asociado, rol, location, args)
  * [ ] `WiringEdge` (from, to, callsite location, “channel”/método, metadata)
* [ ] Añadir rol heurístico inicial:

  * [ ] SOURCE / SINK / PROCESSING basado en patrones simples (p. ej. no-op, ausencia de `setNext`, etc.)
  * [ ] Permitir override manual desde UI (MVP)
* [ ] Persistencia de sesión (MVP):

  * [ ] Recalcular desde código al refrescar (sin mantener un “modelo” paralelo)

**DoD Fase 2**

* [ ] Estructuras listas para renderizar, con navegación a posiciones de código

---

### Fase 3 — React Flow: render del grafo por instancia

* [ ] Integrar React Flow como vista principal “Architecture Graph”
* [ ] Crear node types:

  * [ ] Node “ModuleInstance” con nombre instancia, tipo, rol, badges
* [ ] Crear edge types:

  * [ ] Edge “Wiring” con etiqueta mínima (`setNext`, o canal equivalente)
* [ ] Layout MVP:

  * [ ] Para pipelines lineales: auto-layout simple izquierda→derecha
  * [ ] Para grafos generales: layout incremental (sin obsesión por estética perfecta)
* [ ] Interacción:

  * [ ] Selección nodo/arista
  * [ ] Zoom/pan
  * [ ] Fit view

**DoD Fase 3**

* [ ] Se visualiza el pipeline y se puede seleccionar cada pieza

---

### Fase 4 — Panel lateral: Instancia vs Tipo (progressive disclosure)

* [ ] Implementar panel lateral con dos pestañas:

  * [ ] **Instancia**
  * [ ] **Tipo**
* [ ] Instancia (MVP):

  * [ ] Mostrar call-site de creación (si existe)
  * [ ] Mostrar args/config efectiva (p. ej. parámetros de factoría)
  * [ ] Mostrar conexiones entrantes/salientes
* [ ] Tipo (MVP):

  * [ ] Mostrar símbolo (clase/método) y ubicación
  * [ ] Mostrar contrato embebido (si existe)

**DoD Fase 4**

* [ ] Click en nodo → panel muestra datos de instancia y tipo con navegación al código

---

### Fase 5 — Contratos embebidos en el código (parser + rewriter)

* [ ] Definir “schema” de contrato (mínimo):

  * [ ] Invariantes
  * [ ] Precondiciones / Postcondiciones
  * [ ] Errores esperados
  * [ ] Concurrencia y modelo de thread-safety
  * [ ] Observabilidad (logs/metrics)
  * [ ] Límites/rendimiento (presupuestos)
* [ ] Definir formato embebido:

  * [ ] Bloques delimitados por marcadores BEGIN/END en comentario/docstring
  * [ ] Contenido estructurado (estable, parseable)
* [ ] Implementar lectura:

  * [ ] Localizar bloque asociado a símbolo (clase/método)
  * [ ] Parsear contenido a estructura interna
* [ ] Implementar escritura:

  * [ ] Insertar bloque si no existe (en ubicación canónica)
  * [ ] Reescribir solo el bloque, preservando el resto del archivo
  * [ ] Estabilizar formato para minimizar diffs
* [ ] Soporte por lenguaje (MVP):

  * [ ] C++: comentarios cerca de la declaración
  * [ ] Python: docstring en función/clase

**DoD Fase 5**

* [ ] Editas un contrato desde la UI y se refleja como diff mínimo en el código, sin archivos extra

---

### Fase 6 — Evidencia obligatoria + Gates (control verificable)

* [ ] Definir “evidence types” (MVP):

  * [ ] Test unitario
  * [ ] Test integración
  * [ ] Lint/format
  * [ ] Typecheck (si aplica)
* [ ] Extender schema de contrato para referenciar evidencia:

  * [ ] Qué evidencia lo cubre
  * [ ] Política: required / optional
* [ ] Integrar ejecución de gates (MVP):

  * [ ] Ejecutar lint + tests
  * [ ] Capturar resultado y asociarlo a nodos/tipos
* [ ] UI:

  * [ ] Badges por nodo (rojo si contrato required sin evidencia o evidencia fallando)
  * [ ] Panel muestra evidencias, última ejecución, y estado

**DoD Fase 6**

* [ ] Si un contrato required no tiene evidencia o falla, el grafo lo muestra claramente y bloquea “apply”

---

### Fase 7 — Drift detection (sin modelo externo, pero con coherencia)

* [ ] Drift estructural (MVP):

  * [ ] Cambios de firma en métodos con contrato
  * [ ] Contrato referencia a evidencia inexistente
* [ ] Drift de wiring (MVP):

  * [ ] Aristas que desaparecen/aparecen al reanalizar el composition root
* [ ] Drift semántico (heurístico, MVP-light):

  * [ ] Señalar contradicciones obvias contrato↔implementación cuando sean detectables
* [ ] UI:

  * [ ] Badges “drift”
  * [ ] Lista de drift items con jump-to-code

**DoD Fase 7**

* [ ] Al modificar código, la UI detecta desalineaciones relevantes y las hace visibles

---

### Fase 8 — Integración con agente en modo “controlable”

* [ ] Definir protocolo de ejecución del agente:

  * [ ] Siempre produce **PLAN** antes de editar
  * [ ] Siempre produce **PATCH/DIFF** (no ediciones invisibles)
  * [ ] Siempre corre **GATES** antes de permitir apply
* [ ] Inputs al agente:

  * [ ] Nodo(s) seleccionados (instancias y tipos)
  * [ ] Contratos relevantes (solo lo estructurado)
  * [ ] Evidencia requerida (qué debe pasar)
* [ ] Salidas del agente:

  * [ ] Lista de archivos tocados
  * [ ] Lista de símbolos tocados
  * [ ] Mapeo a nodos del grafo
* [ ] UI:

  * [ ] Resaltar nodos/aristas afectadas por el patch
  * [ ] Vista de diff por archivo y por símbolo
  * [ ] Botón apply solo si gates OK

**DoD Fase 8**

* [ ] “Control” tangible: el usuario ve qué cambia, dónde, y si pasa evidencia antes de aplicar

---

### Fase 9 — Escalabilidad y extensibilidad

* [ ] Caching incremental del análisis (no reparse total)
* [ ] Múltiples composition roots:

  * [ ] Vistas por ejecutable/pipeline
* [ ] Plugins de wiring:

  * [ ] Soporte gradual para wiring indirecto (builders/config/DI)
* [ ] Refinar rol inference:

  * [ ] Permitir “role = manual” persistente vía código (sin archivo extra)

**DoD Fase 9**

* [ ] Repos medianos/grandes siguen siendo usables sin grafo ruidoso

---

### Fase 10 — Documentación y criterios de aceptación

* [ ] Documentar workflow end-to-end:

  * [ ] Descubrir pipeline
  * [ ] Añadir contrato
  * [ ] Vincular evidencia
  * [ ] Ejecutar agente con patch controlado
* [ ] Añadir checklist de calidad:

  * [ ] “Si no pasa gates, no se aplica”
  * [ ] “Si hay drift, se avisa”
* [ ] Añadir guía de estilo para contratos embebidos (para minimizar diffs)

**DoD Fase 10**

* [ ] Un usuario puede replicar el flujo sin contexto interno del proyecto

---

## Preguntas abiertas (no bloqueantes, pero conviene cerrarlas)

1. ¿En el MVP quieres **solo detección automática** de composition root (por convención) o también **selección manual** desde la UI?
2. ¿Qué gates mínimos bloqueantes quieres desde el día 1 para C++ y Python (por ejemplo: `clang-tidy`/`ctest`/`pytest`/`ruff`/`mypy`)?

No necesito respuesta para entregarte este plan; solo afectan a qué tareas exactas se consideran “MVP completo”.
