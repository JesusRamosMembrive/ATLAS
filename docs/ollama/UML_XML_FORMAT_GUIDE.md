# Guía de Formato XML UML para Generación con IA

Este documento describe el formato XML utilizado por AEGIS UML Editor para definir proyectos UML. Está diseñado para que un modelo de IA (como Ollama) pueda generar proyectos UML válidos a partir de descripciones en lenguaje natural.

---

## Estructura General del XML

```xml
<?xml version="1.0" encoding="UTF-8"?>
<uml-project name="NombreProyecto" version="1.0" targetLanguage="python">
  <module name="nombre_modulo">
    <!-- Clases -->
    <class name="MiClase" ... >...</class>

    <!-- Interfaces -->
    <interface name="MiInterface" ... >...</interface>

    <!-- Enums -->
    <enum name="MiEnum" ... >...</enum>

    <!-- Structs -->
    <struct name="MiStruct" ... >...</struct>

    <!-- Relaciones -->
    <relationship type="inheritance" from="ClaseHija" to="ClasePadre" />
  </module>
</uml-project>
```

---

## Elemento Raíz: `<uml-project>`

| Atributo | Tipo | Requerido | Descripción |
|----------|------|-----------|-------------|
| `name` | string | Sí | Nombre del proyecto |
| `version` | string | Sí | Versión del proyecto (ej: "1.0") |
| `targetLanguage` | string | Sí | Lenguaje destino: `python`, `typescript`, `cpp` |

```xml
<uml-project name="EcommerceSystem" version="1.0" targetLanguage="python">
  ...
</uml-project>
```

---

## Elemento: `<module>`

Agrupa entidades relacionadas lógicamente.

| Atributo | Tipo | Requerido | Descripción |
|----------|------|-----------|-------------|
| `name` | string | Sí | Nombre del módulo (ej: "auth", "models", "services") |

```xml
<module name="authentication">
  <class name="AuthService">...</class>
  <interface name="TokenProvider">...</interface>
</module>
```

---

## Elemento: `<class>`

Define una clase con sus atributos y métodos.

### Atributos de `<class>`

| Atributo | Tipo | Requerido | Descripción |
|----------|------|-----------|-------------|
| `name` | string | Sí | Nombre de la clase (PascalCase) |
| `extends` | string | No | Clase padre (herencia simple) |
| `implements` | string | No | Interfaces implementadas (separadas por coma) |
| `isAbstract` | boolean | No | Si es clase abstracta (default: false) |

### Estructura interna

```xml
<class name="UserService" extends="BaseService" implements="Authenticatable" isAbstract="false">
  <description>Servicio para gestión de usuarios</description>

  <attributes>
    <attribute name="repository" type="UserRepository" visibility="private" />
    <attribute name="cache" type="CacheService" visibility="private" />
  </attributes>

  <methods>
    <method name="findById" visibility="public" returnType="User">
      <description>Busca un usuario por su ID</description>
      <parameters>
        <parameter name="userId" type="string" />
      </parameters>
      <preconditions>
        <condition>userId no puede estar vacío</condition>
      </preconditions>
      <postconditions>
        <condition>Retorna User si existe, null si no</condition>
      </postconditions>
      <throws>
        <exception type="ValidationError">Si userId tiene formato inválido</exception>
      </throws>
      <hints>
        <edgeCases>
          <case>Usuario eliminado recientemente (soft delete)</case>
          <case>ID con caracteres especiales</case>
        </edgeCases>
        <performance>Usar caché para IDs frecuentes</performance>
      </hints>
    </method>
  </methods>
</class>
```

---

## Elemento: `<interface>`

Define un contrato que las clases deben implementar.

### Atributos de `<interface>`

| Atributo | Tipo | Requerido | Descripción |
|----------|------|-----------|-------------|
| `name` | string | Sí | Nombre de la interfaz (PascalCase) |
| `extends` | string | No | Interfaces que extiende (separadas por coma) |

```xml
<interface name="Repository" extends="Queryable">
  <description>Contrato base para repositorios de datos</description>

  <methods>
    <method name="findAll" visibility="public" returnType="List[T]" isAbstract="true">
      <description>Obtiene todos los registros</description>
    </method>
    <method name="save" visibility="public" returnType="T" isAbstract="true">
      <parameters>
        <parameter name="entity" type="T" />
      </parameters>
    </method>
  </methods>
</interface>
```

---

## Elemento: `<enum>`

Define un tipo enumerado con valores constantes.

### Atributos de `<enum>`

