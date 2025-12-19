# Guía de Contribución

## Requisitos del Sistema

### Python
- **Versión mínima**: Python 3.10+
- Se recomienda usar `uv` para gestión de dependencias

### Dependencias Python

**Opción A: Usando uv (recomendado - más rápido)**
```bash
# Instalar uv (si no está instalado)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Instalar dependencias
uv sync --all-extras
```

**Opción B: Usando pip (legacy)**
```bash
pip install -r requirements.txt
```

#### Dependencias principales:
- `simple-term-menu` - Para el menú interactivo de prompt_helper.py (requerida)
- `pyperclip` - Para copiar al portapapeles automáticamente (opcional)

### Dependencias del Sistema (Opcional)

**Estas dependencias son OPCIONALES**. El script funciona sin ellas, pero no copiará automáticamente al portapapeles.

Para que `pyperclip` funcione correctamente en Linux, necesitas instalar uno de los siguientes mecanismos de portapapeles:

**Para sistemas X11:**
```bash
sudo apt-get install xclip
# o
sudo apt-get install xsel
```

**Para sistemas Wayland:**
```bash
sudo apt-get install wl-clipboard
```

Si no estás seguro de cuál usar, instala ambos:
```bash
sudo apt-get install xclip xsel wl-clipboard
```

**Sin estas dependencias**: El script funcionará normalmente, pero deberás copiar el texto manualmente usando el ratón (Ctrl+Shift+C).

## Configuración del Entorno de Desarrollo

1. **Clonar el repositorio**:
   ```bash
   git clone <repo-url>
   cd AEGIS
   ```

2. **Instalar dependencias (con uv - recomendado)**:
   ```bash
   # Instalar uv si no está instalado
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Instalar todas las dependencias (crea venv automáticamente)
   uv sync --all-extras
   ```

   **Alternativa con pip:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # En Linux/Mac
   # o
   .venv\Scripts\activate     # En Windows
   pip install -r requirements.txt
   ```

3. **Instalar dependencias del sistema** (ver sección anterior)

## Uso del Script Helper

### prompt_helper.py

El script tiene dos modos de uso: **interactivo** y **comando**.

#### Modo Interactivo (por defecto)

Navegación visual con menús:

```bash
python prompt_helper.py
```

**Navegación:**
- Usa las flechas ↑/↓ para moverte entre opciones
- Enter para seleccionar
- Los snippets se muestran en pantalla
- Si `pyperclip` está instalado y configurado, se copian automáticamente al portapapeles
- Si no, puedes copiar el texto manualmente con el ratón (Ctrl+Shift+C)

#### Modo Comando

Para usar desde scripts o línea de comandos:

**Listar todos los prompts:**
```bash
python prompt_helper.py list
```

**Mostrar un prompt específico:**
```bash
python prompt_helper.py show debugging/stuck
python prompt_helper.py show planning/feature
```

**Copiar un prompt al portapapeles:**
```bash
python prompt_helper.py copy debugging/stuck-in-loop
python prompt_helper.py copy refactoring/simplification
```

**Notas:**
- El matching es flexible: `stuck` encontrará "Stuck in Loop"
- El formato es `categoria/nombre` (usa `-` en lugar de espacios)
- Usa `python prompt_helper.py --help` para más información

## Estructura del Proyecto

```
Claude-Prompt-Library/
├── templates/
│   └── docs/
│       └── PROMPT_LIBRARY.md    # Biblioteca de prompts
├── prompt_helper.py              # Script navegador de prompts
├── requirements.txt              # Dependencias Python
└── CONTRIBUTING.md               # Este archivo
```

## Añadir Nuevos Prompts

1. Edita `templates/docs/PROMPT_LIBRARY.md`
2. Sigue la estructura existente:
   ```markdown
   ## CATEGORÍA

   ### Nombre del Prompt
   ```
   contenido del prompt
   ```
   ```
3. El script `prompt_helper.py` los detectará automáticamente

## Problemas Comunes

### Error: "Pyperclip could not find a copy/paste mechanism"
**Solución**: Instala las dependencias del sistema mencionadas arriba (xclip, xsel, o wl-clipboard)

### El menú no se ve bien
**Solución**: Asegúrate de usar una terminal que soporte códigos ANSI y UTF-8

## Contribuir

1. Crea un branch para tu feature: `git checkout -b mi-feature`
2. Haz tus cambios
3. Commit con mensajes descriptivos
4. Push y crea un Pull Request

## Licencia

[Añadir licencia según corresponda]
