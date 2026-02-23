"""
Scraper Computrabajo - Empleos en Narino (Colombia).

URL fija: https://co.computrabajo.com/empleos-en-narino?pubdate=1
  - pubdate=1 -> solo ofertas del ultimo dia
  - Ubicacion: Narino (ya incluida en la URL)

Flujo:
  1. GET a la URL de búsqueda (y páginas siguientes hasta agotar resultados).
  2. Parsear <article id="..."> para obtener IDs y URLs de detalle.
  3. GET al endpoint JSON /offer/{ID}/d/j; si falla, GET a la página de detalle.
  4. Normalizar: extraer location, salary, published desde url/description.
  5. Guardar cada oferta como JSON en Offer/{offer_id}.json.

Al inicio de cada ejecucion se borran TODOS los JSON de la carpeta Offer/
para que solo queden las ofertas de la busqueda actual.
"""
import io
import json
import os
import re
import sys
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from config import (
    BASE_URL,
    MAX_PAGES,
    OFFER_PATH_TEMPLATE,
    OUTPUT_DIR,
    SEARCH_URL,
    USER_AGENT,
)

# Forzar UTF-8 en stdout/stderr para evitar errores de codificacion en Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HEADERS = {"User-Agent": USER_AGENT}

# Pausa entre peticiones de paginas (segundos) para no saturar el sitio
PAGE_DELAY_SEC = 1.5

# Tipo: list of (offer_id, detail_url)
OfferItem = list[tuple[str, str]]


# ── Peticiones HTTP ──────────────────────────────────────────────────────────

def get_search_page(url: str) -> str:
    """GET a la URL de búsqueda y devuelve el HTML."""
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.text


def get_offer_json(offer_id: str) -> dict | None:
    """GET al endpoint JSON de detalle de la oferta. Devuelve dict o None."""
    path = OFFER_PATH_TEMPLATE.format(offer_id=offer_id)
    url = urljoin(BASE_URL, path)
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        if not r.ok:
            return None
        return r.json()
    except (requests.RequestException, json.JSONDecodeError):
        return None


def get_offer_from_detail_page(detail_url: str, offer_id: str) -> dict | None:
    """
    Plan B: obtiene la página HTML de detalle y extrae datos básicos.
    Se usa cuando el endpoint JSON devuelve 404 u otro error.
    """
    if not detail_url:
        return None
    try:
        r = requests.get(detail_url, headers=HEADERS, timeout=30)
        if not r.ok:
            return None
    except requests.RequestException:
        return None

    soup = BeautifulSoup(r.text, "html.parser")
    data: dict = {
        "offer_id": offer_id,
        "url": detail_url,
        "source": "html_detail_page",
    }

    h1 = soup.find("h1")
    if h1:
        data["title"] = h1.get_text(strip=True)

    main = soup.find("main") or soup
    for h2 in main.find_all("h2", limit=3):
        text = h2.get_text(strip=True)
        if len(text) > 3 and "descripción" not in text.lower() and "gracias" not in text.lower():
            data["job_title"] = text
            break

    for h in main.find_all(["h3", "h4"]):
        if (
            "descripción" in h.get_text(strip=True).lower()
            and "oferta" in h.get_text(strip=True).lower()
        ):
            desc_parts: list[str] = []
            for sib in h.find_next_siblings():
                if sib.name in ("h2", "h3", "h4") and "descripción" in (sib.get_text() or "").lower():
                    break
                if sib.get_text(strip=True):
                    desc_parts.append(sib.get_text(strip=True))
            if desc_parts:
                data["description"] = "\n".join(desc_parts[:15])
            break

    return data


# ── Parseo de páginas de listado ─────────────────────────────────────────────

def extract_offers(html: str) -> OfferItem:
    """Parsea el HTML y devuelve (offer_id, url_detalle) de cada <article id='...'>."""
    soup = BeautifulSoup(html, "html.parser")
    result: OfferItem = []
    for tag in soup.find_all("article", id=True):
        offer_id = str(tag["id"]).strip()
        detail_url = ""
        for a in tag.find_all("a", href=True):
            href = a["href"]
            if "ofertas-de-trabajo" in href and "/oferta-" in href:
                detail_url = href.split("#")[0]
                break
        if detail_url:
            result.append((offer_id, urljoin(BASE_URL, detail_url)))
        else:
            result.append((offer_id, ""))
    return result


