"""
Scraper Magneto365 - Nariño (Colombia).
URL fija: https://www.magneto365.com/co/trabajos/buscar/loc-narino-co/hoy
Filtra ofertas publicadas HOY en el departamento de Nariño.

Comportamiento:
  - Cada ejecución borra los JSON anteriores en offers/ y guarda los nuevos.
  - Recorre todas las páginas de resultados (paginación ?paginator[page]=N).
  - Extrae el detalle de cada oferta desde la página HTML (JSON-LD) y/o la API.
  - Guarda un JSON por oferta en Magneto_Narino/offers/.

Uso:
    python scraper.py
"""
import json
import os
import re
import sys
import time
from urllib.parse import urljoin, urlparse, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup

from config import (
    SEARCH_URL,
    OUTPUT_DIR,
    USER_AGENT,
    get_job_page_url,
    get_api_detail_url,
)

# ── Cabeceras HTTP ─────────────────────────────────────────────────────────────
HEADERS = {"User-Agent": USER_AGENT}
HEADERS_API = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json",
    "Referer": "https://www.magneto365.com/",
    "Origin": "https://www.magneto365.com",
}

# ── Expresiones regulares ──────────────────────────────────────────────────────
# Slug de oferta con ID numérico al final (ej: director-xxx-790953)
RE_VACANT_ID = re.compile(r"([a-z0-9]+(?:-[a-z0-9]+)*-\d+)$", re.I)
RE_VACANT_ID_QUERY = re.compile(r"vacantId=([^&\s]+)", re.I)
# URLs de ofertas en el listado: /co/empleos/slug-123456
RE_EMPLEOS_SLUG_ID = re.compile(r"/co/empleos/([a-z0-9]+(?:-[a-z0-9]+)*-\d{5,})", re.I)

# Metadatos desde HTML
RE_HACE_DIAS = re.compile(r"Hace\s+(\d+)\s+(d[ií]as|d[ií]a)", re.I)
RE_HACE_SEMANAS = re.compile(r"Hace\s+(\d+)\s+semana", re.I)
RE_HACE_MESES = re.compile(r"Hace\s+(\d+)\s+mes", re.I)
RE_SALARIO_A_CONVENIR = re.compile(r"salario\s+a\s+convenir|a\s+convenir", re.I)
RE_NIVEL_ESTUDIOS_HTML = re.compile(
    r"Nivel\s+de\s+estudios?\s*:</p>\s*<p>([^<]+)</p>", re.I
)
RE_NIVEL_EDUCACION_HTML = re.compile(
    r"Nivel\s+de\s+educaci[oó]n\s*:</p>\s*<p>([^<]+)</p>", re.I
)
RE_NIVEL_ESTUDIOS = re.compile(
    r"Nivel\s+de\s+estudios?[:\s]+(.+?)(?=\n\s*(?:Experiencia|Salario|Requisitos|Habilidades)\s*:|\Z)",
    re.I | re.DOTALL,
)
RE_NIVEL_EDUCACION = re.compile(
    r"Nivel\s+de\s+educaci[oó]n[:\s]+(.+?)(?=\n\s*(?:Experiencia|Salario|Requisitos|Habilidades)\s*:|\Z)",
    re.I | re.DOTALL,
)
RE_ANOS_EXPERIENCIA = re.compile(r"(\d+)\s*a[nñ]os?\s+de\s+experiencia", re.I)
RE_EXPERIENCIA_LABEL = re.compile(
    r"Experiencia[:\s]+([^\n<\.]+?)(?:\s*$|\s*Nivel|\s*Salario)", re.I | re.DOTALL
)
RE_SALARIO_NUM = re.compile(r"[\$]?\s*([\d\.]+)\s*\.?\s*(\d{3})\s*\.?\s*(\d{3})", re.I)


# ── Paginación ─────────────────────────────────────────────────────────────────

