# AEGIS v2 - Editor UML para Model-Driven Development con Agentes

## Visión del Proyecto

AEGIS v2 es un editor visual de UML diseñado para trabajar con agentes de programación. El objetivo es separar claramente los roles:

- **Humano (Arquitecto)**: Define la estructura completa del sistema mediante diagramas UML enriquecidos con descripciones semánticas
- **Agente (Implementador)**: Recibe especificaciones precisas y genera código que cumple exactamente con el diseño

Esta separación resuelve los principales problemas de trabajar con agentes:
1. **Contexto limitado** → El UML proporciona el contexto completo del sistema
2. **Ambigüedad** → Tipos, firmas y relaciones están formalmente definidos
3. **Coherencia arquitectónica** → El humano controla la arquitectura global

## Stack Tecnológico

| Componente | Tecnología | Justificación |
|------------|------------|---------------|
|Editor Visual (Canvas) | React Flow |Visualización de arquitectura y conexiones
|State Management | React | Zustand | Gestión reactiva del estado complejo sin re-renders innecesarios
|UI Components |	Shadcn/UI|	Componentes accesibles para el Panel Lateral (Forms, Tabs, Dialogs)
|Estado Interno	|JSON	|Parsing nativo en JS, tipado con TypeScript
|Validación Sintáctica	|Zod	|Validación de esquemas y formularios en tiempo real
|Validación Semántica|	Custom TS Logic	|Chequeo de integridad referencial y lógica de negocio
|Export para Agente	|XML|	Tags semánticos optimizados para LLMs
## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           AEGIS v2 Editor                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────┐   Select    ┌──────────────────┐    ┌──────────────┐    │
│  │ React Flow │────────────▶│  Zustand Store   │◀───│ Side Panel   │    │
│  │  (Canvas)  │◀────────────│ (Project State)  │───▶│ (Inspector)  │    │
│  └────────────┘             └───────────────┬──┘    └──────────────┘    │
│                                             │                           │
│                                             ▼                           │
│   ┌──────────────┐                  ┌───────────────┐                   │
│   │ Type Mapper  │◀─────────────────│ Semantic      │                   │
│   │ (Abstract -> │                  │ Validator     │                   │
│   │  Target Lang)│                  │ (Logic Check) │                   │
│   └──────┬───────┘                  └───────────────┘                   │
│          │                                                              │
│          ▼                                                              │
│   ┌──────────────┐                  ┌───────────────┐                   │
│   │ XML Compiler │─────────────────▶│ Agent Loop    │                   │
│   │ (Exporter)   │                  │ (Claude/GPT)  │                   │
│   └──────────────┘                  └───────────────┘                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```
**Concepto: Type Mapper**: El editor trabaja con "Tipos Abstractos" (Text, Number, Logic, Decimal, List) 
para ser agnóstico del lenguaje. Al exportar, el Type Mapper traduce:
List<Text> → List<String> (Java)
List<Text> → List[str] (Python)
List<Text> → string[] (TypeScript)


## Modelo de Datos

### Jerarquía de Entidades

```
Project
  └── Module (agrupación lógica, como packages)
        ├── Class
        │     ├── Attributes
        │     └── Methods
        │           ├── Parameters
        │           ├── Preconditions
        │           ├── Postconditions
        │           ├── Throws
        │           ├── Hints (campo custom)
        │           └── TestCases
        ├── Interface
        ├── Enum
        └── Relationships (entre clases/interfaces)