def extract_next_page_url(html: str) -> str | None:
    """
    Devuelve la URL de la página siguiente o None si no hay más páginas.
    Computrabajo usa <span data-path="..."> con title="Siguiente" para la paginación JS,
    pero también puede usar <a href="..."> con texto "Siguiente".
    """
    soup = BeautifulSoup(html, "html.parser")
    # 1) Enlace <a> con texto "Siguiente"
    for a in soup.find_all("a", href=True):
        if a.get_text(strip=True).lower() == "siguiente":
            href = a["href"].strip()
            if href and href != "#":
                return urljoin(BASE_URL, href)
    # 2) <span title="Siguiente" data-path="..."> (paginación JS)
    for span in soup.find_all("span", attrs={"title": "Siguiente"}):
        path = span.get("data-path")
        if path and path.strip():
            return urljoin(BASE_URL, path.strip())
    return None


def collect_all_offers_from_pages(search_url: str) -> OfferItem:
    """
    Recorre la URL de búsqueda y todas las páginas 'Siguiente'.
    Devuelve la lista completa de (offer_id, detail_url).
    Respeta MAX_PAGES si está definido en config.
    """
    all_offers: OfferItem = []
    url: str | None = search_url
    page_num = 1

    while url:
        if MAX_PAGES is not None and page_num > MAX_PAGES:
            print(f"  Límite de {MAX_PAGES} páginas alcanzado.")
            break
        print(f"  Página {page_num}...", end=" ", flush=True)
        html = get_search_page(url)
        offers = extract_offers(html)
        all_offers.extend(offers)
        print(f"{len(offers)} ofertas encontradas.")
        url = extract_next_page_url(html)
        page_num += 1
        if url and (MAX_PAGES is None or page_num <= MAX_PAGES):
            time.sleep(PAGE_DELAY_SEC)

    return all_offers


# ── Normalización de datos ───────────────────────────────────────────────────

def _extract_location_from_url(url: str, offer_id: str) -> str | None:
    """Extrae la ciudad/lugar desde el slug de la URL (ej: ...-en-pasto-{id})."""
    if not url or not offer_id:
        return None
    match = re.search(r"-en-([^-]+(?:-[^-]+)*)-" + re.escape(offer_id), url)
    if not match:
        return None
    raw = match.group(1).strip()
    return raw.replace("-", " ").title() if raw else None


def _extract_salary_and_trim(description: str) -> tuple[str, str]:
    """
    Extrae el salario al inicio del texto (ej: '$ 6.500.000,00 (Mensual)' o 'A convenir')
    y devuelve (salario, descripción_restante).
    """
    if not description or not description.strip():
        return "A convenir", description or ""
    text = description.strip()
    m = re.match(r"^(A convenir|\$\s*[\d.,]+\s*\([^)]+\))", text, re.IGNORECASE)
    if m:
        salary = m.group(1).strip()
        rest = text[m.end():].strip()
        rest = re.sub(
            r"^Contrato[^.\n]*(?:Tiempo\s+Completo)?[^.\n]*(?:Presencial[^.\n]*)?",
            "",
            rest,
            flags=re.IGNORECASE,
        ).strip()
        return salary, rest
    return "A convenir", text


def _extract_published_and_trim(description: str) -> tuple[str, str]:
    """
    Extrae la fecha de publicación al final del texto
    (ej: 'Hace 6 días', 'Hace 2 horas', 'Hoy (actualizada)')
    y devuelve (published_label, descripción_sin_ese_final).
    """
    if not description or not description.strip():
        return "", description or ""
    text = description.strip()
    pub_pattern = (
        r"(?:Hace\s+\d+\s+(?:días?|horas?|minutos?|meses?)|Ayer|Hoy)\s*(?:\(actualizada\))?"
    )
    match = re.search(pub_pattern, text, re.IGNORECASE)
    if match:
        published = match.group(0).strip()
        rest = text[: match.start()].strip()
        rest = re.sub(
            r"\nRequerimientos\s*\n.*$", "", rest, flags=re.DOTALL | re.IGNORECASE
        ).strip()
        return published, rest
    return "", text


