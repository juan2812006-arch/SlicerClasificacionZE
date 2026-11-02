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

INPUT_WM_SEG = MRI_DIR / "wm.seg.mgz"

INPUT_BRAIN = MRI_DIR / "brain.mgz"

INPUT_ASEG = MRI_DIR / "aseg.presurf.mgz"


# ------------------------------------------------------------
# SALIDA
# ------------------------------------------------------------

OUTPUT = MRI_DIR / "wm.asegedit.mgz"


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

if not INPUT_WM_SEG.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_WM_SEG}"
    )

if not INPUT_BRAIN.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_BRAIN}"
    )

if not INPUT_ASEG.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_ASEG}"
    )


# ============================================================
# COMANDO FREE SURFER
# ============================================================

command = f"""
export FREESURFER_HOME="{FREESURFER_HOME}"
export FS_LICENSE="{FS_LICENSE}"
export SUBJECTS_DIR="{SUBJECTS_DIR}"

source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

cd "{MRI_DIR}"

mri_edit_wm_with_aseg \
"wm.seg.mgz" \
"brain.mgz" \
"aseg.presurf.mgz" \
"wm.asegedit.mgz"
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
print("PASO 15 - MRI_EDIT_WM_WITH_ASEG")
print("============================================")

print(f"WM segmentation : {INPUT_WM_SEG}")
print(f"Brain           : {INPUT_BRAIN}")
print(f"ASEG presurf    : {INPUT_ASEG}")
print(f"Salida          : {OUTPUT}")

print()
print("Ejecutando mri_edit_wm_with_aseg...")
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
        f"\nmri_edit_wm_with_aseg terminó "
        f"con código {result.returncode}."
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
print("✓ PASO 15 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"Entrada WM segmentation : {INPUT_WM_SEG}")
print(f"Entrada brain           : {INPUT_BRAIN}")
print(f"Entrada aseg.presurf    : {INPUT_ASEG}")
print(f"Salida                  : {OUTPUT}")