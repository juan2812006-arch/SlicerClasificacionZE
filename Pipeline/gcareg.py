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

INPUT_BRAINMASK = MRI_DIR / "brainmask.mgz"
INPUT_NU = MRI_DIR / "nu.mgz"

ATLAS = (
    FREESURFER_HOME
    / "average"
    / "RB_all_2016-05-10.vc700.gca"
)

OUTPUT = (
    TRANSFORMS_DIR
    / "talairach.lta"
)


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

if not ATLAS.exists():
    raise FileNotFoundError(
        f"No se encontró el atlas:\n{ATLAS}"
    )


# ============================================================
# CREAR DIRECTORIO DE TRANSFORMACIONES
# ============================================================

TRANSFORMS_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# COMANDO DE FREESURFER
# ============================================================

command = f"""
export FREESURFER_HOME="{FREESURFER_HOME}"
export FS_LICENSE="{FS_LICENSE}"
export SUBJECTS_DIR="{SUBJECTS_DIR}"

source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

mri_em_register \
-uns 3 \
-mask "{INPUT_BRAINMASK}" \
"{INPUT_NU}" \
"{ATLAS}" \
"{OUTPUT}"
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
print("PASO 7 - GCAREg")
print("============================================")

print(f"Brainmask : {INPUT_BRAINMASK}")
print(f"NU        : {INPUT_NU}")
print(f"Atlas     : {ATLAS}")
print(f"Salida    : {OUTPUT}")

print()
print("Ejecutando mri_em_register...")
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
        f"\nmri_em_register terminó con código "
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
print("✓ PASO 7 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"Entrada brainmask : {INPUT_BRAINMASK}")
print(f"Entrada nu        : {INPUT_NU}")
print(f"Salida            : {OUTPUT}")