```

### Schema JSON Completo

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AEGIS v2 Project Schema",
  
  "project": {
    "name": "string",
    "version": "string",
    "description": "string",
    "targetLanguage": "python | typescript | java",
    
    "modules": [
      {
        "id": "uuid",
        "name": "string",
        "description": "string",
        
        "classes": [
          {
            "id": "uuid",
            "name": "string",
            "description": "string",
            "isAbstract": "boolean",
            "extends": "string | null",
            "implements": ["string"],
            
            "attributes": [
              {
                "id": "uuid",
                "name": "string",
                "type": "string",
                "visibility": "public | private | protected",
                "description": "string",
                "defaultValue": "string | null",
                "isStatic": "boolean",
                "isReadonly": "boolean"
              }
            ],
            
            "methods": [
              {
                "id": "uuid",
                "name": "string",
                "visibility": "public | private | protected",
                "description": "string",
                "isStatic": "boolean",
                "isAsync": "boolean",
                
                "parameters": [
                  {
                    "name": "string",
                    "type": "string",
                    "description": "string",
                    "isOptional": "boolean",
                    "defaultValue": "string | null"
                  }
                ],
                
                "returnType": "string",
                "returnDescription": "string",
                
                "preconditions": ["string"],
                "postconditions": ["string"],
                
                "throws": [
                  {
                    "exception": "string",
                    "when": "string"
                  }
                ],
                
                "hints": {
                  "edgeCases": ["string"],
                  "performance": ["string"],
                  "style": ["string"],
                  "custom": ["string"]
                },
                
                "testCases": [
                  {
                    "name": "string",
                    "type": "success | error | edge",
                    "description": "string"
                  }
                ]
              }
            ]
          }
        ],
        
        "interfaces": [
          {
            "id": "uuid",
            "name": "string",
            "description": "string",
            "extends": ["string"],
            
            "methods": [
              {
                "name": "string",
                "description": "string",
                "parameters": [
                  {
                    "name": "string",
                    "type": "string",
                    "description": "string"
                  }
                ],
                "returnType": "string"
              }
            ]
          }
        ],
        
        "enums": [
          {
            "id": "uuid",
            "name": "string",
            "description": "string",
            "values": [
              {
                "name": "string",
                "description": "string",
                "value": "string | number | null"
              }
            ]
          }
        ],
        
        "relationships": [
          {
            "id": "uuid",
            "type": "inheritance | implementation | composition | aggregation | association | dependency",
            "from": "string (class/interface id)",
            "to": "string (class/interface id)",
            "description": "string",
            "cardinality": "string | null"
          }
        ]
      }
    ]
  }
}
```

## Formato XML de Exportación para Agente

El XML exportado está optimizado para que los LLMs lo interpreten correctamente, usando tags semánticos claros.

### Ejemplo de Exportación

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project name="MyApp" version="1.0.0" language="python">
  <description>Sistema de gestión de usuarios</description>
  
  <module name="users">
    <description>Módulo de gestión de usuarios</description>
    
    <class name="UserService">
      <description>Maneja creación, borrado y estado de usuarios</description>
      
      <attributes>
        <attribute name="repository" type="UserRepository" visibility="private">
          <description>Repositorio de persistencia de usuarios</description>
        </attribute>
      </attributes>
      
      <methods>
        <method name="createUser" visibility="public" returns="User">
          <description>Crea un usuario y lo persiste en base de datos</description>
          
          <parameters>
            <param name="dto" type="CreateUserDTO">
              <description>Datos del nuevo usuario</description>
            </param>
          </parameters>
          
          <preconditions>
            <condition>dto.email debe ser válido</condition>
            <condition>No debe existir usuario con ese email</condition>
          </preconditions>
          
          <postconditions>
            <condition>Usuario existe en repository</condition>
            <condition>Usuario tiene estado PENDING_VERIFICATION</condition>
          </postconditions>
          
          <throws>
            <exception type="DuplicateEmailError">
              Ya existe usuario con ese email
            </exception>
          </throws>
          
          <hints>
            <edge_case>Validar formato de email antes de check duplicados</edge_case>
            <performance>Usar índice único en email para check rápido</performance>
          </hints>
          
          <tests>
            <test type="success">should create user with valid data</test>
            <test type="error">should throw when email duplicated</test>
            <test type="edge">should handle email with unicode characters</test>
          </tests>
        </method>
        
        <method name="removeEvenNumbers" visibility="public" returns="List[int]">
          <description>Recibe una lista y elimina números pares</description>
          
          <parameters>
            <param name="items" type="List[Any]">
              <description>Lista de elementos a filtrar</description>
            </param>
          </parameters>
          
          <preconditions>
            <condition>La lista no debe ser None</condition>
          </preconditions>
          
          <hints>
            <edge_case>La lista puede contener strings, intentar convertir a número</edge_case>
            <edge_case>Si la conversión falla, ignorar el elemento silenciosamente</edge_case>
            <edge_case>Mantener el orden original de los elementos válidos</edge_case>
          </hints>
          
          <tests>
            <test type="success">should remove 2,4 from [1,2,3,4,5]</test>
            <test type="edge">should convert "2" string and remove it</test>
            <test type="edge">should ignore non-convertible strings</test>
          </tests>
        </method>
      </methods>
    </class>
    
    <interface name="UserRepository">
      <description>Contrato de persistencia de usuarios</description>
      
      <methods>
        <method name="save" returns="User">
          <param name="user" type="User"/>
        </method>
        <method name="findById" returns="Optional[User]">
          <param name="id" type="UUID"/>
        </method>
      </methods>
    </interface>
    
    <enum name="UserStatus">
      <description>Estados posibles de un usuario</description>
      <value name="PENDING_VERIFICATION">Esperando confirmación email</value>
      <value name="ACTIVE">Usuario activo</value>
      <value name="SUSPENDED">Usuario suspendido</value>
    </enum>
    
    <relationships>
      <relationship type="dependency" from="UserService" to="UserRepository">
        UserService usa UserRepository para persistencia
      </relationship>
    </relationships>
  </module>