| Atributo | Tipo | Requerido | Descripción |
|----------|------|-----------|-------------|
| `name` | string | Sí | Nombre del enum (PascalCase) |

```xml
<enum name="OrderStatus">
  <description>Estados posibles de un pedido</description>
  <values>
    <value name="PENDING" description="Pedido creado, pendiente de pago" />
    <value name="PAID" description="Pago confirmado" />
    <value name="SHIPPED" description="Enviado al cliente" />
    <value name="DELIVERED" description="Entregado" />
    <value name="CANCELLED" description="Cancelado" />
  </values>
</enum>
```

---

## Elemento: `<struct>`

Define una estructura de datos simple (sin comportamiento complejo).

### Atributos de `<struct>`

| Atributo | Tipo | Requerido | Descripción |
|----------|------|-----------|-------------|
| `name` | string | Sí | Nombre del struct (PascalCase) |

```xml
<struct name="Address">
  <description>Dirección postal</description>
  <attributes>
    <attribute name="street" type="string" visibility="public" />
    <attribute name="city" type="string" visibility="public" />
    <attribute name="zipCode" type="string" visibility="public" />
    <attribute name="country" type="string" visibility="public" />
  </attributes>
</struct>
```

---

## Elemento: `<attribute>`

Define un atributo/propiedad de una clase o struct.

| Atributo | Tipo | Requerido | Descripción |
|----------|------|-----------|-------------|
| `name` | string | Sí | Nombre del atributo (camelCase) |
| `type` | string | Sí | Tipo de dato |
| `visibility` | string | No | `public`, `private`, `protected` (default: public) |
| `isStatic` | boolean | No | Si es estático (default: false) |
| `isReadonly` | boolean | No | Si es de solo lectura (default: false) |
| `defaultValue` | string | No | Valor por defecto |

```xml
<attribute name="maxRetries" type="int" visibility="private" isStatic="true" defaultValue="3" />
<attribute name="createdAt" type="datetime" visibility="public" isReadonly="true" />
```

---

## Elemento: `<method>`

Define un método de una clase o interfaz.

### Atributos de `<method>`

| Atributo | Tipo | Requerido | Descripción |
|----------|------|-----------|-------------|
| `name` | string | Sí | Nombre del método (camelCase) |
| `visibility` | string | No | `public`, `private`, `protected` (default: public) |
| `returnType` | string | No | Tipo de retorno (default: void) |
| `isStatic` | boolean | No | Si es estático (default: false) |
| `isAsync` | boolean | No | Si es asíncrono (default: false) |
| `isAbstract` | boolean | No | Si es abstracto (default: false) |

### Subelementos de `<method>`

```xml
<method name="processPayment" visibility="public" returnType="PaymentResult" isAsync="true">
  <description>Procesa un pago con el proveedor externo</description>

  <parameters>
    <parameter name="amount" type="decimal" />
    <parameter name="currency" type="string" defaultValue="USD" />
    <parameter name="paymentMethod" type="PaymentMethod" />
  </parameters>

  <preconditions>
    <condition>amount > 0</condition>
    <condition>paymentMethod debe estar activo</condition>
  </preconditions>

  <postconditions>
    <condition>Se genera transactionId único</condition>
    <condition>Se registra en el log de auditoría</condition>
  </postconditions>

  <throws>
    <exception type="PaymentError">Cuando el proveedor rechaza el pago</exception>
    <exception type="NetworkError">Cuando hay timeout de conexión</exception>
  </throws>

  <hints>
    <edgeCases>
      <case>Pago duplicado en ventana de 5 minutos</case>
      <case>Moneda no soportada por el proveedor</case>
    </edgeCases>
    <performance>Implementar retry con backoff exponencial</performance>
    <style>Usar patrón Circuit Breaker para fallos externos</style>
  </hints>

  <testCases>
    <test name="should process valid payment">
      <given>Usuario con método de pago válido</given>
      <when>Procesa pago de $100 USD</when>
      <then>Retorna PaymentResult con status SUCCESS</then>
    </test>
    <test name="should reject negative amount">
      <given>Cualquier usuario</given>
      <when>Intenta pagar cantidad negativa</when>
      <then>Lanza ValidationError</then>
    </test>
  </testCases>
</method>
```

---

## Elemento: `<relationship>`

Define una relación entre dos entidades.

### Atributos de `<relationship>`

| Atributo | Tipo | Requerido | Descripción |
|----------|------|-----------|-------------|
| `type` | string | Sí | Tipo de relación (ver tabla abajo) |
| `from` | string | Sí | Nombre de la entidad origen |
| `to` | string | Sí | Nombre de la entidad destino |
| `label` | string | No | Etiqueta descriptiva |
| `fromCardinality` | string | No | Cardinalidad origen (ej: "1", "0..1", "*", "1..*") |
| `toCardinality` | string | No | Cardinalidad destino |

