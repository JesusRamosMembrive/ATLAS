# Backend Quickstart

Guía rápida para poner en marcha el backend, validar que el watcher funciona y consultar el estado del índice antes de conectar la UI.

## Requisitos previos
1. Crear y activar el entorno virtual (`.venv`) y asegurarse de tener las dependencias instaladas:
   ```bash
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt  # o pip install -e .
   .venv/bin/pip install watchdog            # necesario para el watcher en vivo
   .venv/bin/pip install esprima             # habilita análisis de JS/TS
   .venv/bin/pip install tree_sitter_languages  # soporte TypeScript/TSX
   .venv/bin/pip install beautifulsoup4      # extracción básica en HTML
   ```
   En Windows usa `.venv\Scripts\pip.exe` para los comandos equivalentes.
2. Elegir un directorio de trabajo que actuará como proyecto a analizar. En los ejemplos usamos `/tmp/code-map-playground/project`.
3. Registra esa ruta con el CLI:
   ```bash
   python -m code_map config set-root /tmp/code-map-playground/project
   ```
   Si omites este paso, el backend usará el directorio actual en el que lances el comando `run`.

### Unificación de entornos virtuales

Si trabajaste previamente con otro entorno creado en la raíz (carpetas `bin/`, `lib/`, `include/`, etc.), deja únicamente `.venv/` para evitar conflictos en el `PATH`:

```bash
rm -rf bin include lib lib64 pyvenv.cfg venv
```

Después, reactiva `.venv`, reinstala dependencias si es necesario y comprueba que los comandos (`ruff`, `black`, etc.) se resuelven dentro de `.venv/bin/`.

## Arranque del servidor
```bash
python -m code_map run --host 0.0.0.0 --port 8010 --log-level info
```

- Añade `--root /ruta/al/proyecto` si quieres sobreescribir temporalmente la ruta configurada.
- Al arrancar verás logs del estado del watcher. Si aparece “watchdog no está disponible”, el watcher queda deshabilitado (instala `watchdog` para activarlo).
- Usa `python -m code_map --help` para ver todos los comandos disponibles.

### Opciones adicionales
- `CODE_MAP_INCLUDE_DOCSTRINGS` (`true` por defecto): controla si el motor añade docstrings en los resultados. Ajusta a `0` o `false` para omitirlos.

## Empaquetar el backend con PyInstaller

Cuando necesites distribuir el backend como ejecutable autónomo, usa `pyinstaller` apuntando al módulo principal `code_map` (el mismo que ejecutas con `python -m code_map`). Pasos recomendados:

1. Activa `.venv` e instala PyInstaller si aún no está presente:
   ```bash
   .venv/bin/pip install pyinstaller
   ```
2. Genera el binario de una sola pieza:
   ```bash
   pyinstaller --name code-map-backend --onefile code_map/__main__.py
   ```
   - En lugar de un script suelto, apuntamos al `__main__` del paquete (`python -m code_map` hace exactamente lo mismo).
   - PyInstaller dejará el ejecutable final en `dist/code-map-backend` (o `code-map-backend.exe` en Windows).
3. Copia el ejecutable donde lo vayas a publicar (por ejemplo, una release en GitHub) o súbelo a tu web.
4. Al ejecutar el binario, pasa los mismos argumentos que usarías con `python -m code_map`:
   ```bash
   ./code-map-backend --host 0.0.0.0 --port 8010 --root /ruta/al/proyecto
   ```

Recuerda incluir junto al ejecutable cualquier archivo de configuración requerido (`.code-map/code-map.json`, etc.) o documentar cómo generar la configuración al primer arranque.

## Validación manual
1. **Crear/editar archivos** en la ruta configurada:
   ```bash
   echo 'def demo():\n    return 42' > /tmp/code-map-playground/project/demo.py
   ```
2. **Consultar el árbol y archivos**:
   ```bash
   curl http://localhost:8010/tree | jq
   curl http://localhost:8010/files/demo.py | jq
   ```
3. **Escuchar eventos SSE** (verás `event: update` cuando haya cambios):
   ```bash
   curl -N http://localhost:8010/events
   ```
4. **Forzar un rescan completo** (si el watcher está desactivado o después de muchos cambios):
   ```bash
   curl -X POST http://localhost:8010/rescan
   ```

El backend persiste un snapshot en `<root>/.code-map/code-map.json`; al reiniciar lo carga para responder rápido y luego ejecuta un escaneo completo en segundo plano.

## Integración con Ollama

Para que el panel "Stage Toolkit" pueda consultar y hacer ping a modelos locales debes tener Ollama instalado y sirviendo peticiones.

1. **Instala Ollama** siguiendo la guía oficial según tu plataforma.
2. **Arranca el servicio** antes (o en paralelo) al backend:
   ```bash
   ollama serve
   ```
   - Por defecto queda escuchando en `http://127.0.0.1:11434`.
   - Si prefieres otra dirección/puerto, exporta `OLLAMA_HOST=http://host:puerto` antes de iniciar Uvicorn.
3. **Verifica la conexión** desde nuestro backend:
   ```bash
   curl -s http://localhost:8010/integrations/ollama/status | jq
   ```
   Deberías ver `installed: true` y `running: true`. Si todo está correcto puedes probar un chat corto:
   ```bash
   curl -s -X POST http://localhost:8010/integrations/ollama/test \
     -H 'Content-Type: application/json' \
     -d '{"model":"gpt-oss:latest","prompt":"ping"}' | jq
   ```
4. **Usa la UI**. En la vista Stage Toolkit:
   - Pulsa "Iniciar Ollama" si el servicio aún no estaba levantado (esto ejecuta `ollama serve`).
   - Selecciona un modelo y lanza “Probar chat”.
   - Recuerda que la primera llamada puede tardar mientras se carga el modelo; si ves un aviso de “modelo en carga”, espera unos segundos y reintenta.
   - Consulta la página “Ollama” para revisar el historial de insights y recomendaciones generadas.
   - En esa página puedes escoger el enfoque del análisis (general, refactors, fallos, duplicación, testing) y ver el prompt exacto que se enviará a Ollama.

Si tienes problemas de conectividad, ejecuta `python tools/debug_ollama.py --endpoint http://127.0.0.1:11434 --model <modelo>` para comprobar TCP, `/api/tags` y un chat de prueba.

## Siguientes pasos
- Añadir logging más detallado en los batch del watcher si hace falta visibilidad extra.
- Escribir pruebas de integración una vez tengamos scripts automatizados.
- Iniciar la configuración del frontend (React/Vite) consumiendo estos endpoints.

### Hacia un setup más sencillo (plan de trabajo)
- Extender el CLI (`python -m code_map`) con comandos que automaticen la creación del entorno virtual y la instalación de dependencias.
- Ajustar `code_map.settings.load_settings` para que, ante la ausencia de variables, asuma la carpeta actual como root y use `<root>/.code-map/state.db` por defecto.
- Refinar el pipeline de linters: usar siempre `sys.executable -m ...`, registrar el `PATH` efectivo y mostrar en la UI un aviso claro cuando se omita una herramienta.
- Mantener este documento actualizado con una tabla de problemas comunes (DB de solo lectura, reportes antiguos, etc.) y pasos para resolverlos.