</project>
```

## Tipos de Relaciones UML Soportadas

| Tipo | Descripción | Ejemplo |
|------|-------------|---------|
| `inheritance` | Herencia de clase | `class Admin extends User` |
| `implementation` | Implementación de interfaz | `class UserService implements IUserService` |
| `composition` | Parte inseparable del todo | `User` contiene `UserStatus` (si User muere, Status también) |
| `aggregation` | Parte separable del todo | `Team` tiene `Users` (Users pueden existir sin Team) |
| `association` | Relación genérica | `Order` referencia `Product` |
| `dependency` | Usa pero no posee | `UserService` usa `Logger` |

## Campo Hints - Guía de Uso

El campo `hints` permite dar instrucciones al agente que no encajan en pre/post condiciones formales.

### Categorías Disponibles

```json
"hints": {
  "edgeCases": [
    "Strings se convierten a número si es posible",
    "Valores null se tratan como lista vacía"
  ],
  "performance": [
    "Usar list comprehension en vez de filter()",
    "Cachear resultado si input > 1000 elementos"
  ],
  "style": [
    "Nombrar variables en español",
    "Usar early return pattern"
  ],
  "custom": [
    "Cualquier instrucción adicional para el agente"
  ]
}
```

## Generación Incremental

El sistema permite generar código de forma incremental:

```bash
# Generar un módulo completo
aegis generate --module users

# Generar una clase específica
aegis generate --class UserService

# Generar solo un método
aegis generate --class UserService --method createUser

# Generar solo tests
aegis generate --module users --tests-only
```

## Validación Pre-Implementación

Antes de enviar al agente, el editor debe validar:

1. **Integridad de referencias**: Todos los tipos referenciados existen
2. **Ciclos de dependencia**: Detectar dependencias circulares
3. **Completitud**: Métodos tienen al menos descripción y returnType
4. **Consistencia**: Interfaces implementadas tienen todos sus métodos

### Ejemplo de Validación

```typescript
interface ValidationResult {
  isValid: boolean;
  errors: ValidationError[];
  warnings: ValidationWarning[];
}

interface ValidationError {
  type: 'missing_type' | 'circular_dependency' | 'incomplete_method';
  location: string;  // "users.UserService.createUser"
  message: string;
}
```

## Flujo de Trabajo Propuesto

```
1. Diseño & Especificación
   Usuario define estructura y reglas (Hints/Tests) en el Editor.
         │
         ▼
2. Validación Estricta
   Sistema verifica:
   - Integridad Referencial (¿Existe el tipo de retorno?)
   - Completitud (¿Hay descripción y al menos 1 test case?)
         │
         ▼
