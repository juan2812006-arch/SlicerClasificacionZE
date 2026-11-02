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


# Entradas
INPUT_BRAIN = MRI_DIR / "brain.mgz"
INPUT_BRAINMASK = MRI_DIR / "brainmask.mgz"


# Salida
OUTPUT = MRI_DIR / "brain.finalsurfs.mgz"


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

if not INPUT_BRAIN.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_BRAIN}"
    )

if not INPUT_BRAINMASK.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_BRAINMASK}"
    )


# ============================================================
# COMANDO DE FREESURFER
# ============================================================

command = f"""
export FREESURFER_HOME="{FREESURFER_HOME}"
export FS_LICENSE="{FS_LICENSE}"
export SUBJECTS_DIR="{SUBJECTS_DIR}"

source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

cd "{MRI_DIR}"

mri_mask \
-T 5 \
"brain.mgz" \
"brainmask.mgz" \
"brain.finalsurfs.mgz"
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
print("PASO 13 - MASKBFS")
print("============================================")

print(f"Brain      : {INPUT_BRAIN}")
print(f"Brainmask  : {INPUT_BRAINMASK}")
print(f"Salida     : {OUTPUT}")

print()
print("Ejecutando mri_mask...")
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
        f"\nmri_mask terminó con código "
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
print("✓ PASO 13 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"Entrada brain     : {INPUT_BRAIN}")
print(f"Entrada brainmask : {INPUT_BRAINMASK}")
print(f"Salida            : {OUTPUT}")