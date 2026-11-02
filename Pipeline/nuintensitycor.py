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
MRI_DIR = SUBJECT_DIR / "mri"

INPUT = MRI_DIR / "orig.mgz"

TALAIRACH = MRI_DIR / "transforms" / "talairach.xfm"

OUTPUT = MRI_DIR / "nu.mgz"


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

if not TALAIRACH.exists():
    raise FileNotFoundError(
        f"No se encontró la transformación Talairach:\n{TALAIRACH}"
    )


# ============================================================
# COMANDO DE FREESURFER
# ============================================================

command = f"""
export FREESURFER_HOME="{FREESURFER_HOME}"
export FS_LICENSE="{FS_LICENSE}"
export SUBJECTS_DIR="{SUBJECTS_DIR}"

source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

mri_nu_correct.mni \
--i "{INPUT}" \
--o "{OUTPUT}" \
--uchar "{TALAIRACH}" \
--n 2
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
print(f"SUBJECT_ID      : {SUBJECT_ID}")

print()
print("============================================")
print("PASO 4 - NUINTENSITYCOR")
print("============================================")

print(f"Entrada T1     : {INPUT}")
print(f"Talairach      : {TALAIRACH}")
print(f"Salida         : {OUTPUT}")

print()
print("Ejecutando mri_nu_correct.mni...")
print()


# ============================================================
# EJECUTAR
# ============================================================

result = subprocess.run(
    ["bash", "-lc", command]
)


# ============================================================
# COMPROBAR EJECUCIÓN
# ============================================================

if result.returncode != 0:
    raise RuntimeError(
        f"\nmri_nu_correct.mni terminó con código "
        f"{result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDA
# ============================================================

if not OUTPUT.exists():
    raise RuntimeError(
        f"\nFreeSurfer terminó, pero no se encontró:\n{OUTPUT}"
    )


# ============================================================
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ PASO 4 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"Entrada : {INPUT}")
print(f"Salida  : {OUTPUT}")