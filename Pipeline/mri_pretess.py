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

INPUT_WM_ASEGEDIT = MRI_DIR / "wm.asegedit.mgz"
INPUT_NORM = MRI_DIR / "norm.mgz"


# ------------------------------------------------------------
# SALIDA
# ------------------------------------------------------------

OUTPUT = MRI_DIR / "wm.mgz"


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

if not INPUT_WM_ASEGEDIT.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_WM_ASEGEDIT}"
    )

if not INPUT_NORM.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_NORM}"
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

mri_pretess \
"wm.asegedit.mgz" \
"wm" \
"norm.mgz" \
"wm.mgz"
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
print("PASO 16 - MRI_PRETESS")
print("============================================")

print(f"WM asegedit : {INPUT_WM_ASEGEDIT}")
print(f"Norm        : {INPUT_NORM}")
print(f"Salida      : {OUTPUT}")

print()
print("Ejecutando mri_pretess...")
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
        f"\nmri_pretess terminó con código "
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
print("✓ PASO 16 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"Entrada WM asegedit : {INPUT_WM_ASEGEDIT}")
print(f"Entrada norm       : {INPUT_NORM}")
print(f"Salida             : {OUTPUT}")