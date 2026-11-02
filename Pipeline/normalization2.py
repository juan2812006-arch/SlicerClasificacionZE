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


# ------------------------------------------------------------
# ENTRADAS
# ------------------------------------------------------------

INPUT_BRAINMASK = MRI_DIR / "brainmask.mgz"
INPUT_NORM = MRI_DIR / "norm.mgz"
INPUT_ASEG = MRI_DIR / "aseg.presurf.mgz"


# ------------------------------------------------------------
# SALIDA
# ------------------------------------------------------------

OUTPUT = MRI_DIR / "brain.mgz"


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

if not INPUT_BRAINMASK.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_BRAINMASK}"
    )

if not INPUT_NORM.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_NORM}"
    )

if not INPUT_ASEG.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_ASEG}"
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

mri_normalize \
-mprage \
-aseg "aseg.presurf.mgz" \
-mask "brainmask.mgz" \
"norm.mgz" \
"brain.mgz"
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
print("PASO 12 - NORMALIZATION2")
print("============================================")

print(f"Brainmask : {INPUT_BRAINMASK}")
print(f"Norm      : {INPUT_NORM}")
print(f"Aseg      : {INPUT_ASEG}")
print(f"Salida    : {OUTPUT}")

print()
print("Ejecutando mri_normalize...")
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
        f"\nmri_normalize terminó con código "
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
print("✓ PASO 12 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"Entrada brainmask : {INPUT_BRAINMASK}")
print(f"Entrada norm      : {INPUT_NORM}")
print(f"Entrada aseg      : {INPUT_ASEG}")
print(f"Salida            : {OUTPUT}")