# Code Similarity Detector - Propuesta Técnica

## Resumen Ejecutivo

Un módulo C++ de alto rendimiento para detección de código duplicado y clones en proyectos de software. Utiliza algoritmos avanzados (Rabin-Karp fingerprinting) para identificar similitudes entre archivos y funciones, generando reportes visuales útiles para code reviews y mantenimiento.

---

## Contexto y Motivación

### Problema Actual
AEGIS actualmente no tiene capacidad de detectar:
- Código duplicado entre archivos
- Funciones copy-paste con modificaciones menores
- Patrones repetidos que podrían abstraerse
- Código "clonado" que diverge con el tiempo

### Por Qué C++
| Aspecto | Python | C++ |
|---------|--------|-----|
| Procesamiento de hashes | ~100K/seg | ~10M/seg |
| Memoria para índices | Alta (objetos) | Baja (POD) |
| Paralelización | GIL limitado | Sin restricciones |
| Portfolio value | Común | Diferenciador |

### Valor para AEGIS
- **Feature única**: Ningún competidor directo en el ecosistema
- **Altamente visual**: Reportes de similitud impresionan en demos
- **Útil en code reviews**: Detecta copy-paste automáticamente
- **Escalable**: Puede analizar proyectos grandes eficientemente

---

## Tipos de Clones de Código

### Type-1: Clones Exactos
Código idéntico excepto por whitespace y comentarios.
```python
# Archivo A                    # Archivo B
def calc(x):                   def calc(x):
    return x * 2                   return x * 2
```

### Type-2: Clones Renombrados
Mismo código con diferentes nombres de variables/funciones.
```python
# Archivo A                    # Archivo B
def process(data):             def handle(items):
    for item in data:              for elem in items:
        print(item)                    print(elem)
```

### Type-3: Clones con Modificaciones
Código similar con algunas líneas añadidas/eliminadas/modificadas.
```python
# Archivo A                    # Archivo B
def validate(x):               def validate(x):
    if x < 0:                      if x < 0:
        return False                   return False
    return True                    if x > 100:      # Añadido
                                       return False
                                   return True
```

### Type-4: Clones Semánticos (Futuro)
Código diferente que hace lo mismo - requiere análisis más profundo.

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                    Code Similarity Detector                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐      │
│  │   Tokenizer   │───▶│  Normalizer  │───▶│   Hasher     │      │
│  │  (por idioma) │    │ (abstracto)  │    │ (Rabin-Karp) │      │
│  └──────────────┘    └──────────────┘    └──────────────┘      │
│         │                                        │               │
│         ▼                                        ▼               │
│  ┌──────────────┐                       ┌──────────────┐        │
│  │  Token Cache │                       │  Hash Index  │        │
│  │   (LRU)      │                       │ (Inverted)   │        │
│  └──────────────┘                       └──────────────┘        │
│                                                  │               │
│                                                  ▼               │
│                                         ┌──────────────┐        │
│                                         │   Matcher    │        │
│                                         │  (paralelo)  │        │
│                                         └──────────────┘        │
│                                                  │               │
│                                                  ▼               │
│                                         ┌──────────────┐        │
│                                         │   Reporter   │        │
│                                         │  (JSON/HTML) │        │
│                                         └──────────────┘        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Algoritmo Principal: Rabin-Karp Rolling Hash

### Concepto
Genera "fingerprints" de secuencias de tokens que pueden compararse en O(1).

### Implementación

