#!/usr/bin/env bash
# ============================================================
#  TU CHAMBITA — Ejecutor automático (Linux / macOS)
#  Uso: bash run_all.sh
#  Para cron (19:00 Colombia = 00:00 UTC): 0 0 * * * /ruta/run_all.sh
#  Ver README_automatizacion.md para más detalles
# ============================================================

# ── 1. Ir al directorio del proyecto ────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

# ── 2. Crear carpeta de logs si no existe ───────────────────
mkdir -p logs

# ── 3. Nombre del log con fecha ──────────────────────────────
LOGFILE="logs/run_$(date +%Y-%m-%d).log"

# ── 4. (Opcional) Activar entorno virtual si existe ─────────
# Descomenta si usas un venv llamado "venv":
# source venv/bin/activate

# ── 5. Ejecutar el orquestador y guardar log ─────────────────
{
  echo ""
  echo "============================================================"
  echo "Ejecucion: $(date '+%d/%m/%Y %H:%M:%S')"
  echo "============================================================"
  python3 run_all.py
} >> "$LOGFILE" 2>&1

echo "Listo. Log guardado en: $LOGFILE"
