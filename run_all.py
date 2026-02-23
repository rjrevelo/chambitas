"""
Orquestador principal — Tu Chambita
====================================
Ejecuta en secuencia:
  1. Scraper de Computrabajo Nariño
  2. Scraper de Magneto Nariño
  3. Generador de reporte Markdown (generate_report.py)

Uso:
    python run_all.py

El reporte .md queda en la carpeta reports/ con timestamp en el nombre.
"""

import subprocess
import sys
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ─── Configuración ────────────────────────────────────────────────────────────

# Zona horaria Colombia: UTC-5
TIMEZONE = timezone(timedelta(hours=-5), name="America/Bogota")

# Directorio raíz del proyecto (donde vive este script)
ROOT_DIR = Path(__file__).resolve().parent

# Intérprete Python actual (el mismo que ejecuta este script)
PYTHON = sys.executable

# Pasos a ejecutar en orden: (nombre_legible, script, directorio_de_trabajo)
STEPS = [
    (
        "Scraper Computrabajo Nariño",
        ROOT_DIR / "Computrabajo_Narino" / "scraper.py",
        ROOT_DIR / "Computrabajo_Narino",
    ),
    (
        "Scraper Magneto Nariño",
        ROOT_DIR / "Magneto_Narino" / "scraper.py",
        ROOT_DIR / "Magneto_Narino",
    ),
    (
        "Generador de reporte Markdown",
        ROOT_DIR / "generate_report.py",
        ROOT_DIR,
    ),
]

# ─── Helpers ──────────────────────────────────────────────────────────────────

SEP = "=" * 65


def log(msg: str) -> None:
    now = datetime.now(tz=TIMEZONE).strftime("%H:%M:%S")
    print(f"[{now}] {msg}", flush=True)


def run_step(name: str, script: Path, cwd: Path) -> bool:
    """
    Ejecuta un script Python como subproceso.
    Retorna True si terminó con código 0, False en caso contrario.
    """
    log(f"▶  Iniciando: {name}")
    log(f"   Script : {script}")
    log(f"   CWD    : {cwd}")
    print()

    result = subprocess.run(
        [PYTHON, str(script)],
        cwd=str(cwd),
        # Heredar stdout/stderr para ver la salida en tiempo real
        stdout=None,
        stderr=None,
    )

    print()
    if result.returncode == 0:
        log(f"✔  Completado: {name}")
    else:
        log(f"✘  ERROR en '{name}' (código de salida: {result.returncode})")

    return result.returncode == 0


# ─── Main ─────────────────────────────────────────────────────────────────────


def main() -> int:
    start = datetime.now(tz=TIMEZONE)

    print()
    print(SEP)
    print("  TU CHAMBITA — Ejecución automática de scrapers + reporte")
    print(f"  Inicio: {start.strftime('%d/%m/%Y %H:%M:%S')} (hora Colombia)")
    print(SEP)
    print()

    failed_steps: list[str] = []

    for name, script, cwd in STEPS:
        print(SEP)
        ok = run_step(name, script, cwd)
        if not ok:
            failed_steps.append(name)
        print()

    # ── Resumen final ──────────────────────────────────────────────────────────
    end = datetime.now(tz=TIMEZONE)
    elapsed = (end - start).total_seconds()

    print(SEP)
    print("  RESUMEN")
    print(SEP)
    print(f"  Fin     : {end.strftime('%d/%m/%Y %H:%M:%S')} (hora Colombia)")
    print(f"  Duración: {elapsed:.1f} segundos")
    print()

    if failed_steps:
        print(f"  ✘ Pasos con error ({len(failed_steps)}):")
        for s in failed_steps:
            print(f"      - {s}")
        print()
        print("  El reporte puede estar incompleto. Revisa los errores arriba.")
        exit_code = 1
    else:
        print("  ✔ Todos los pasos completados exitosamente.")
        # Mostrar el último reporte generado
        reports_dir = ROOT_DIR / "reports"
        if reports_dir.exists():
            reports = sorted(reports_dir.glob("reporte_ofertas_*.md"), reverse=True)
            if reports:
                print(f"\n  📄 Reporte generado: {reports[0].name}")
        exit_code = 0

    print(SEP)
    print()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
