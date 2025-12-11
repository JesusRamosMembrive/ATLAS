# Backend Improvement Roadmap

Este documento describe las mejoras potenciales para el backend de AEGIS, organizadas por prioridad y complejidad.

## Estado Actual

✅ **Completado**: Refactoring de SQL crudo a SQLModel ORM (Diciembre 2025)
- Eliminado todo el SQL crudo
- Implementados 7 modelos SQLModel
- 52/52 tests pasando
- Type safety completo

✅ **Completado**: Error Handling & Custom Exceptions (Diciembre 2025)
- Jerarquía de excepciones en `code_map/exceptions.py`
- Exception handlers centralizados en `code_map/api/error_handlers.py`
- Todos los endpoints migrados de HTTPException a excepciones custom
- Error responses estandarizados con code, message, timestamp, path

✅ **Completado**: Async/Await Optimization (Diciembre 2025)
- Módulo `code_map/database_async.py` con AsyncEngine y AsyncSession
- Storage modules migrados: audit, linters, insights
- Todos los endpoints API usando funciones async
- 89/89 tests core pasando (database, API, linters)

---

## Mejoras Propuestas

### 1. ~~Async/Await Optimization~~ ✅ COMPLETADO

**Estado**: Implementado
**Complejidad**: Media
**Impacto**: Alto rendimiento en concurrencia

#### Pasos Completados

- [x] Migrar de SQLModel sync a SQLAlchemy async
- [x] Crear `database_async.py` para usar `create_async_engine`
- [x] Convertir funciones de storage a `async def`
- [x] Actualizar endpoints FastAPI para usar `await`
- [x] Actualizar tests para soportar async
- [ ] Medir mejora de rendimiento (benchmark) - Opcional

#### Ejemplo de Código

```python
# Antes (sync)
def get_settings() -> AppSettings:
    with Session(engine) as session:
        return session.get(AppSettingsDB, 1)

# Después (async)
async def get_settings() -> AppSettings:
    async with AsyncSession(engine) as session:
        result = await session.get(AppSettingsDB, 1)
        return result
```

#### Beneficios
- Mejor uso de recursos en operaciones I/O
- Mayor throughput en FastAPI
- Escalabilidad mejorada

---

### 2. Caching Layer 💾

**Prioridad**: Media  
**Complejidad**: Baja  
**Impacto**: Reducción de latencia 10-100x

#### Pasos

- [ ] Evaluar estrategia: Redis vs in-memory
- [ ] Implementar cache para `AppSettings`
- [ ] Añadir cache invalidation en updates
- [ ] Cache para linter reports recientes
- [ ] Añadir métricas de cache hit/miss
- [ ] Documentar TTL policies

#### Ejemplo de Código

```python
from functools import lru_cache
from datetime import datetime, timedelta

_settings_cache = None
_cache_timestamp = None
CACHE_TTL = timedelta(minutes=5)

def get_cached_settings() -> AppSettings:
    global _settings_cache, _cache_timestamp
    
    now = datetime.now()
    if _settings_cache and _cache_timestamp:
        if now - _cache_timestamp < CACHE_TTL:
            return _settings_cache
    
    _settings_cache = _load_settings_from_db()
    _cache_timestamp = now
    return _settings_cache
```

#### Beneficios
- Reducción drástica de queries a BD
- Mejor experiencia de usuario (latencia)
- Menor carga en SQLite

---

### 3. API Validation con Pydantic 🛡️

**Prioridad**: Media  
**Complejidad**: Baja  
**Impacto**: Mejor DX y seguridad

#### Pasos

- [ ] Crear modelos Pydantic para requests
- [ ] Crear modelos Pydantic para responses
- [ ] Añadir validadores custom (e.g., path exists)
- [ ] Actualizar endpoints para usar modelos
- [ ] Generar OpenAPI schema automático
- [ ] Añadir ejemplos en documentación

#### Ejemplo de Código

```python
from pydantic import BaseModel, Field, validator
from pathlib import Path

class UpdateSettingsRequest(BaseModel):
    root_path: str = Field(..., description="Project root path")
    exclude_dirs: list[str] = Field(default_factory=list)
    include_docstrings: bool = True
    
    @validator('root_path')
    def path_must_exist(cls, v):
        p = Path(v).expanduser().resolve()
        if not p.exists():
            raise ValueError(f"Path does not exist: {v}")
        return str(p)

class SettingsResponse(BaseModel):
    root_path: str
    exclude_dirs: list[str]
    include_docstrings: bool
    
    class Config:
        schema_extra = {
            "example": {
                "root_path": "/home/user/project",
                "exclude_dirs": ["node_modules", ".git"],
                "include_docstrings": True
            }
        }
```

#### Beneficios
- Auto-documentación de API
- Validación automática de inputs
- Mejores mensajes de error
- Type hints en cliente

---

### 4. ~~Error Handling & Custom Exceptions~~ ✅ COMPLETADO

**Estado**: Implementado
**Complejidad**: Baja
**Impacto**: Mejor debugging y UX

#### Pasos Completados

- [x] Definir jerarquía de excepciones custom (`code_map/exceptions.py`)
- [x] Crear exception handlers en FastAPI (`code_map/api/error_handlers.py`)
- [x] Añadir logging estructurado en errores
- [x] Implementar error responses consistentes
- [x] Añadir error codes únicos
- [ ] Documentar errores posibles por endpoint - Opcional

#### Ejemplo de Código

