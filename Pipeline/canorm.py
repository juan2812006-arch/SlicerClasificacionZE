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

TRANSFORMS_DIR = MRI_DIR / "transforms"


# Entradas
INPUT_BRAINMASK = MRI_DIR / "brainmask.mgz"
INPUT_NU = MRI_DIR / "nu.mgz"
INPUT_TALAIRACH = TRANSFORMS_DIR / "talairach.lta"


# Atlas
ATLAS = (
    FREESURFER_HOME
    / "average"
    / "RB_all_2016-05-10.vc700.gca"
)


# Salidas
OUTPUT = MRI_DIR / "norm.mgz"

# Este archivo NO debe existir previamente.
# FreeSurfer lo generará durante mri_ca_normalize.
CTRL_PTS = MRI_DIR / "ctrl_pts.mgz"


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

if not INPUT_NU.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_NU}"
    )

if not INPUT_TALAIRACH.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_TALAIRACH}"
    )

if not ATLAS.exists():
    raise FileNotFoundError(
        f"No se encontró el atlas:\n{ATLAS}"
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

mri_ca_normalize \
-c "ctrl_pts.mgz" \
-mask "brainmask.mgz" \
"nu.mgz" \
"{ATLAS}" \
"transforms/talairach.lta" \
"norm.mgz"
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
print("PASO 8 - CANORM")
print("============================================")

print(f"Brainmask : {INPUT_BRAINMASK}")
print(f"NU        : {INPUT_NU}")
print(f"Talairach : {INPUT_TALAIRACH}")
print(f"Atlas     : {ATLAS}")
print(f"Salida    : {OUTPUT}")

print()
print("ctrl_pts.mgz será generado por FreeSurfer.")
print()
print("Ejecutando mri_ca_normalize...")
print()


# ============================================================
# EJECUTAR FREESURFER
# ============================================================

result = subprocess.run(
    ["bash", "-lc", command]
)


# ============================================================
# COMPROBAR EJECUCIÓN
# ============================================================

if result.returncode != 0:
    raise RuntimeError(
        f"\nmri_ca_normalize terminó con código "
        f"{result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDA PRINCIPAL
# ============================================================

if not OUTPUT.exists():
    raise RuntimeError(
        f"\nFreeSurfer terminó, pero no se encontró:\n{OUTPUT}"
    )


# ============================================================
# COMPROBAR CONTROL POINTS
# ============================================================

if CTRL_PTS.exists():
    print()
    print(f"✓ FreeSurfer también generó: {CTRL_PTS}")


# ============================================================
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ PASO 8 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"Entrada  : {INPUT_NU}")
print(f"Salida   : {OUTPUT}")

if CTRL_PTS.exists():
    print(f"Control points generado: {CTRL_PTS}")