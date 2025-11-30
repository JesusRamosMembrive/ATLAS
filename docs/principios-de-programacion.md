Elegir buenas prácticas es fundamental para que el código sea mantenible, escalable y fácil de entender por otros (o por ti mismo en el futuro).

Además de **KISS**, **DRY** y **SOLID**, aquí tienes una recopilación de las prácticas y principios más importantes, clasificados por su propósito:

### 1. Principios de Pragmatismo (Evitar el sobre-ingeniería)

*   **YAGNI (You Ain't Gonna Need It):**
    *   *Concepto:* No escribas código para funcionalidades que "quizás" necesites en el futuro.
    *   *Por qué:* El futuro es incierto; implementar cosas por adelantado suele llevar a código muerto o a arquitecturas innecesariamente complejas.
*   **Evitar la Optimización Prematura:**
    *   *Concepto:* Como dijo Donald Knuth, "la optimización prematura es la raíz de todos los males".
    *   *Por qué:* No intentes hacer que el código sea micro-eficiente antes de saber si es un cuello de botella. Primero haz que funcione, luego hazlo correcto y, finalmente, hazlo rápido solo si es necesario.

### 2. Principios de Diseño y Arquitectura

*   **SoC (Separation of Concerns - Separación de Responsabilidades):**
    *   *Concepto:* Divide el programa en secciones distintas, cada una manejando una "preocupación" diferente (ej. Lógica de negocio vs. Interfaz de usuario vs. Acceso a datos).
    *   *Relacionado:* Arquitectura en capas o Hexagonal.
*   **Composición sobre Herencia:**
    *   *Concepto:* Es mejor componer objetos (un objeto *tiene* otro objeto) que heredar de ellos (un objeto *es* otro objeto).
    *   *Por qué:* La herencia crea un acoplamiento muy fuerte y rígido. La composición es más flexible.
*   **Ley de Demeter (Principio del menor conocimiento):**
    *   *Concepto:* Un objeto no debe conocer los detalles internos de los objetos que manipula. "Habla solo con tus amigos inmediatos".
    *   *Ejemplo:* Evita cadenas como `usuario.getDepartamento().getDireccion().getCodigoPostal()`.
*   **Alta Cohesión y Bajo Acoplamiento:**
    *   El "santo grial" de la arquitectura. Quieres que los módulos sean muy independientes entre sí (**bajo acoplamiento**) pero que las piezas dentro de un módulo estén muy relacionadas y tengan sentido juntas (**alta cohesión**).

### 3. Legibilidad y "Clean Code"

*   **Boy Scout Rule (Regla del Boy Scout):**
    *   *Concepto:* "Deja el campamento más limpio de lo que lo encontraste".
    *   *Aplicación:* Si tocas un archivo antiguo para arreglar un bug, aprovecha para mejorar un poco el nombre de una variable o extraer una función pequeña.
*   **Principio de Menor Asombro (POLA - Principle of Least Astonishment):**
    *   *Concepto:* El código debe comportarse de la manera más obvia posible para el usuario o desarrollador que lo lee.
    *   *Ejemplo:* Una función llamada `obtenerUsuario()` no debería modificar la base de datos, solo devolver datos.
*   **Nombrado Semántico:**
    *   Las variables deben decir *qué son*, las funciones *qué hacen*. Evita `var x`, `temp`, `data`. Usa `totalCarrito`, `calcularImpuesto`, `usuarioActivo`.
*   **Evitar "Magic Numbers" y "Magic Strings":**
    *   No uses números sueltos en el código (ej. `if status == 2`). Define constantes (ej. `const STATUS_ACTIVE = 2`).

### 4. Estabilidad y Manejo de Errores

*   **Fail Fast (Fallar Rápido):**
    *   *Concepto:* Si algo va mal (ej. parámetros nulos, configuración faltante), el programa debe detenerse y reportarlo inmediatamente en lugar de intentar continuar y causar errores extraños más adelante.
*   **Inmutabilidad (cuando sea posible):**
    *   *Concepto:* Evita cambiar el estado de los objetos una vez creados.
    *   *Por qué:* Reduce drásticamente los bugs relacionados con efectos secundarios, especialmente en programación asíncrona o concurrente.

### 5. Testing (Pruebas)

*   **F.I.R.S.T (Para Unit Tests):**
    *   Los tests deben ser **F**ast (Rápidos), **I**solated (Aislados/Independientes), **R**epeatable (Repetibles en cualquier entorno), **S**elf-validating (Auto-validables, pasan o fallan sin inspección manual) y **T**imely (Oportunos, escritos antes o junto al código).
*   **AAA (Arrange, Act, Assert):**
    *   Estructura estándar para escribir tests: Preparar los datos, ejecutar la acción y verificar el resultado.

### Resumen rápido para tu día a día:

Si tuviera que priorizar más allá de las que dijiste, me quedaría con estas tres:

1.  **YAGNI:** Para no perder tiempo.
2.  **Clean Code (Naming):** Porque leemos código 10 veces más de lo que lo escribimos.
3.  **Fail Fast:** Para encontrar bugs lo antes posible.