### Tipos de Relación

| Tipo | Descripción | Ejemplo |
|------|-------------|---------|
| `inheritance` | Herencia (es-un) | Dog hereda de Animal |
| `implementation` | Implementa interfaz | UserService implementa Repository |
| `composition` | Composición fuerte (parte-de, ciclo de vida ligado) | Order contiene OrderItems |
| `aggregation` | Agregación débil (tiene-un, ciclo de vida independiente) | Department tiene Employees |
| `association` | Asociación simple (usa) | User tiene Address |
| `dependency` | Dependencia (depende-de) | Controller depende de Service |

```xml
<!-- Herencia -->
<relationship type="inheritance" from="Dog" to="Animal" />

<!-- Implementación de interfaz -->
<relationship type="implementation" from="UserRepository" to="Repository" />

<!-- Composición: Order "posee" sus OrderItems -->
<relationship type="composition" from="Order" to="OrderItem"
              fromCardinality="1" toCardinality="1..*"
              label="contains" />

<!-- Agregación: Department "tiene" Employees -->
<relationship type="aggregation" from="Department" to="Employee"
              fromCardinality="1" toCardinality="*"
              label="employs" />

<!-- Asociación simple -->
<relationship type="association" from="User" to="Address"
              fromCardinality="1" toCardinality="0..*"
              label="lives at" />

<!-- Dependencia -->
<relationship type="dependency" from="OrderController" to="OrderService"
              label="uses" />
```

---

## Mapeo de Tipos por Lenguaje

### Tipos Primitivos

| Abstracto | Python | TypeScript | C++ |
|-----------|--------|------------|-----|
| `string` | `str` | `string` | `std::string` |
| `int` | `int` | `number` | `int` |
| `float` | `float` | `number` | `double` |
| `bool` | `bool` | `boolean` | `bool` |
| `datetime` | `datetime` | `Date` | `std::chrono::time_point` |
| `void` | `None` | `void` | `void` |
| `any` | `Any` | `any` | `std::any` |

### Tipos Colección

| Abstracto | Python | TypeScript | C++ |
|-----------|--------|------------|-----|
| `List[T]` | `List[T]` | `T[]` | `std::vector<T>` |
| `Dict[K,V]` | `Dict[K, V]` | `Record<K, V>` | `std::map<K, V>` |
| `Set[T]` | `Set[T]` | `Set<T>` | `std::set<T>` |
| `Optional[T]` | `Optional[T]` | `T \| null` | `std::optional<T>` |

### Nombres de Entidades por Lenguaje

| Tipo | Python | TypeScript | C++ |
|------|--------|------------|-----|
| Interface | Protocol | Interface | Abstract Class |
| Struct | Dataclass | Type | Struct |

---

## Ejemplo Completo: Sistema de E-commerce