```cpp
class RollingHash {
private:
    static constexpr uint64_t BASE = 31;
    static constexpr uint64_t MOD = 1e9 + 9;

    uint64_t hash = 0;
    uint64_t base_power = 1;  // BASE^(window_size-1)
    std::deque<uint64_t> window;
    size_t window_size;

public:
    explicit RollingHash(size_t window_size)
        : window_size(window_size) {
        // Pre-calcular BASE^(window_size-1) mod MOD
        for (size_t i = 1; i < window_size; ++i) {
            base_power = (base_power * BASE) % MOD;
        }
    }

    // Añadir nuevo token, devuelve hash si ventana llena
    std::optional<uint64_t> push(uint64_t token_hash) {
        // Añadir nuevo token
        hash = (hash * BASE + token_hash) % MOD;
        window.push_back(token_hash);

        if (window.size() < window_size) {
            return std::nullopt;  // Ventana no llena aún
        }

        uint64_t result = hash;

        // Remover token más antiguo
        uint64_t old_token = window.front();
        window.pop_front();
        hash = (hash - old_token * base_power % MOD + MOD) % MOD;

        return result;
    }

    void reset() {
        hash = 0;
        window.clear();
    }
};
```

### Complejidad
- **Tiempo**: O(n) para procesar n tokens
- **Espacio**: O(w) donde w = tamaño de ventana
- **Comparación**: O(1) por par de hashes

---

## Normalización de Tokens

### Objetivo
Convertir código fuente en tokens abstractos para detectar clones Type-2.

### Proceso

```cpp
enum class TokenType : uint8_t {
    IDENTIFIER,      // Nombres → $ID
    STRING_LITERAL,  // Strings → $STR
    NUMBER_LITERAL,  // Números → $NUM
    KEYWORD,         // if, for, while → se mantienen
    OPERATOR,        // +, -, *, / → se mantienen
    PUNCTUATION,     // {, }, (, ) → se mantienen
    TYPE,            // int, string → $TYPE
    COMMENT,         // Se ignora
    WHITESPACE       // Se ignora
};

struct NormalizedToken {
    TokenType type;
    uint32_t hash;        // Hash del valor normalizado
    uint32_t line;        // Línea original (para reportes)
    uint16_t column;      // Columna original
};

// Ejemplo de normalización
// Original:  "int calculateSum(int a, int b) { return a + b; }"
// Tokens:    [$TYPE, $ID, (, $TYPE, $ID, ,, $TYPE, $ID, ), {, return, $ID, +, $ID, ;, }]
```

### Mapeo por Lenguaje

```cpp
class TokenNormalizer {
public:
    virtual ~TokenNormalizer() = default;
    virtual std::vector<NormalizedToken> normalize(
        std::string_view source
    ) = 0;
};

class PythonNormalizer : public TokenNormalizer {
    // Usa tree-sitter-python o tokenize simple
};

class CppNormalizer : public TokenNormalizer {
    // Usa libclang para tokenización precisa
};

class JavaScriptNormalizer : public TokenNormalizer {
    // Usa esprima-like tokenizer
};

// Factory
std::unique_ptr<TokenNormalizer> create_normalizer(Language lang);
```

---

## Índice de Hashes

### Estructura

```cpp
struct HashLocation {
    uint32_t file_id;
    uint32_t start_line;
    uint32_t end_line;
    uint16_t start_col;
    uint16_t end_col;
};

class HashIndex {
private:
    // Hash → lista de ubicaciones donde aparece
    std::unordered_map<uint64_t, std::vector<HashLocation>> index;

    // Metadatos de archivos
    std::vector<std::string> file_paths;

public:
    void add_hash(uint64_t hash, const HashLocation& loc) {
        index[hash].push_back(loc);
    }

    // Encontrar todos los clones potenciales
    std::vector<ClonePair> find_clones(size_t min_matches = 5) {
        std::vector<ClonePair> results;

        for (const auto& [hash, locations] : index) {
            if (locations.size() < 2) continue;

            // Generar pares de ubicaciones que comparten este hash
            for (size_t i = 0; i < locations.size(); ++i) {
                for (size_t j = i + 1; j < locations.size(); ++j) {
                    // Evitar auto-comparación del mismo archivo/región
                    if (locations[i].file_id == locations[j].file_id &&
                        overlaps(locations[i], locations[j])) {
                        continue;
                    }

                    results.emplace_back(locations[i], locations[j], hash);
                }
            }
        }

        return merge_adjacent_clones(results, min_matches);
    }
};
```

---

## Pipeline de Detección

### Flujo Completo

