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

INPUT_LH_ORIG = SURF_DIR / "lh.orig"
INPUT_RH_ORIG = SURF_DIR / "rh.orig"


# ============================================================
# SALIDAS
# ============================================================

OUTPUT_LH_WHITE = SURF_DIR / "lh.white"
OUTPUT_RH_WHITE = SURF_DIR / "rh.white"

OUTPUT_LH_CORTEX = LABEL_DIR / "lh.cortex.label"
OUTPUT_RH_CORTEX = LABEL_DIR / "rh.cortex.label"


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

required_files = [
    INPUT_ASEG,
    INPUT_BRAIN_FINAL,
    INPUT_WM,
    INPUT_FILLED,
    INPUT_LH_ORIG,
    INPUT_RH_ORIG,
]

for file in required_files:
    if not file.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo necesario:\n{file}"
        )
    
    SURF_DIR.mkdir(
    parents=True,
    exist_ok=True
)

LABEL_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# COMANDO FREESURFER
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
echo "WHITE - HEMISFERIO IZQUIERDO"
echo "============================================"

mris_make_surfaces \
-aseg "../mri/aseg.presurf" \
-whiteonly \
-noaparc \
-mgz \
-T1 "../mri/brain.finalsurfs" \
"{SUBJECT_ID}" \
lh

if [ $? -ne 0 ]; then
    echo "ERROR en mris_make_surfaces LH."
    exit 1
fi


# ==========================================================
# HEMISFERIO DERECHO
# ==========================================================

echo ""
echo "============================================"
echo "WHITE - HEMISFERIO DERECHO"
echo "============================================"

mris_make_surfaces \
-aseg "../mri/aseg.presurf" \
-whiteonly \
-noaparc \
-mgz \
-T1 "../mri/brain.finalsurfs" \
"{SUBJECT_ID}" \
rh

if [ $? -ne 0 ]; then
    echo "ERROR en mris_make_surfaces RH."
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
print("PASO 24 - WHITE")
print("============================================")

print("Entradas:")
print(f"  ASEG          : {INPUT_ASEG}")
print(f"  Brain final   : {INPUT_BRAIN_FINAL}")
print(f"  WM            : {INPUT_WM}")
print(f"  Filled        : {INPUT_FILLED}")
print(f"  LH orig       : {INPUT_LH_ORIG}")
print(f"  RH orig       : {INPUT_RH_ORIG}")

print()
print("Salidas principales:")
print(f"  LH white          : {OUTPUT_LH_WHITE}")
print(f"  RH white          : {OUTPUT_RH_WHITE}")
print(f"  LH cortex label   : {OUTPUT_LH_CORTEX}")
print(f"  RH cortex label   : {OUTPUT_RH_CORTEX}")

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
        f"\nmris_make_surfaces terminó con código "
        f"{result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDAS
# ============================================================

required_outputs = [
    OUTPUT_LH_WHITE,
    OUTPUT_RH_WHITE,
    OUTPUT_LH_CORTEX,
    OUTPUT_RH_CORTEX,
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
print("✓ PASO 24 - WHITE COMPLETADO")
print("============================================")

print(f"LH white        : {OUTPUT_LH_WHITE}")
print(f"RH white        : {OUTPUT_RH_WHITE}")
print(f"LH cortex label : {OUTPUT_LH_CORTEX}")
print(f"RH cortex label : {OUTPUT_RH_CORTEX}")