```xml
<?xml version="1.0" encoding="UTF-8"?>
<uml-project name="EcommerceSystem" version="1.0" targetLanguage="python">

  <module name="domain">
    <!-- Entidades de dominio -->

    <enum name="OrderStatus">
      <description>Estados del ciclo de vida de un pedido</description>
      <values>
        <value name="PENDING" description="Esperando pago" />
        <value name="PAID" description="Pago confirmado" />
        <value name="SHIPPED" description="En tránsito" />
        <value name="DELIVERED" description="Entregado" />
        <value name="CANCELLED" description="Cancelado" />
      </values>
    </enum>

    <struct name="Money">
      <description>Valor monetario con moneda</description>
      <attributes>
        <attribute name="amount" type="decimal" visibility="public" />
        <attribute name="currency" type="string" visibility="public" defaultValue="USD" />
      </attributes>
    </struct>

    <class name="Product">
      <description>Producto del catálogo</description>
      <attributes>
        <attribute name="id" type="string" visibility="private" isReadonly="true" />
        <attribute name="name" type="string" visibility="public" />
        <attribute name="price" type="Money" visibility="public" />
        <attribute name="stock" type="int" visibility="private" />
      </attributes>
      <methods>
        <method name="isAvailable" visibility="public" returnType="bool">
          <description>Verifica si hay stock disponible</description>
          <postconditions>
            <condition>Retorna true si stock > 0</condition>
          </postconditions>
        </method>
        <method name="reduceStock" visibility="public" returnType="void">
          <parameters>
            <parameter name="quantity" type="int" />
          </parameters>
          <preconditions>
            <condition>quantity > 0</condition>
            <condition>stock >= quantity</condition>
          </preconditions>
          <throws>
            <exception type="InsufficientStockError">Si no hay suficiente stock</exception>
          </throws>
        </method>
      </methods>
    </class>

    <class name="OrderItem">
      <description>Línea de pedido</description>
      <attributes>
        <attribute name="product" type="Product" visibility="private" />
        <attribute name="quantity" type="int" visibility="public" />
        <attribute name="unitPrice" type="Money" visibility="public" isReadonly="true" />
      </attributes>
      <methods>
        <method name="getTotal" visibility="public" returnType="Money">
          <description>Calcula el total de la línea</description>
        </method>
      </methods>
    </class>

    <class name="Order">
      <description>Pedido de compra</description>
      <attributes>
        <attribute name="id" type="string" visibility="private" isReadonly="true" />
        <attribute name="items" type="List[OrderItem]" visibility="private" />
        <attribute name="status" type="OrderStatus" visibility="public" />
        <attribute name="createdAt" type="datetime" visibility="public" isReadonly="true" />
      </attributes>
      <methods>
        <method name="addItem" visibility="public" returnType="void">
          <parameters>
            <parameter name="product" type="Product" />
            <parameter name="quantity" type="int" />
          </parameters>
          <preconditions>
            <condition>status == PENDING</condition>
            <condition>product.isAvailable()</condition>
          </preconditions>
        </method>
        <method name="getTotal" visibility="public" returnType="Money">
          <description>Suma todos los items del pedido</description>
        </method>
        <method name="cancel" visibility="public" returnType="void">
          <preconditions>
            <condition>status in [PENDING, PAID]</condition>
          </preconditions>
          <postconditions>
            <condition>status == CANCELLED</condition>
            <condition>Stock restaurado para todos los items</condition>
          </postconditions>
        </method>
      </methods>
    </class>

    <!-- Relaciones -->
    <relationship type="composition" from="Order" to="OrderItem"
                  fromCardinality="1" toCardinality="1..*" />
    <relationship type="association" from="OrderItem" to="Product"
                  fromCardinality="*" toCardinality="1" />
  </module>

  <module name="services">
    <!-- Interfaces -->

    <interface name="OrderRepository">
      <description>Contrato para persistencia de pedidos</description>
      <methods>
        <method name="findById" visibility="public" returnType="Optional[Order]" isAbstract="true">
          <parameters>
            <parameter name="orderId" type="string" />
          </parameters>
        </method>
        <method name="save" visibility="public" returnType="Order" isAbstract="true">
          <parameters>
            <parameter name="order" type="Order" />
          </parameters>
        </method>
        <method name="findByStatus" visibility="public" returnType="List[Order]" isAbstract="true">
          <parameters>
            <parameter name="status" type="OrderStatus" />
          </parameters>
        </method>
      </methods>
    </interface>

    <interface name="PaymentGateway">
      <description>Contrato para procesamiento de pagos</description>
      <methods>
        <method name="charge" visibility="public" returnType="PaymentResult" isAsync="true" isAbstract="true">
          <parameters>
            <parameter name="amount" type="Money" />
            <parameter name="paymentMethod" type="string" />
          </parameters>
        </method>
        <method name="refund" visibility="public" returnType="RefundResult" isAsync="true" isAbstract="true">
          <parameters>
            <parameter name="transactionId" type="string" />
          </parameters>
        </method>
      </methods>
    </interface>

    <!-- Servicios -->

    <class name="OrderService">
      <description>Lógica de negocio para pedidos</description>
      <attributes>
        <attribute name="repository" type="OrderRepository" visibility="private" />
        <attribute name="paymentGateway" type="PaymentGateway" visibility="private" />
      </attributes>
      <methods>
        <method name="createOrder" visibility="public" returnType="Order" isAsync="true">
          <parameters>
            <parameter name="items" type="List[OrderItem]" />
          </parameters>
          <postconditions>
            <condition>Order creado con status PENDING</condition>
            <condition>Order persistido en repository</condition>
          </postconditions>
        </method>
        <method name="checkout" visibility="public" returnType="Order" isAsync="true">
          <parameters>
            <parameter name="orderId" type="string" />
            <parameter name="paymentMethod" type="string" />
          </parameters>
          <preconditions>
            <condition>Order existe y status == PENDING</condition>
          </preconditions>
          <postconditions>
            <condition>Pago procesado exitosamente</condition>
            <condition>Order status == PAID</condition>
          </postconditions>
          <throws>
            <exception type="OrderNotFoundError">Si el pedido no existe</exception>
            <exception type="PaymentError">Si el pago falla</exception>
          </throws>
          <hints>
            <edgeCases>
              <case>Pago exitoso pero fallo al actualizar status</case>
              <case>Timeout durante el pago</case>
            </edgeCases>
            <performance>Usar transacción distribuida o saga</performance>
          </hints>
        </method>
      </methods>
    </class>

    <!-- Relaciones del módulo services -->
    <relationship type="dependency" from="OrderService" to="OrderRepository" />
    <relationship type="dependency" from="OrderService" to="PaymentGateway" />
  </module>

</uml-project>
```