```cpp
class SimilarityDetector {
public:
    struct Config {
        size_t window_size = 10;        // Tokens por ventana
        size_t min_clone_tokens = 30;   // Mínimo para reportar
        float similarity_threshold = 0.7; // 70% similitud
        bool detect_type2 = true;       // Detectar renombrados
        bool detect_type3 = true;       // Detectar modificados
        size_t num_threads = 0;         // 0 = auto
    };

    explicit SimilarityDetector(Config config = {});

    // Analizar un proyecto completo
    SimilarityReport analyze(const std::filesystem::path& root);

    // Analizar archivos específicos
    SimilarityReport analyze(const std::vector<std::string>& files);

    // Comparar dos archivos específicos
    FileSimilarity compare(
        const std::string& file1,
        const std::string& file2
    );

private:
    Config config_;
    HashIndex index_;
    std::unique_ptr<ThreadPool> pool_;

    // Fases del pipeline
    void phase1_tokenize(const std::vector<std::string>& files);
    void phase2_normalize_and_hash();
    void phase3_find_clones();
    void phase4_calculate_similarity();
};
```

### Paralelización

```cpp
void SimilarityDetector::phase1_tokenize(
    const std::vector<std::string>& files
) {
    // Dividir archivos entre threads
    std::vector<std::future<TokenizedFile>> futures;

    for (const auto& file : files) {
        futures.push_back(pool_->submit([&, file]() {
            auto normalizer = create_normalizer(detect_language(file));
            auto source = read_file(file);
            auto tokens = normalizer->normalize(source);
            return TokenizedFile{file, std::move(tokens)};
        }));
    }

    // Recolectar resultados
    for (auto& future : futures) {
        auto result = future.get();
        process_tokenized_file(std::move(result));
    }
}
```

---

## Cálculo de Similitud

### Métrica: Jaccard Similarity

```cpp
float calculate_similarity(
    const std::set<uint64_t>& hashes_a,
    const std::set<uint64_t>& hashes_b
) {
    std::set<uint64_t> intersection;
    std::set_intersection(
        hashes_a.begin(), hashes_a.end(),
        hashes_b.begin(), hashes_b.end(),
        std::inserter(intersection, intersection.begin())
    );

    std::set<uint64_t> union_set;
    std::set_union(
        hashes_a.begin(), hashes_a.end(),
        hashes_b.begin(), hashes_b.end(),
        std::inserter(union_set, union_set.begin())
    );

    if (union_set.empty()) return 0.0f;

    return static_cast<float>(intersection.size()) / union_set.size();
}
```

### Extensión de Clones (Type-3)

```cpp
CloneRegion extend_clone(
    const TokenizedFile& file_a, size_t start_a,
    const TokenizedFile& file_b, size_t start_b,
    size_t initial_length
) {
    // Extender hacia adelante
    size_t end_a = start_a + initial_length;
    size_t end_b = start_b + initial_length;

    while (end_a < file_a.tokens.size() &&
           end_b < file_b.tokens.size()) {
        if (file_a.tokens[end_a].hash == file_b.tokens[end_b].hash) {
            ++end_a;
            ++end_b;
        } else {
            // Permitir gaps para Type-3
            if (can_skip_gap(file_a, end_a, file_b, end_b)) {
                // Intentar realinear
                auto [new_a, new_b] = find_realignment(
                    file_a, end_a, file_b, end_b
                );
                if (new_a && new_b) {
                    end_a = *new_a;
                    end_b = *new_b;
                    continue;
                }
            }
            break;
        }
    }

    // Extender hacia atrás (similar)
    // ...

    return CloneRegion{
        .file_a = file_a.path,
        .file_b = file_b.path,
        .start_a = start_a,
        .end_a = end_a,
        .start_b = start_b,
        .end_b = end_b,
        .similarity = calculate_region_similarity(...)
    };
}
```

---

## Formato de Reporte

### Estructura JSON

