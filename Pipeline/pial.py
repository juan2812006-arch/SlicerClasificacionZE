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

SURF_DIR = SUBJECT_DIR / "surf"

LABEL_DIR = SUBJECT_DIR / "label"


# ============================================================
# ENTRADAS
# ============================================================

INPUT_ASEG = MRI_DIR / "aseg.presurf.mgz"

INPUT_BRAIN_FINAL = MRI_DIR / "brain.finalsurfs.mgz"

INPUT_WM = MRI_DIR / "wm.mgz"

INPUT_FILLED = MRI_DIR / "filled.mgz"

INPUT_LH_WHITE = SURF_DIR / "lh.white"

INPUT_RH_WHITE = SURF_DIR / "rh.white"

INPUT_LH_APARC = LABEL_DIR / "lh.aparc.annot"

INPUT_RH_APARC = LABEL_DIR / "rh.aparc.annot"


# ============================================================
# SALIDAS PRINCIPALES
# ============================================================

OUTPUT_LH_PIAL = SURF_DIR / "lh.pial"

OUTPUT_RH_PIAL = SURF_DIR / "rh.pial"


# ============================================================
# SALIDAS AUXILIARES
# ============================================================

OUTPUT_LH_CURV_PIAL = SURF_DIR / "lh.curv.pial"
OUTPUT_RH_CURV_PIAL = SURF_DIR / "rh.curv.pial"

OUTPUT_LH_AREA_PIAL = SURF_DIR / "lh.area.pial"
OUTPUT_RH_AREA_PIAL = SURF_DIR / "rh.area.pial"

OUTPUT_LH_THICKNESS = SURF_DIR / "lh.thickness"
OUTPUT_RH_THICKNESS = SURF_DIR / "rh.thickness"


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


required_inputs = [
    INPUT_ASEG,
    INPUT_BRAIN_FINAL,
    INPUT_WM,
    INPUT_FILLED,
    INPUT_LH_WHITE,
    INPUT_RH_WHITE,
    INPUT_LH_APARC,
    INPUT_RH_APARC,
]

for file in required_inputs:

    if not file.exists():

        raise FileNotFoundError(
            f"No se encontró el archivo necesario:\n{file}"
        )


# ============================================================
# CREAR DIRECTORIOS
# ============================================================

SURF_DIR.mkdir(
    parents=True,
    exist_ok=True
)

LABEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# COMANDO COMPLETO DE FREESURFER
# ============================================================

command = f"""
export FREESURFER_HOME="{FREESURFER_HOME}"
export FS_LICENSE="{FS_LICENSE}"
export SUBJECTS_DIR="{SUBJECTS_DIR}"

source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

cd "{SURF_DIR}"


# ==========================================================
# HEMISFERIO IZQUIERDO
# ==========================================================

echo ""
echo "============================================"
echo "PIAL - HEMISFERIO IZQUIERDO"
echo "============================================"

mris_make_surfaces \
-orig_white "lh.white" \
-orig_pial "lh.white" \
-aseg "../mri/aseg.presurf" \
-nowhite \
-mgz \
-T1 "../mri/brain.finalsurfs" \
"{SUBJECT_ID}" \
lh

if [ $? -ne 0 ]; then
    echo "ERROR en mris_make_surfaces PIAL LH."
    exit 1
fi


# ==========================================================
# HEMISFERIO DERECHO
# ==========================================================

echo ""
echo "============================================"
echo "PIAL - HEMISFERIO DERECHO"
echo "============================================"

mris_make_surfaces \
-orig_white "rh.white" \
-orig_pial "rh.white" \
-aseg "../mri/aseg.presurf" \
-nowhite \
-mgz \
-T1 "../mri/brain.finalsurfs" \
"{SUBJECT_ID}" \
rh

if [ $? -ne 0 ]; then
    echo "ERROR en mris_make_surfaces PIAL RH."
    exit 2
fi
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
print("PASO 30 - PIAL")
print("============================================")

print()
print("Entradas:")
print(f"  ASEG             : {INPUT_ASEG}")
print(f"  Brain final      : {INPUT_BRAIN_FINAL}")
print(f"  WM               : {INPUT_WM}")
print(f"  Filled           : {INPUT_FILLED}")
print(f"  LH white         : {INPUT_LH_WHITE}")
print(f"  RH white         : {INPUT_RH_WHITE}")
print(f"  LH aparc         : {INPUT_LH_APARC}")
print(f"  RH aparc         : {INPUT_RH_APARC}")

print()
print("Salidas principales:")
print(f"  LH pial          : {OUTPUT_LH_PIAL}")
print(f"  RH pial          : {OUTPUT_RH_PIAL}")

print()
print("Ejecutando mris_make_surfaces...")
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
        f"\nmris_make_surfaces (pial) terminó "
        f"con código {result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDAS PRINCIPALES
# ============================================================

required_outputs = [
    OUTPUT_LH_PIAL,
    OUTPUT_RH_PIAL,
]

for file in required_outputs:

    if not file.exists():

        raise RuntimeError(
            f"\nNo se generó el archivo esperado:\n{file}"
        )


# ============================================================
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ PASO 30 - PIAL COMPLETADO")
print("============================================")

print(f"LH pial : {OUTPUT_LH_PIAL}")
print(f"RH pial : {OUTPUT_RH_PIAL}")