3. Generación (Agente Loop) 
   ┌──────────────────────────────────────────────────────────────┐
   │  A. Editor envía XML contextual al Agente                    │
   │  B. Agente genera Código de Implementación + Código de Test  │
   │  C. Sistema ejecuta Tests en Sandbox (Docker/VM)             │
   │                                                              │
   │  ¿Tests Pasan? ───▶ NO ──┐                                   │
   │       │                  │                                   │
   │       ▼                  ▼                                   │
   │      SI          (Re-prompt automático con el error)         │
   │       │          "El test 'X' falló con error 'Y'. Ajusta."  │
   │       │          (Max 3 intentos)                            │
   └───────┼──────────────────────────────────────────────────────┘
           │
           ▼
4. Revisión Humana
   Usuario ve el código final y el resultado de los tests (Verde).
   Acepta e integra en el codebase.
```

## Diseño de Interfaz: Patrón Canvas + Inspector

Para evitar la sobrecarga visual en el diagrama, se adopta una estrategia de "Divulgación Progresiva":
 1. El Canvas (Vista de Arquitectura)
Los nodos en el diagrama deben ser ligeros. Su función es mostrar la estructura macro y las relaciones.
Header: Icono (Clase/Interface/Enum) + Nombre.
Body:
Lista resumen de Atributos (ej: + id: UUID, - password: String).
Lista resumen de Métodos (solo nombres, ej: + createUser()).
Footer: Indicadores de estado (ej: "¿Validado?", "¿Tiene Tests?").
 2. El Inspector (Panel Lateral Derecho)
Al hacer clic en un nodo, se despliega un panel lateral ("Contextual Sidebar") que permite la edición profunda sin estorbar el diagrama. Este panel usa pestañas:
General: Nombre, Descripción, Herencia (extends), Implementaciones.
Atributos: Tabla editable para definir campos, tipos, visibilidad y valores default.
Métodos (Detalle):
Lista de métodos seleccionables. Al entrar en uno:
Firma: Params, Return Type, Async/Static.
Contratos: Editores de texto para Preconditions, Postconditions y Throws.
Agente: Campos específicos para Hints (instrucciones naturales) y Edge Cases.
Tests: Lista de casos de prueba (Input -> Expected Output).
Preview XML: Vista en tiempo real de cómo el agente recibirá esta entidad.

## Validación Semántica (Detalle Técnico)
- Añadir esta sección para clarificar qué valida el sistema antes de generar.
- Reglas de Validación Semántica (Pre-Export)
- Antes de generar el XML, el sistema debe pasar checkeos que Zod no puede hacer (porque dependen del contexto global del proyecto):
- **Validación de Tipss:**
  + Si un método devuelve UserDTO, la clase UserDTO debe existir en el proyecto o estar marcada como "External".
  + Validación de Herencia:
  + No se permiten ciclos de herencia (A extends B y B extends A).
  + Si A implements I, A debe tener definidos todos los métodos de I (o estar marcada como abstracta).
- **Validación de Contrato**: 
  - Los parameters definidos en los métodos deben coincidir con los usados en las preconditions (simple string matching o parsing básico).
  - Validación de Calidad para Agente:
  - Warning si un método complejo no tiene testCases.
  - Error si hay hints vacíos.

## Próximos Pasos de Implementación

### Fase 1: Core del Editor
- [ ] Setup proyecto React + TypeScript
- [ ] Integrar React Flow
- [ ] Definir tipos TypeScript desde JSON Schema
- [ ] Crear nodos básicos: Class, Interface, Enum
- [ ] Implementar conexiones (relationships)

### Fase 2: Edición de Entidades
- [ ] Panel de propiedades para cada nodo
- [ ] Editor de métodos con todos los campos
- [ ] Editor de hints/custom fields
- [ ] Validación en tiempo real

### Fase 3: Persistencia y Export
- [ ] Guardar/cargar proyectos (JSON)
- [ ] Exportador JSON → XML
- [ ] Preview del XML generado

### Fase 4: Integración con Agente
- [ ] Interface de comunicación con Claude Code
- [ ] Generación incremental
- [ ] Feedback loop (errores del agente → editor)

---

*Documento generado para AEGIS v2 - Model-Driven Development con Agentes*
