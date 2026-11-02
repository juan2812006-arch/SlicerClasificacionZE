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
SCRIPTS_DIR = SUBJECT_DIR / "scripts"

TRANSFORMS_DIR = MRI_DIR / "transforms"


# ------------------------------------------------------------
# ENTRADAS
# ------------------------------------------------------------

INPUT_WM = MRI_DIR / "wm.mgz"

INPUT_ASEG = MRI_DIR / "aseg.auto_noCCseg.mgz"

INPUT_TALAIRACH = (
    TRANSFORMS_DIR / "talairach.lta"
)


# ------------------------------------------------------------
# SALIDAS
# ------------------------------------------------------------

OUTPUT = MRI_DIR / "filled.mgz"

PONSCC_LOG = SCRIPTS_DIR / "ponscc.cut.log"


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

if not INPUT_WM.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_WM}"
    )

if not INPUT_ASEG.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_ASEG}"
    )

if not INPUT_TALAIRACH.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_TALAIRACH}"
    )


# ============================================================
# PREPARAR DIRECTORIOS
# ============================================================

SCRIPTS_DIR.mkdir(
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

cd "{MRI_DIR}"

mri_fill \
-a "../scripts/ponscc.cut.log" \
-xform "transforms/talairach.lta" \
-segmentation "aseg.auto_noCCseg.mgz" \
"wm.mgz" \
"filled.mgz"
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
print("PASO 17 - FILL")
print("============================================")

print(f"WM            : {INPUT_WM}")
print(f"ASEG          : {INPUT_ASEG}")
print(f"Talairach LTA : {INPUT_TALAIRACH}")
print(f"Salida        : {OUTPUT}")
print(f"Log generado  : {PONSCC_LOG}")

print()
print("Ejecutando mri_fill...")
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
        f"\nmri_fill terminó con código "
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
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ PASO 17 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"Entrada WM    : {INPUT_WM}")
print(f"Entrada ASEG  : {INPUT_ASEG}")
print(f"Entrada LTA   : {INPUT_TALAIRACH}")
print(f"Salida        : {OUTPUT}")

if PONSCC_LOG.exists():
    print(f"Log generado  : {PONSCC_LOG}")
else:
    print(
        "Aviso: no se encontró ponscc.cut.log "
        "después de la ejecución."
    )