"""
Configuración para el scraper de Computrabajo — Empleos en Nariño (Colombia).
URL fija: https://co.computrabajo.com/empleos-en-narino?pubdate=1
Filtra solo las ofertas publicadas en el último día (pubdate=1).
Los JSON se guardan en tu_chambita/Computrabajo_Narino/Offer/
y se borran en cada ejecución para mantener solo las ofertas actuales.
"""
from pathlib import Path

# Carpeta de este scraper
SCRAPER_DIR = Path(__file__).resolve().parent

# ── URL de búsqueda ──────────────────────────────────────────────────────────
BASE_URL = "https://co.computrabajo.com"

# URL principal: empleos en Nariño publicados en el último día
SEARCH_URL = "https://co.computrabajo.com/empleos-en-narino?pubdate=1"

# Endpoint JSON de detalle de oferta
OFFER_PATH_TEMPLATE = "/offer/{offer_id}/d/j?ipo=1&iapo=1"

# ── Salida ───────────────────────────────────────────────────────────────────
# Carpeta donde se guardan los JSON de ofertas (se limpia en cada ejecución)
OUTPUT_DIR = str(SCRAPER_DIR / "Offer")

# ── Paginación ───────────────────────────────────────────────────────────────
# None = sin límite (recorre todas las páginas disponibles)
MAX_PAGES: int | None = None

# ── HTTP ─────────────────────────────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