---

## Reglas de Validación

Al generar XML, asegúrate de cumplir:

1. **Nombres únicos**: No repetir nombres de clases, interfaces, enums o structs en el mismo proyecto
2. **Referencias válidas**: `extends`, `implements`, `from`, `to` deben referir a entidades existentes
3. **Relaciones coherentes**:
   - `inheritance`: solo entre clases
   - `implementation`: de clase a interfaz
   - `composition`/`aggregation`: entre clases o structs
4. **Visibilidad válida**: Solo `public`, `private`, `protected`
5. **Cardinalidad válida**: Formatos aceptados: `1`, `0..1`, `*`, `1..*`, `0..*`, `n..m`
6. **Tipos consistentes**: Usar tipos abstractos que mapean al lenguaje destino

---

## Patrones de Diseño Comunes

### Factory Pattern

```xml
<interface name="ProductFactory">
  <methods>
    <method name="create" returnType="Product" isAbstract="true">
      <parameters>
        <parameter name="type" type="string" />
      </parameters>
    </method>
  </methods>
</interface>

<class name="ConcreteProductFactory" implements="ProductFactory">
  <methods>
    <method name="create" returnType="Product">
      <parameters>
        <parameter name="type" type="string" />
      </parameters>
    </method>
  </methods>
</class>

<relationship type="implementation" from="ConcreteProductFactory" to="ProductFactory" />
```

### Repository Pattern

```xml
<interface name="Repository">
  <methods>
    <method name="findById" returnType="Optional[T]" isAbstract="true">
      <parameters><parameter name="id" type="string" /></parameters>
    </method>
    <method name="save" returnType="T" isAbstract="true">
      <parameters><parameter name="entity" type="T" /></parameters>
    </method>
    <method name="delete" returnType="void" isAbstract="true">
      <parameters><parameter name="id" type="string" /></parameters>
    </method>
  </methods>
</interface>

<class name="UserRepository" implements="Repository">
  <attributes>
    <attribute name="database" type="Database" visibility="private" />
  </attributes>
  <!-- Implementaciones concretas -->
</class>
```

### Observer Pattern

```xml
<interface name="Observer">
  <methods>
    <method name="update" returnType="void" isAbstract="true">
      <parameters>
        <parameter name="event" type="Event" />
      </parameters>
    </method>
  </methods>
</interface>

<class name="Subject">
  <attributes>
    <attribute name="observers" type="List[Observer]" visibility="private" />
  </attributes>
  <methods>
    <method name="attach" returnType="void">
      <parameters><parameter name="observer" type="Observer" /></parameters>
    </method>
    <method name="detach" returnType="void">
      <parameters><parameter name="observer" type="Observer" /></parameters>
    </method>
    <method name="notify" returnType="void" visibility="protected">
      <parameters><parameter name="event" type="Event" /></parameters>
    </method>
  </methods>
</class>

<relationship type="aggregation" from="Subject" to="Observer"
              fromCardinality="1" toCardinality="*" />
```

---

## Instrucciones para el Modelo IA

Cuando generes XML UML:

1. **Analiza los requisitos** del usuario para identificar:
   - Entidades principales (sustantivos → clases/structs)
   - Comportamientos (verbos → métodos)
   - Relaciones (pertenece-a, usa, hereda-de)

2. **Organiza en módulos** por responsabilidad:
   - `domain`: Entidades de negocio puras
   - `services`: Lógica de aplicación
   - `repositories`: Persistencia de datos
   - `controllers`: Puntos de entrada (API)

3. **Aplica principios SOLID**:
   - Una clase = una responsabilidad
   - Interfaces para dependencias
   - Composición sobre herencia

4. **Incluye contratos** (pre/post condiciones) para métodos críticos

5. **Documenta** con `<description>` y `<hints>` para guiar la implementación

6. **Valida** que todas las referencias sean válidas antes de finalizar
