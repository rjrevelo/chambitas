# 🤖 Automatización — Tu Chambita

Guía completa para ejecutar los scrapers de **Computrabajo** y **Magneto** de forma automática todos los días y generar el reporte `.md`.

---

## 📁 Archivos involucrados

| Archivo | Descripción |
|---------|-------------|
| `run_all.py` | Orquestador principal: ejecuta los dos scrapers y luego genera el reporte |
| `run_all.bat` | Script para **Windows** (Programador de tareas) |
| `run_all.sh` | Script para **Linux / macOS** (cron) |
| `logs/` | Carpeta donde se guardan los logs de cada ejecución |
| `reports/` | Carpeta donde quedan los reportes `.md` generados |

---

## 🚀 Ejecución manual (prueba rápida)

Desde la raíz del proyecto:

```bash
# Windows
python run_all.py

# Linux / macOS
python3 run_all.py
```

El script:
1. Ejecuta `Computrabajo_Narino/scraper.py`
2. Ejecuta `Magneto_Narino/scraper.py`
3. Ejecuta `generate_report.py`
4. Deja el reporte en `reports/reporte_ofertas_YYYY-MM-DD_HH-MM-SS.md`

---

## ⏰ Automatización en Windows — Programador de tareas

### Paso 1 — Abrir el Programador de tareas

1. Presiona `Win + R`, escribe `taskschd.msc` y pulsa **Enter**.
2. En el panel derecho haz clic en **"Crear tarea básica…"**.

### Paso 2 — Configurar la tarea

| Campo | Valor |
|-------|-------|
| **Nombre** | `TuChambita - Scrapers diarios` |
| **Descripción** | Ejecuta scrapers de empleo y genera reporte MD |
| **Desencadenador** | Diariamente |
| **Hora de inicio** | `19:00:00` |
| **Acción** | Iniciar un programa |

### Paso 3 — Configurar la acción

- **Programa o script:**
  ```
  C:\Windows\System32\cmd.exe
  ```
- **Agregar argumentos:**
  ```
  /c "d:\Cursor_Proyectos\tu_chambita\run_all.bat"
  ```
- **Iniciar en (directorio de trabajo):**
  ```
  d:\Cursor_Proyectos\tu_chambita
  ```

> 💡 **Alternativa directa con Python:**
> - Programa: ruta completa a `python.exe` (ej: `C:\Python312\python.exe`)
> - Argumentos: `d:\Cursor_Proyectos\tu_chambita\run_all.py`
> - Iniciar en: `d:\Cursor_Proyectos\tu_chambita`

### Paso 4 — Opciones adicionales recomendadas

En la pestaña **"Condiciones"**:
- ✅ Iniciar la tarea solo si el equipo está conectado a la red.

En la pestaña **"Configuración"**:
- ✅ Si la tarea ya se está ejecutando, no iniciar una nueva instancia.
- ✅ Ejecutar la tarea lo antes posible si se perdió una ejecución programada.

### Paso 5 — Verificar

Haz clic derecho sobre la tarea → **"Ejecutar"** para probarla manualmente.  
Revisa el log en `logs\run_YYYY-MM-DD.log`.

---

## ⏰ Automatización en Linux / macOS — cron

### Paso 1 — Dar permisos de ejecución al script

```bash
chmod +x /ruta/al/proyecto/run_all.sh
```

### Paso 2 — Editar el crontab

```bash
crontab -e
```

### Paso 3 — Agregar la línea de cron

```cron
# Ejecutar todos los días a las 19:00 hora Colombia = 00:00 UTC
0 0 * * * /ruta/al/proyecto/run_all.sh
```

> ⚠️ **Importante:** cron usa la hora del servidor.
> - Si el servidor está en **UTC**: usa `0 0 * * *` (00:00 UTC = 19:00 Colombia).
> - Si el servidor está configurado en **hora Colombia**: usa `0 19 * * *`.

### Paso 4 — Verificar que cron está activo

```bash
# Ver las tareas programadas
crontab -l

# Ver logs del sistema (Linux)
grep CRON /var/log/syslog | tail -20
```

---

## ☁️ Publicar el reporte `.md` online (GitHub Pages)

Para que el reporte quede disponible en internet de forma automática:

### Opción A — GitHub Actions (recomendada)

1. Sube el proyecto a un repositorio de GitHub.
2. Crea el archivo `.github/workflows/scraper_diario.yml` con el siguiente contenido:

```yaml
name: Scrapers diarios — Tu Chambita

on:
  schedule:
    # Todos los días a las 12:00 UTC = 7:00 AM Colombia
    - cron: "0 12 * * *"
  workflow_dispatch:   # permite ejecutar manualmente desde GitHub

jobs:
  scrape-and-report:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout del repositorio
        uses: actions/checkout@v4

      - name: Configurar Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Instalar dependencias
        run: |
          pip install -r Computrabajo_Narino/requirements.txt
          pip install -r Magneto_Narino/requirements.txt

      - name: Ejecutar scrapers y generar reporte
        run: python run_all.py

      - name: Copiar último reporte como index.md (para GitHub Pages)
        run: |
          LATEST=$(ls -t reports/reporte_ofertas_*.md | head -1)
          cp "$LATEST" docs/index.md

      - name: Commit y push del reporte
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add reports/ docs/index.md
          git commit -m "chore: reporte diario $(date +'%Y-%m-%d')" || echo "Sin cambios"
          git push
```

3. Crea la carpeta `docs/` en la raíz del proyecto y activa **GitHub Pages** apuntando a la rama `main` / carpeta `docs`.
4. El reporte estará disponible en: `https://TU_USUARIO.github.io/TU_REPO/`

### Opción B — Netlify Drop (sin código)

1. Genera el reporte localmente con `python run_all.py`.
2. Arrastra la carpeta `reports/` a [netlify.com/drop](https://app.netlify.com/drop).
3. Netlify te da una URL pública inmediatamente.

---

## 📋 Estructura de logs

Cada ejecución genera (o actualiza) un archivo en `logs/`:

```
logs/
  run_2026-02-23.log   ← log del día 23 de febrero
  run_2026-02-24.log   ← log del día 24 de febrero
  ...
```

Si hay errores, el log mostrará el traceback completo de Python.

---

## 🔧 Solución de problemas frecuentes

| Problema | Solución |
|----------|----------|
| `ModuleNotFoundError: requests` | Ejecuta `pip install -r Computrabajo_Narino/requirements.txt` |
| El Programador de tareas no encuentra Python | Usa la ruta completa: `C:\Python312\python.exe` |
| El scraper no encuentra ofertas | Verifica la conexión a internet y que las URLs de los sitios no hayan cambiado |
| El reporte queda vacío | Revisa los logs; puede que los scrapers fallaron antes de guardar JSON |
| cron no ejecuta el script | Verifica permisos con `chmod +x run_all.sh` y usa rutas absolutas en el crontab |

---

_Documentación generada para el proyecto **Tu Chambita**._