```json
{
  "summary": {
    "files_analyzed": 150,
    "total_lines": 25000,
    "clone_pairs_found": 23,
    "estimated_duplication": "12.5%",
    "analysis_time_ms": 1250
  },
  "clones": [
    {
      "id": "clone_001",
      "type": "Type-2",
      "similarity": 0.95,
      "locations": [
        {
          "file": "src/auth/login.py",
          "start_line": 45,
          "end_line": 67,
          "snippet_preview": "def validate_user(username, password):..."
        },
        {
          "file": "src/api/auth_handler.py",
          "start_line": 120,
          "end_line": 142,
          "snippet_preview": "def check_credentials(user, pwd):..."
        }
      ],
      "recommendation": "Consider extracting common validation logic to shared module"
    }
  ],
  "hotspots": [
    {
      "file": "src/utils/helpers.py",
      "duplication_score": 0.35,
      "clone_count": 5,
      "recommendation": "High duplication - review for refactoring opportunities"
    }
  ],
  "metrics": {
    "by_type": {
      "Type-1": 8,
      "Type-2": 12,
      "Type-3": 3
    },
    "by_language": {
      "python": 18,
      "javascript": 5
    }
  }
}
```

### Reporte HTML (Opcional)

```html
<!-- Vista side-by-side con highlighting de diferencias -->
<div class="clone-comparison">
  <div class="file-a">
    <h3>src/auth/login.py:45-67</h3>
    <pre><code class="highlight-match">
def validate_user(<span class="diff">username</span>, <span class="diff">password</span>):
    if not <span class="diff">username</span>:
        return False
    ...
    </code></pre>
  </div>
  <div class="file-b">
    <h3>src/api/auth_handler.py:120-142</h3>
    <pre><code class="highlight-match">
def check_credentials(<span class="diff">user</span>, <span class="diff">pwd</span>):
    if not <span class="diff">user</span>:
        return False
    ...
    </code></pre>
  </div>
</div>
```

---

## API de Integración

### Unix Domain Socket (como el motor actual)

```cpp
// Comandos soportados
enum class Command {
    ANALYZE_PROJECT,    // Analizar directorio completo
    ANALYZE_FILES,      // Analizar archivos específicos
    COMPARE_FILES,      // Comparar dos archivos
    GET_FILE_CLONES,    // Obtener clones de un archivo
    GET_HOTSPOTS,       // Obtener archivos más duplicados
    GET_STATUS,         // Estado del análisis
    CLEAR_CACHE         // Limpiar caché de tokens
};

// Request
{
  "command": "ANALYZE_PROJECT",
  "params": {
    "root": "/path/to/project",
    "extensions": [".py", ".js", ".ts"],
    "exclude_patterns": ["**/node_modules/**", "**/__pycache__/**"],
    "config": {
      "window_size": 10,
      "min_clone_tokens": 30,
      "similarity_threshold": 0.7
    }
  }
}

// Response
{
  "success": true,
  "result": { /* SimilarityReport JSON */ },
  "timing": {
    "tokenize_ms": 450,
    "hash_ms": 200,
    "match_ms": 500,
    "total_ms": 1150
  }
}
```

### Integración con Code Map Backend

```python
# code_map/integrations/similarity_service.py

class SimilarityService:
    def __init__(self, socket_path: str = "/tmp/aegis_similarity.sock"):
        self.socket_path = socket_path
        self._client = None

    async def analyze_project(self, root: Path) -> SimilarityReport:
        """Analizar proyecto completo para código duplicado."""
        response = await self._send_command({
            "command": "ANALYZE_PROJECT",
            "params": {"root": str(root)}
        })
        return SimilarityReport(**response["result"])

    async def get_file_clones(self, file_path: Path) -> List[ClonePair]:
        """Obtener clones de un archivo específico."""
        response = await self._send_command({
            "command": "GET_FILE_CLONES",
            "params": {"file": str(file_path)}
        })
        return [ClonePair(**c) for c in response["result"]]
```

---

## Fases de Implementación

