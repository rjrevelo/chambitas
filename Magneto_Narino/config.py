"""
Configuración para el scraper de Magneto365 - Nariño (Colombia).
URL fija: https://www.magneto365.com/co/trabajos/buscar/loc-narino-co/hoy
Filtra ofertas publicadas HOY en el departamento de Nariño.
"""
import os
from pathlib import Path

# ── Rutas ──────────────────────────────────────────────────────────────────────
# Carpeta raíz de este módulo (Magneto_Narino/)
MODULE_DIR = Path(__file__).resolve().parent

# Carpeta donde se guardan los JSON de ofertas: Magneto_Narino/offers/
OUTPUT_DIR = str(MODULE_DIR / "offers")

# ── URL de búsqueda ────────────────────────────────────────────────────────────
# URL fija con filtro de ubicación Nariño y filtro "hoy"
SEARCH_URL = "https://www.magneto365.com/co/trabajos/buscar/loc-narino-co/hoy"

# Base URL de Magneto365 Colombia
BASE_URL = "https://www.magneto365.com"
JOB_PAGE_PATH_TEMPLATE = "/co/empleos/{slug}"

# API para detalle de vacante
API_BASE = "https://api.magneto365.com"
API_JOBS_SUGGESTED_TEMPLATE = "/jobs/v2/jobs/suggested/mimir-wisdom?vacantId={vacant_id}"

# ── HTTP ───────────────────────────────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# ── Extracción con LLM (Ollama) ────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")
OLLAMA_TIMEOUT = int(os.environ.get("OLLAMA_TIMEOUT", "120"))


def get_job_page_url(slug: str) -> str:
    """URL de la página de detalle de una oferta."""
    return f"{BASE_URL}{JOB_PAGE_PATH_TEMPLATE.format(slug=slug)}"


def get_api_detail_url(vacant_id: str) -> str:
    """URL del API de detalle de vacante."""
    return f"{API_BASE}{API_JOBS_SUGGESTED_TEMPLATE.format(vacant_id=vacant_id)}"
