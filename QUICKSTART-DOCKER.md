# Quick Start - Docker Kiosk Mode

Guía rápida para ejecutar Code Map en modo kiosco con Docker.

---

## 🚀 Inicio Rápido (Linux)

```bash
# 1. Asegúrate de tener Docker instalado
sudo apt install docker.io docker-compose-plugin

# 2. Asegúrate de tener Chrome instalado
sudo apt install google-chrome-stable

# 3. Ejecuta el launcher
./launch-kiosk.sh

# 4. Ingresa el path del proyecto a analizar (o Enter para directorio actual)
# Ejemplo: /home/usuario/mi-proyecto

# 5. Espera a que build y Chrome se abra automáticamente en modo kiosk
```

**Salir:** `Alt+F4`

**Detener contenedor:** `docker compose down`

---

## 🚀 Inicio Rápido (Windows)

```cmd
REM 1. Asegúrate de tener Docker Desktop instalado
REM Descarga de: https://www.docker.com/products/docker-desktop/

REM 2. Asegúrate de tener Chrome instalado
REM Descarga de: https://www.google.com/chrome/

REM 3. Ejecuta el launcher
launch-kiosk.bat

REM 4. Ingresa el path del proyecto a analizar (o Enter para directorio actual)
REM Ejemplo: C:\Users\usuario\mi-proyecto

REM 5. Espera a que build y Chrome se abra automáticamente en modo kiosk
```

**Salir:** `Alt+F4`

**Detener contenedor:** `docker compose down`

---

## ⚙️ Configuración Opcional

### Cambiar Puerto

Edita `docker-compose.yml`:

```yaml
ports:
  - "9000:8010"  # Cambia 8080 por el puerto que prefieras
```

Luego actualiza los scripts de launcher para usar el nuevo puerto.

### Habilitar Ollama (AI Insights)

Edita `docker-compose.yml`:

```yaml
environment:
  - CODE_MAP_OLLAMA_BASE_URL=http://host.docker.internal:11434
  - CODE_MAP_OLLAMA_MODEL=codellama
```

### Limitar Recursos

Edita `docker-compose.yml` (descomenta la sección `deploy`):

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
```

---

## 🔧 Comandos Útiles

```bash
# Ver logs del contenedor
docker compose logs -f

# Reiniciar contenedor
docker compose restart

# Detener contenedor
docker compose down

# Limpiar todo (incluyendo volúmenes)
docker compose down -v

# Rebuild completo
docker compose build --no-cache
docker compose up -d

# Acceder al contenedor (debug)
docker compose exec code-map bash
```

---

## 🌐 Acceso Manual (sin kiosk)

Si prefieres abrir el navegador manualmente:

```bash
# Inicia el contenedor
export PROJECT_PATH=/path/to/project
docker compose up -d

# Abre tu navegador en:
# http://localhost:8080
```

**API Docs:** http://localhost:8080/docs

---

## 🐛 Problemas Comunes

### "Docker is not running"
```bash
# Linux
sudo systemctl start docker

# Windows/macOS
# Inicia Docker Desktop
```

### "Port 8080 already in use"
```bash
# Encuentra qué proceso usa el puerto
sudo lsof -i :8080

# Mata el proceso o cambia el puerto en docker-compose.yml
```

### "Chrome not found"
```bash
# Linux
sudo apt install google-chrome-stable

# macOS/Windows
# Descarga de https://www.google.com/chrome/
```

### El build tarda mucho
```bash
# Normal en el primer build (~5-10 minutos)
# Siguientes builds son más rápidos gracias al cache
```

### El frontend no carga
```bash
# Rebuild sin cache
docker compose down
docker compose build --no-cache
docker compose up -d
```

---

## 📖 Documentación Completa

Para más detalles, consulta:
- [README-DOCKER.md](README-DOCKER.md) - Documentación completa
- [TESTING-DOCKER.md](TESTING-DOCKER.md) - Guía de testing

---

## ✨ Características

- ✅ **Modo kiosk**: Chrome en pantalla completa automático
- ✅ **Producción**: Frontend optimizado + backend FastAPI
- ✅ **Persistencia**: Base de datos sobrevive reinicios
- ✅ **Multiplataforma**: Linux, macOS, Windows
- ✅ **Aislado**: Contenedor completamente separado del host
- ✅ **Flexible**: Analiza cualquier proyecto montando el directorio

---

**¡Listo para usar!** 🎉
