import subprocess
from pathlib import Path
import os


FREESURFER_HOME = Path(os.environ["FREESURFER_HOME"])
FS_LICENSE = Path(os.environ["FS_LICENSE"])
SUBJECTS_DIR = Path(os.environ["SUBJECTS_DIR"])
SUBJECT_ID = os.environ["SUBJECT_ID"]


# ============================================================
# RUTAS
# ============================================================

SUBJECT_DIR = SUBJECTS_DIR / SUBJECT_ID

INPUT = SUBJECT_DIR / "mri" / "orig" / "001.mgz"

OUTPUT = SUBJECT_DIR / "mri" / "orig.mgz"


# ============================================================
# COMPROBACIONES
# ============================================================

if not FREESURFER_HOME.exists():
    raise FileNotFoundError(
        f"No se encontró FreeSurfer:\n{FREESURFER_HOME}"
    )

if not FS_LICENSE.exists():
    raise FileNotFoundError(
        f"No se encontró la licencia:\n{FS_LICENSE}"
    )

if not INPUT.exists():
    raise FileNotFoundError(
        f"No se encontró el archivo de entrada:\n{INPUT}"
    )


# ============================================================
# COMANDO FREE SURFER
# ============================================================

command = f"""
export FREESURFER_HOME="{FREESURFER_HOME}"
export FS_LICENSE="{FS_LICENSE}"
export SUBJECTS_DIR="{SUBJECTS_DIR}"

source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

mri_convert "{INPUT}" "{OUTPUT}" --conform
"""


# ============================================================
# INFORMACIÓN
# ============================================================

print()
print("============================================")
print("CONFIGURACIÓN DE FREESURFER")
print("============================================")

print(f"FREESURFER_HOME : {FREESURFER_HOME}")
print(f"FS_LICENSE      : {FS_LICENSE}")
print(f"SUBJECTS_DIR    : {SUBJECTS_DIR}")

print()
print("============================================")
print("PASO 2 - CONFORM")
print("============================================")

print(f"Entrada : {INPUT}")
print(f"Salida  : {OUTPUT}")

print()
print("Ejecutando mri_convert --conform...")
print()


# ============================================================
# EJECUTAR FREE SURFER
# ============================================================

result = subprocess.run(
    ["bash", "-lc", command]
)


# ============================================================
# COMPROBAR EJECUCIÓN
# ============================================================

if result.returncode != 0:

    raise RuntimeError(
        f"\nmri_convert --conform terminó "
        f"con código {result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDA
# ============================================================

if not OUTPUT.exists():

    raise RuntimeError(
        f"\nFreeSurfer terminó, pero no se encontró "
        f"el archivo esperado:\n{OUTPUT}"
    )


# ============================================================
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ PASO 2 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"Entrada : {INPUT}")
print(f"Salida  : {OUTPUT}")