def get_page_url(base_url: str, page: int) -> str:
    """Añade el parámetro de paginación a la URL. page=1 devuelve la URL sin cambios."""
    if page <= 1:
        return base_url
    parsed = urlparse(base_url)
    params: dict = {}
    if parsed.query:
        from urllib.parse import parse_qs
        for k, v in parse_qs(parsed.query).items():
            params[k] = v[0] if isinstance(v, list) and v else v
    params["paginator[page]"] = str(page)
    new_query = urlencode(params)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )


# ── Extracción de IDs desde el HTML ───────────────────────────────────────────

def _extract_ids_from_empleos_urls(html: str) -> list[str]:
    """Extrae slugs con ID desde URLs /co/empleos/slug-123456 en el HTML."""
    seen: set[str] = set()
    ids: list[str] = []
    for m in RE_EMPLEOS_SLUG_ID.finditer(html):
        slug = m.group(1).strip()
        if slug and slug not in seen:
            seen.add(slug)
            ids.append(slug)
    return ids


def _extract_ids_from_next_data(html: str) -> list[str]:
    """Extrae vacantId desde el bloque __NEXT_DATA__ de Next.js."""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script or not script.string:
        return []
    try:
        data = json.loads(script.string)
    except json.JSONDecodeError:
        return []

    ids: list[str] = []

    def walk(obj, depth: int = 0) -> None:
        if depth > 15:
            return
        if isinstance(obj, dict):
            if "vacantId" in obj and obj["vacantId"]:
                ids.append(str(obj["vacantId"]).strip())
            for v in obj.values():
                walk(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                walk(item, depth + 1)

    walk(data)
    return list(dict.fromkeys(ids))


def _extract_ids_from_links(html: str, base_url: str) -> list[str]:
    """Extrae vacantId desde enlaces del HTML."""
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    ids: list[str] = []
    for a in soup.find_all("a", href=True):
        href = (a["href"] or "").strip()
        if not href:
            continue
        full = urljoin(base_url, href)
        parsed = urlparse(full)
        if parsed.query:
            m = RE_VACANT_ID_QUERY.search(parsed.query)
            if m:
                vid = m.group(1).strip()
                if vid and vid not in seen:
                    seen.add(vid)
                    ids.append(vid)
        path = (parsed.path or "").strip("/")
        if "/co/trabajos/" in full or path.startswith("co/trabajos/"):
            segment = path.split("/")[-1].split("?")[0]
            m = RE_VACANT_ID.search(segment)
            if m:
                vid = m.group(1).strip()
                if vid and vid not in seen:
                    seen.add(vid)
                    ids.append(vid)
    return ids


def extract_vacant_ids(html: str, page_url: str) -> list[str]:
    """Obtiene todos los vacantId de la página. Prioridad: /co/empleos/ > __NEXT_DATA__ > enlaces."""
    ids = _extract_ids_from_empleos_urls(html)
    if ids:
        return ids
    ids = _extract_ids_from_next_data(html)
    if ids:
        return ids
    return _extract_ids_from_links(html, page_url)


def fetch_all_vacant_ids(max_pages: int = 50) -> list[str]:
    """
    Recorre todas las páginas de resultados de SEARCH_URL y devuelve la lista
    completa de vacantId únicos encontrados.
    """
    seen: set[str] = set()
    result: list[str] = []
    page = 1
    while page <= max_pages:
        url = get_page_url(SEARCH_URL, page)
        print(f"  Página {page}: {url}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            html = r.text
        except requests.RequestException as e:
            print(f"  Error al obtener página {page}: {e}")
            break

        ids = extract_vacant_ids(html, url)
        if not ids:
            print(f"  Página {page}: sin ofertas. Fin de paginación.")
            break

        new_count = 0
        for vid in ids:
            if vid not in seen:
                seen.add(vid)
                result.append(vid)
                new_count += 1

        print(f"  Página {page}: {len(ids)} encontradas, {new_count} nuevas (total: {len(result)}).")
        if new_count == 0:
            break
        page += 1
        time.sleep(0.3)

    return result


# ── Extracción de metadatos desde HTML ────────────────────────────────────────

def extract_offer_metadata_from_html(html: str) -> dict:
    """
    Extrae metadatos desde el HTML de la página de detalle:
    fecha de publicación, salario, nivel de estudios, experiencia, habilidades.
    """
    from datetime import datetime, timedelta, timezone

    metadata: dict = {}
    text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    text_norm = " ".join(text.split())

    # Fecha de publicación
    for pattern, unit in [
        (RE_HACE_DIAS, "days"),
        (RE_HACE_SEMANAS, "weeks"),
        (RE_HACE_MESES, "months"),
    ]:
        m = pattern.search(html) or pattern.search(text_norm)
        if m:
            num = int(m.group(1))
            metadata["publishedAtText"] = m.group(0).strip()
            try:
                if unit == "days":
                    delta = timedelta(days=num)
                elif unit == "weeks":
                    delta = timedelta(weeks=num)
                else:
                    delta = timedelta(days=num * 30)
                metadata["datePosted"] = (
                    datetime.now(timezone.utc) - delta
                ).strftime("%Y-%m-%d")
            except Exception:
                pass
            break

    # Salario
    if RE_SALARIO_A_CONVENIR.search(html) or RE_SALARIO_A_CONVENIR.search(text_norm):
        metadata["toAgree"] = True
    else:
        nums = RE_SALARIO_NUM.findall(html)
        if nums:
            values = []
            for g in nums:
                s = (g[0] + g[1] + g[2]).replace(".", "")
                try:
                    values.append(int(s))
                except ValueError:
                    pass
            if values:
                metadata["minSalary"] = min(values)
                metadata["maxSalary"] = max(values)
                metadata["toAgree"] = False

    # Nivel de estudios
    for pattern in (RE_NIVEL_ESTUDIOS_HTML, RE_NIVEL_EDUCACION_HTML):
        m = pattern.search(html)
        if m:
            metadata["educationLevel"] = " ".join(m.group(1).split()).strip()
            break
    if "educationLevel" not in metadata:
        for pattern in (RE_NIVEL_ESTUDIOS, RE_NIVEL_EDUCACION):
            m = pattern.search(html) or pattern.search(text_norm)
            if m:
                raw = m.group(1)
                raw = re.sub(r"<[^>]+>", " ", raw)
                metadata["educationLevel"] = " ".join(raw.split()).strip()
                break

    # Experiencia
    m = RE_ANOS_EXPERIENCIA.search(html) or RE_ANOS_EXPERIENCIA.search(text_norm)
    if m:
        metadata["experience"] = m.group(0).strip()
    else:
        m = RE_EXPERIENCIA_LABEL.search(html) or RE_EXPERIENCIA_LABEL.search(text_norm)
        if m:
            metadata["experience"] = m.group(1).strip()

    # Habilidades
    soup = BeautifulSoup(html, "html.parser")
    skills: list[str] = []
    for elem in soup.find_all(class_=re.compile(r"skill|tag|chip|badge", re.I)):
        t = (elem.get_text() or "").strip()
        if t and 2 <= len(t) <= 80 and t not in skills:
            skills.append(t)
    if not skills:
        for heading in soup.find_all(["h2", "h3", "h4"]):
            if "Habilidades" not in (heading.get_text() or ""):
                continue
            for sib in heading.find_next_siblings():
                if sib.name in ("ul", "ol", "div"):
                    for li in sib.find_all("li") or sib.find_all("span"):
                        t = (li.get_text() or "").strip()
                        if 2 <= len(t) <= 80 and t != "Habilidades" and t not in skills:
                            skills.append(t)
                break
    if skills:
        metadata["skills"] = skills[:30]

    return metadata


def _merge_metadata(offer: dict, metadata: dict) -> None:
    """Rellena en offer los campos de metadata que no estén ya definidos."""
    if not isinstance(offer, dict) or not metadata:
        return
    for key, value in metadata.items():
        if value is None:
            continue
        current = offer.get(key)
        if key == "educationLevel" and value and isinstance(current, str) and current.strip():
            if len(str(value).strip()) > len(current.strip()):
                offer[key] = value
            continue
        if current is None or current == "" or (isinstance(current, list) and not current):
            offer[key] = value


# ── Conversión de formatos ─────────────────────────────────────────────────────

def _ldjson_to_offer(ld: dict, slug: str) -> dict:
    """Convierte JSON-LD JobPosting al formato estándar."""
    ident = ld.get("identifier", {})
    if isinstance(ident, dict):
        ident = ident.get("value") or ld.get("url", "").split("-")[-1]

    cities: list[str] = []
    job_loc = ld.get("jobLocation")
    if isinstance(job_loc, dict):
        addr = job_loc.get("address")
        if isinstance(addr, dict):
            locality = addr.get("addressLocality")
            if isinstance(locality, list):
                cities = [str(x).strip() for x in locality if x]
            elif locality:
                cities = [str(locality).strip()]

    min_sal, max_sal, to_agree = 0, 0, True
    base_sal = ld.get("baseSalary")
    if isinstance(base_sal, dict):
        val = base_sal.get("value")
        if isinstance(val, dict):
            min_v = val.get("minValue")
            max_v = val.get("maxValue")
            if min_v is not None or max_v is not None:
                try:
                    min_sal = int(float(min_v)) if min_v is not None else 0
                    max_sal = int(float(max_v)) if max_v is not None else min_sal
                    to_agree = False
                except (TypeError, ValueError):
                    pass

    education = ld.get("qualifications") or ld.get("educationRequirements") or ""
    if isinstance(education, dict):
        education = education.get("credentialCategory") or education.get("name") or ""
    education = str(education).strip() if education else ""

    skills_raw = ld.get("skills") or []
    if isinstance(skills_raw, str):
        skills_raw = [s.strip() for s in skills_raw.split(",") if s.strip()]
    elif not isinstance(skills_raw, list):
        skills_raw = []
    skills = [str(s).strip() for s in skills_raw if s]

    experience = ld.get("experienceRequirements") or ""
    if isinstance(experience, dict):
        experience = (
            experience.get("monthsOfExperience")
            or experience.get("duration")
            or experience.get("name")
            or ""
        )
    experience = str(experience).strip() if experience else ""

    return {
        "id": int(ident) if str(ident).isdigit() else 0,
        "title": (ld.get("title") or "").strip(),
        "jobSlug": slug,
        "description": (ld.get("description") or "").strip(),
        "companyName": (
            ld.get("hiringOrganization", {}).get("name", "")
            if isinstance(ld.get("hiringOrganization"), dict)
            else ""
        ),
        "cities": cities,
        "minSalary": min_sal,
        "maxSalary": max_sal,
        "salary": max_sal or min_sal,
        "toAgree": to_agree,
        "datePosted": (ld.get("datePosted") or "").strip() or None,
        "educationLevel": education or None,
        "experience": experience or None,
        "skills": skills if skills else None,
    }


def _normalize_raw_job_block(obj: dict, slug: str) -> dict:
    """Convierte un bloque JSON crudo (jobSlug, description, etc.) al formato estándar."""
    def _num(v):
        if v is None:
            return 0
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return 0

    cities = obj.get("cities") or obj.get("jobLocation") or []
    if isinstance(cities, str):
        cities = [cities]
    elif not isinstance(cities, list):
        cities = []

    min_sal = _num(obj.get("minSalary"))
    max_sal = _num(obj.get("maxSalary")) or _num(obj.get("salary"))
    to_agree = bool(obj.get("toAgree", True) or (not min_sal and not max_sal))

    education = (
        obj.get("educationLevel")
        or obj.get("qualifications")
        or obj.get("educationRequirements")
        or ""
    )
    if isinstance(education, dict):
        education = education.get("name") or education.get("credentialCategory") or ""
    education = str(education).strip() or None

    skills_raw = obj.get("skills") or []
    if isinstance(skills_raw, str):
        skills_raw = [s.strip() for s in skills_raw.split(",") if s.strip()]
    skills = [str(s).strip() for s in skills_raw] if skills_raw else None

    experience = obj.get("experience") or obj.get("experienceRequirements") or ""
    if isinstance(experience, dict):
        experience = (
            experience.get("duration")
            or experience.get("monthsOfExperience")
            or experience.get("name")
            or ""
        )
    experience = str(experience).strip() or None

    return {
        "id": int(obj.get("id") or 0),
        "title": (obj.get("title") or "").strip(),
        "jobSlug": obj.get("jobSlug") or slug,
        "description": (obj.get("description") or "").strip(),
        "companyName": (obj.get("companyName") or obj.get("company") or "").strip(),
        "cities": cities,
        "minSalary": min_sal,
        "maxSalary": max_sal,
        "salary": max_sal or min_sal,
        "toAgree": to_agree,
        "datePosted": (obj.get("datePosted") or obj.get("datePublished") or "").strip() or None,
        "educationLevel": education,
        "experience": experience,
        "skills": skills,
    }


# ── Obtención del detalle de cada oferta ──────────────────────────────────────

def _extract_numeric_id(vacant_id: str) -> str | None:
    """Extrae el ID numérico del slug (ej: 'director-xxx-790953' -> '790953')."""
    if not vacant_id:
        return None
    if vacant_id.isdigit():
        return vacant_id
    m = re.search(r"-(\d+)$", vacant_id.strip())
    return m.group(1) if m else None


def get_offer_from_job_page(slug: str) -> dict | None:
    """
    Obtiene el detalle de la oferta desde la página HTML (co/empleos/slug).
    Busca JSON-LD JobPosting o bloques con jobSlug/description.
    Enriquece con metadatos del HTML.
    """
    url = get_job_page_url(slug)
    try:
        r = requests.get(url, headers=HEADERS, timeout=25)
        if not r.ok:
            return None
        html = r.text
    except requests.RequestException:
        return None

    soup = BeautifulSoup(html, "html.parser")
    offer = None

    # 1) JSON-LD JobPosting
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                offer = _ldjson_to_offer(data, slug)
                break
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        offer = _ldjson_to_offer(item, slug)
                        break
                if offer:
                    break
        except json.JSONDecodeError:
            continue

    # 2) Bloque con jobSlug y description en el HTML
    if not offer:
        match = re.search(r'"jobSlug"\s*:\s*"([^"]+)"[^}]*"id"\s*:\s*(\d+)', html)
        if match:
            try:
                start = html.rfind("{", 0, match.start())
                if start != -1:
                    depth = 0
                    for i in range(start, min(start + 150000, len(html))):
                        if html[i] == "{":
                            depth += 1
                        elif html[i] == "}":
                            depth -= 1
                            if depth == 0:
                                block = html[start: i + 1]
                                obj = json.loads(block)
                                if isinstance(obj, dict) and "jobSlug" in obj and "description" in obj:
                                    offer = _normalize_raw_job_block(obj, slug)
                                    break
            except (json.JSONDecodeError, ValueError):
                pass

    if not offer:
        return None

    # Enriquecer con metadatos del HTML
    meta = extract_offer_metadata_from_html(html)
    _merge_metadata(offer, meta)
    return offer


def get_offer_detail(vacant_id: str) -> dict | None:
    """
    Obtiene el detalle de la oferta:
    1) Desde la página HTML (co/empleos/slug) — datos correctos.
    2) Fallback: API suggested (filtra por ID numérico).
    """
    # 1) Página de la oferta
    job = get_offer_from_job_page(vacant_id)
    if job and isinstance(job, dict):
        return job

    # 2) Fallback: API suggested
    numeric = _extract_numeric_id(vacant_id) or vacant_id
    ids_to_try = [numeric, vacant_id] if numeric != vacant_id else [vacant_id]
    for vid in ids_to_try:
        url = get_api_detail_url(vid)
        try:
            r = requests.get(url, headers=HEADERS_API, timeout=25)
            if not r.ok:
                continue
            raw = r.json()
            if not isinstance(raw, list) or not raw:
                continue
            wanted_id = int(numeric) if numeric.isdigit() else None
            if wanted_id is not None:
                for item in raw:
                    if isinstance(item, dict) and item.get("id") == wanted_id:
                        return item
            return None
        except (json.JSONDecodeError, requests.RequestException, ValueError):
            continue
    return None


# ── Normalización y guardado ───────────────────────────────────────────────────

def normalize_offer(data: dict, requested_vacant_id: str) -> None:
    """Añade/estandariza campos: offer_id, url, source."""
    if not isinstance(data, dict):
        return
    offer_id = data.get("id") or data.get("jobSlug") or requested_vacant_id
    data["offer_id"] = str(offer_id)
    data["vacantId_requested"] = requested_vacant_id
    data["source"] = data.get("source", "magneto365_narino")
    data["location_filter"] = "Nariño"
    data["time_filter"] = "hoy"
    if "url" not in data or not data["url"]:
        slug = data.get("jobSlug") or offer_id
        data["url"] = get_job_page_url(str(slug))


def save_offer(offer_id: str, data: dict) -> str:
    """Guarda el JSON de la oferta en OUTPUT_DIR. Devuelve la ruta del archivo."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_name = re.sub(r"[^\w\-]", "_", str(offer_id)).strip("_") or "offer"
    path = os.path.join(OUTPUT_DIR, f"{safe_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path


# ── Limpieza de ofertas anteriores ────────────────────────────────────────────

def clear_offers() -> int:
    """
    Borra todos los JSON en OUTPUT_DIR (offers/).
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
        print(f"Eliminadas {deleted} ofertas anteriores en {OUTPUT_DIR}/\n")
    return deleted


# ── Punto de entrada ───────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("Scraper Magneto365 - Nariño (filtro: hoy)")
    print(f"URL: {SEARCH_URL}")
    print(f"Salida: {OUTPUT_DIR}/")
    print("=" * 60)

    # 1) Borrar ofertas anteriores
    clear_offers()

    # 2) Obtener todos los vacantId de todas las páginas
    print("\nObteniendo listado de ofertas...")
    vacant_ids = fetch_all_vacant_ids()
    print(f"\nTotal vacantId encontrados: {len(vacant_ids)}\n")

    if not vacant_ids:
        print("No se encontraron ofertas para hoy en Nariño.")
        return

    # 3) Obtener detalle y guardar cada oferta
    saved = 0
    seen_ids: set[str] = set()
    for i, vid in enumerate(vacant_ids, 1):
        short = (vid[:50] + "...") if len(vid) > 50 else vid
        print(f"[{i}/{len(vacant_ids)}] {short}...", end=" ", flush=True)

        data = get_offer_detail(vid)
        if not data or not isinstance(data, dict):
            print("sin datos.")
            continue

        normalize_offer(data, vid)
        oid = data.get("offer_id") or data.get("id") or data.get("jobSlug") or vid

        if str(oid) in seen_ids:
            print("duplicada, omitida.")
            continue
        seen_ids.add(str(oid))

        path = save_offer(str(oid), data)
        saved += 1
        title = data.get("title") or "(sin título)"
        company = data.get("companyName") or ""
        cities = data.get("cities") or []
        loc = ", ".join(cities) if cities else "—"
        print(f"OK  [{title[:40]}] {company[:25]} | {loc}")
        time.sleep(0.3)

    print(f"\n{'=' * 60}")
    print(f"Ofertas guardadas: {saved}  |  Directorio: {OUTPUT_DIR}/")
    print("=" * 60)


if __name__ == "__main__":
    main()
