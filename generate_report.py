"""
Script para generar informes de ofertas de empleo en formato Markdown.
Lee los archivos JSON de las carpetas Offer de Computrabajo_Narino y Magneto_Narino
y genera un reporte consolidado con fecha y hora de generación.
"""

import json
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── Configuración ────────────────────────────────────────────────────────────

# Zona horaria Colombia: UTC-5
TIMEZONE = timezone(timedelta(hours=-5), name="America/Bogota")

SOURCES = [
    {
        "name": "Computrabajo Nariño",
        "folder": Path("Computrabajo_Narino/Offer"),
        "fields": {
            "title":   "title",
            "company": None,          # Computrabajo no tiene campo empresa
            "salary":  "salary",
            "url":     "url",
        },
    },
    {
        "name": "Magneto Nariño",
        "folder": Path("Magneto_Narino/offers"),
        "fields": {
            "title":   "title",
            "company": "companyName",
            "salary":  None,          # se construye desde minSalary/maxSalary/toAgree
            "url":     "url",
        },
    },
]

REPORTS_DIR = Path("reports")

# ─── Helpers ──────────────────────────────────────────────────────────────────


def load_json_files(folder: Path) -> list[dict]:
    """Carga todos los archivos .json de una carpeta y retorna una lista de dicts."""
    offers = []
    if not folder.exists():
        print(f"  [ADVERTENCIA] La carpeta '{folder}' no existe. Se omite.")
        return offers
    for file in sorted(folder.glob("*.json")):
        try:
            with open(file, encoding="utf-8") as f:
                data = json.load(f)
                offers.append(data)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [ERROR] No se pudo leer '{file.name}': {e}")
    return offers


def get_salary_magneto(offer: dict) -> str:
    """Construye la cadena de salario para ofertas de Magneto."""
    if offer.get("toAgree"):
        return "A convenir"
    min_s = offer.get("minSalary", 0) or 0
    max_s = offer.get("maxSalary", 0) or 0
    salary = offer.get("salary", 0) or 0

    if salary > 0:
        return f"$ {salary:,.0f}".replace(",", ".")
    if min_s > 0 and max_s > 0:
        return f"$ {min_s:,.0f} – $ {max_s:,.0f}".replace(",", ".")
    if min_s > 0:
        return f"$ {min_s:,.0f}".replace(",", ".")
    return "No especificado"


def extract_fields(offer: dict, source_cfg: dict) -> dict:
    """Extrae los campos relevantes de una oferta según la configuración de la fuente."""
    fields = source_cfg["fields"]

    title   = offer.get(fields["title"], "Sin título").strip()
    company = (
        offer.get(fields["company"], "No especificada").strip()
        if fields["company"]
        else "No especificada"
    )
    url = offer.get(fields["url"], "#")

    # Salario
    if fields["salary"]:
        salary = offer.get(fields["salary"]) or "No especificado"
    else:
        salary = get_salary_magneto(offer)

    return {"title": title, "company": company, "salary": salary, "url": url}


def build_markdown(report_dt: datetime, all_sections: list[dict]) -> str:
    """Construye el contenido Markdown del reporte."""
    date_str = report_dt.strftime("%d/%m/%Y")
    time_str = report_dt.strftime("%H:%M:%S")

    lines = [
        "# 📋 Informe de Ofertas de Empleo — Nariño",
        "",
        f"> **Fecha de generación:** {date_str}  ",
        f"> **Hora de generación:** {time_str} (hora Colombia)",
        "",
        "---",
        "",
    ]

    total_offers = sum(len(s["offers"]) for s in all_sections)
    lines += [
        f"**Total de vacantes encontradas:** {total_offers}",
        "",
        "---",
        "",
    ]

    for section in all_sections:
        source_name = section["source"]
        offers      = section["offers"]

        lines += [
            f"## 🔍 {source_name}",
            "",
            f"**Vacantes:** {len(offers)}",
            "",
        ]

        if not offers:
            lines += ["> _No se encontraron ofertas en esta fuente._", ""]
            continue

        # Encabezado de tabla
        lines += [
            "| # | Cargo | Empresa | Salario | Enlace |",
            "|---|-------|---------|---------|--------|",
        ]

        for idx, offer in enumerate(offers, start=1):
            title   = offer["title"].replace("|", "\\|")
            company = offer["company"].replace("|", "\\|")
            salary  = str(offer["salary"]).replace("|", "\\|")
            url     = offer["url"]
            link    = f"[Ver vacante]({url})"

            lines.append(f"| {idx} | {title} | {company} | {salary} | {link} |")

        lines.append("")

    lines += [
        "---",
        "",
        f"_Reporte generado automáticamente el {date_str} a las {time_str}._",
    ]

    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    # Fecha y hora actuales en zona horaria de Colombia
    now = datetime.now(tz=TIMEZONE)
    timestamp = now.strftime("%Y-%m-%d_%H-%M-%S")

    print(f"\n{'='*60}")
    print(f"  Generando informe de ofertas de empleo")
    print(f"  Fecha/Hora: {now.strftime('%d/%m/%Y %H:%M:%S')} (Colombia)")
    print(f"{'='*60}\n")

    all_sections = []

    for source in SOURCES:
        print(f"[FUENTE] {source['name']} ({source['folder']})")
        raw_offers = load_json_files(source["folder"])
        print(f"   -> {len(raw_offers)} oferta(s) encontrada(s)")

        extracted = [extract_fields(o, source) for o in raw_offers]
        all_sections.append({"source": source["name"], "offers": extracted})

    # Crear carpeta de reportes si no existe
    REPORTS_DIR.mkdir(exist_ok=True)

    # Nombre del archivo con timestamp
    report_filename = REPORTS_DIR / f"reporte_ofertas_{timestamp}.md"

    # Construir y guardar el Markdown
    markdown_content = build_markdown(now, all_sections)

    with open(report_filename, "w", encoding="utf-8") as f:
        f.write(markdown_content)

    print(f"\n[OK] Reporte generado exitosamente:")
    print(f"     {report_filename}")
    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    main()