```python
# exceptions.py
class AEGISException(Exception):
    """Base exception for AEGIS"""
    code: str
    message: str
    status_code: int = 500

class DatabaseError(AEGISException):
    code = "DB_ERROR"
    status_code = 500

class SettingsNotFoundError(AEGISException):
    code = "SETTINGS_NOT_FOUND"
    status_code = 404

class InvalidPathError(AEGISException):
    code = "INVALID_PATH"
    status_code = 400

# server.py
@app.exception_handler(AEGISException)
async def aegis_exception_handler(request: Request, exc: AEGISException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "timestamp": datetime.now().isoformat()
            }
        }
    )
```

#### Beneficios
- Errores más informativos
- Debugging más rápido
- Mejor experiencia de usuario
- Logs más útiles

---

### 5. Structured Logging & Observability 📊

**Prioridad**: Media  
**Complejidad**: Media  
**Impacto**: Mejor debugging en producción

#### Pasos

- [ ] Migrar a `structlog` o similar
- [ ] Añadir request ID tracking
- [ ] Log de métricas de performance
- [ ] Integrar con sistema de métricas (Prometheus?)
- [ ] Añadir health check endpoint
- [ ] Dashboard de métricas básico

#### Ejemplo de Código

```python
import structlog

logger = structlog.get_logger()

@app.post("/api/settings")
async def update_settings(request: UpdateSettingsRequest):
    logger.info(
        "settings_update_started",
        root_path=request.root_path,
        exclude_dirs_count=len(request.exclude_dirs)
    )
    
    try:
        result = await save_settings(request)
        logger.info(
            "settings_update_completed",
            duration_ms=...,
            success=True
        )
        return result
    except Exception as e:
        logger.error(
            "settings_update_failed",
            error=str(e),
            error_type=type(e).__name__
        )
        raise
```

#### Beneficios
- Logs parseables (JSON)
- Correlación de requests
- Métricas de performance
- Alertas automáticas

---

### 6. Connection Pooling & Performance 🚀

**Prioridad**: Baja  
**Complejidad**: Baja  
**Impacto**: Mejor rendimiento bajo carga

#### Pasos

- [ ] Configurar pool size en SQLAlchemy
- [ ] Añadir connection timeout
- [ ] Implementar retry logic
- [ ] Añadir circuit breaker para BD
- [ ] Benchmark antes/después
- [ ] Documentar configuración óptima

#### Ejemplo de Código

```python
from sqlalchemy.pool import QueuePool

engine = create_engine(
    sqlite_url,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=3600,
    connect_args={"check_same_thread": False}
)
```

#### Beneficios
- Mejor uso de conexiones
- Manejo de picos de tráfico
- Reducción de overhead

---

### 7. API Rate Limiting 🛡️

**Prioridad**: Baja  
**Complejidad**: Baja  
**Impacto**: Protección contra abuso

#### Pasos

- [ ] Implementar rate limiter (SlowAPI o similar)
- [ ] Configurar límites por endpoint
- [ ] Añadir headers de rate limit
- [ ] Implementar whitelist para CI/CD
- [ ] Logging de rate limit hits
- [ ] Documentar límites en API docs

#### Ejemplo de Código

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/api/analyze")
@limiter.limit("10/minute")
async def analyze_project():
    ...
```

#### Beneficios
- Protección contra DoS
- Uso justo de recursos
- Mejor estabilidad

---

## Priorización

### Alcance Actual - COMPLETADO ✅
1. ✅ SQL → SQLModel (Completado)
2. ✅ Error Handling & Custom Exceptions (Completado)
3. ✅ Async/Await Optimization (Completado)

### Futuro (si se necesita)
Las mejoras 2, 3, 5, 6, 7 están documentadas arriba pero **no son prioritarias** dado el tamaño del proyecto y el uso limitado de la base de datos.

---

## Métricas de Éxito

Para cada mejora, medir:
- **Performance**: Latencia p50, p95, p99
- **Reliability**: Error rate, uptime
- **Developer Experience**: Tiempo de debugging, facilidad de testing
- **Code Quality**: Test coverage, type coverage

---

## Notas

- Todas las mejoras son **opcionales** y pueden implementarse de forma incremental
- Priorizar según necesidades reales del proyecto
- Cada mejora debe incluir tests y documentación
- Considerar impacto en deployment y CI/CD

---

*Última actualización: 2025-12-11*

---

## Archivos Creados/Modificados (Async + Error Handling)

### Nuevos Archivos
- `code_map/exceptions.py` - Jerarquía de excepciones custom
- `code_map/api/error_handlers.py` - FastAPI exception handlers
- `code_map/database_async.py` - Async database engine y sessions

### Archivos Modificados
- `code_map/server.py` - Registra exception handlers
- `code_map/audit/storage.py` - Funciones async añadidas
- `code_map/audit/__init__.py` - Exports async
- `code_map/api/audit.py` - Usa async storage
- `code_map/linters/storage.py` - Funciones async añadidas
- `code_map/linters/__init__.py` - Exports async
- `code_map/api/linters.py` - Usa async storage + custom exceptions
- `code_map/insights/storage.py` - Funciones async añadidas
- `code_map/insights/__init__.py` - Exports async
- `code_map/api/integrations.py` - Usa async storage
- `code_map/api/preview.py` - Usa custom exceptions
- `code_map/api/settings.py` - Usa custom exceptions
- `code_map/api/analysis.py` - Usa custom exceptions
- `code_map/api/graph.py` - Usa custom exceptions
- `code_map/api/similarity.py` - Usa custom exceptions
- `code_map/api/stage.py` - Usa custom exceptions
- `code_map/api/terminal.py` - Usa custom exceptions
- `requirements.txt` - Añade aiosqlite
- `tests/test_api.py` - Actualiza para async + error format