def normalize_offer_data(data: dict) -> None:
    """
    Rellena location, salary y published a partir de url/description cuando falten,
    y limpia description para que no repita esos datos.
    Modifica data in-place.
    """
    offer_id = data.get("offer_id") or ""
    url = data.get("url") or ""

    # Location desde URL si no viene en el JSON
    if not data.get("location") and url and offer_id:
        loc = _extract_location_from_url(url, offer_id)
        if loc:
            data["location"] = loc

    # Salary y published desde description
    desc = data.get("description")
    if desc is not None and isinstance(desc, str):
        salary, desc = _extract_salary_and_trim(desc)
        if not data.get("salary"):
            data["salary"] = salary
        published, desc = _extract_published_and_trim(desc)
        if published and not data.get("published"):
            data["published"] = published
        data["description"] = desc.strip()


# ── Persistencia ─────────────────────────────────────────────────────────────

def clear_offer_dir() -> int:
    """
    Borra todos los archivos JSON de la carpeta OUTPUT_DIR (Offer/).
    Se llama al inicio de cada ejecución para que solo queden las ofertas actuales.
    Devuelve el número de archivos eliminados.
    """
    if not os.path.isdir(OUTPUT_DIR):
        return 0
    deleted = 0
    for name in os.listdir(OUTPUT_DIR):
        if not name.endswith(".json"):
            continue
        path = os.path.join(OUTPUT_DIR, name)
        try:
            os.remove(path)
            deleted += 1
        except OSError as e:
            print(f"  No se pudo borrar {path}: {e}")
    if deleted:
        print(f"Eliminados {deleted} JSON antiguos de {OUTPUT_DIR}/\n")
    return deleted


def save_offer(offer_id: str, data: dict) -> str:
    """Guarda el JSON de la oferta en OUTPUT_DIR/{offer_id}.json."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, f"{offer_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


# ── Ejecución principal ───────────────────────────────────────────────────────

def run() -> None:
    """
    Ejecuta el scraper completo:
      1. Limpia la carpeta Offer/.
      2. Recorre todas las páginas de resultados de SEARCH_URL.
      3. Descarga y guarda cada oferta como JSON.
    """
    print("=" * 60)
    print("Scraper Computrabajo - Empleos en Narino (pubdate=1)")
    print("=" * 60)
    print(f"URL de busqueda: {SEARCH_URL}")
    print(f"Carpeta de salida: {OUTPUT_DIR}\n")

    # 1. Limpiar ofertas antiguas
    clear_offer_dir()

    # 2. Recopilar todas las ofertas de todas las paginas
    print("Recorriendo paginas de resultados...")
    offers = collect_all_offers_from_pages(SEARCH_URL)
    print(f"\nTotal de ofertas encontradas: {len(offers)}\n")

    if not offers:
        print("No se encontraron ofertas. Verifica la URL o el filtro de fecha.")
        return


    # 3. Descargar y guardar cada oferta
    saved = 0
    errors = 0
    for i, (offer_id, detail_url) in enumerate(offers, 1):
        short_id = offer_id[:12] + "..." if len(offer_id) > 12 else offer_id
        print(f"  [{i:>3}/{len(offers)}] {short_id}", end=" -> ", flush=True)

        # Intentar endpoint JSON primero
        data = get_offer_json(offer_id)
        if data is None and detail_url:
            data = get_offer_from_detail_page(detail_url, offer_id)

        if data is None:
            print("sin datos, omitida.")
            errors += 1
            continue

        normalize_offer_data(data)
        path = save_offer(offer_id, data)
        saved += 1
        title = data.get("title") or data.get("job_title") or "(sin título)"
        location = data.get("location") or "?"
        print(f"OK  [{location}]  {title[:55]}")

    print("\n" + "=" * 60)
    print(f"Guardadas: {saved}  |  Sin datos: {errors}  |  Total: {len(offers)}")
    print(f"Carpeta: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    t0 = time.perf_counter()
    run()
    elapsed = time.perf_counter() - t0
    print(f"\nTiempo total: {elapsed:.1f} s ({elapsed / 60:.1f} min)")