### Fase 1: Core Engine (2-3 semanas)
- [ ] Clase `RollingHash` con tests
- [ ] `TokenNormalizer` base + Python normalizer
- [ ] `HashIndex` básico
- [ ] Detección Type-1 (exactos)
- [ ] Tests unitarios completos

### Fase 2: Multi-lenguaje (1-2 semanas)
- [ ] JavaScript/TypeScript normalizer
- [ ] C/C++ normalizer (reusando libclang)
- [ ] Detección Type-2 (renombrados)
- [ ] Configuración de extensiones

### Fase 3: Avanzado (2 semanas)
- [ ] Detección Type-3 (modificados)
- [ ] Paralelización con thread pool
- [ ] Caché de tokens (LRU)
- [ ] Optimización de memoria

### Fase 4: Integración (1 semana)
- [ ] Servidor UDS (reutilizar infra existente)
- [ ] Protocolo JSON
- [ ] Integración con Code Map backend
- [ ] Reportes JSON completos

### Fase 5: Polish (1 semana)
- [ ] Reportes HTML opcionales
- [ ] Métricas de rendimiento
- [ ] Documentación
- [ ] Benchmarks vs herramientas existentes

---

## Estimación de Rendimiento

### Objetivos

| Métrica | Objetivo | Comparación |
|---------|----------|-------------|
| Velocidad | 10K LOC/seg | PMD CPD: ~2K LOC/seg |
| Memoria | <500MB para 100K LOC | Similar a competidores |
| Precisión Type-1 | >99% | Estado del arte |
| Precisión Type-2 | >95% | Estado del arte |
| Precisión Type-3 | >80% | Competitivo |

### Benchmarks Planificados
- Linux kernel (subset) - 100K LOC
- React codebase - 50K LOC
- Django codebase - 80K LOC

---

## Diferenciadores para Portfolio

### Técnicos
1. **Algoritmo Rabin-Karp optimizado** - Demuestra conocimiento de algoritmos
2. **Multi-threaded sin GIL** - Aprovecha C++ para paralelismo real
3. **Detección Type-3** - Más allá de herramientas básicas
4. **Integración con sistema existente** - Demuestra arquitectura modular

### Visuales (para demos)
1. **Side-by-side diff highlighting** - Muy impactante visualmente
2. **Heatmap de duplicación** - Muestra hotspots del código
3. **Métricas de proyecto** - Dashboard de calidad de código

### Prácticos
1. **Útil en code reviews** - Caso de uso real
2. **Detección de copy-paste** - Problema común en equipos
3. **Refactoring assistant** - Sugiere extracciones

---

## Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Falsos positivos excesivos | Media | Alto | Tunear thresholds, whitelist patterns |
| Rendimiento insuficiente | Baja | Medio | Profiling temprano, optimización incremental |
| Complejidad de tokenizers | Media | Medio | Empezar con Python, añadir lenguajes gradualmente |
| Memoria en proyectos grandes | Media | Medio | Streaming, análisis incremental |

---

## Referencias

### Papers
- "Deckard: Scalable and Accurate Tree-Based Detection of Code Clones" (Jiang et al., 2007)
- "A Survey on Software Clone Detection Research" (Roy et al., 2009)

### Herramientas Existentes
- **PMD CPD**: Java-based, detecta Type-1 y Type-2
- **Simian**: Comercial, multi-lenguaje
- **jscpd**: JavaScript, popular en ecosistema npm
- **CCFinder**: Académico, token-based

### Recursos Técnicos
- Rabin-Karp: https://cp-algorithms.com/string/rabin-karp.html
- Rolling Hash: https://codeforces.com/blog/entry/60445

---

## Conclusión

El Code Similarity Detector es una adición de alto valor a AEGIS:
- **No duplica** funcionalidad existente
- **Demuestra** habilidades avanzadas de C++ (algoritmos, paralelismo, optimización)
- **Proporciona** valor real en code reviews y mantenimiento
- **Es visualmente impactante** para demos y portfolio

La implementación sigue el enfoque evolutivo del proyecto, comenzando con detección básica y añadiendo complejidad según las necesidades demostradas.
