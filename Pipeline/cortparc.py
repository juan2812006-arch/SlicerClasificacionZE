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

INPUT_LH_CORTEX = LABEL_DIR / "lh.cortex.label"
INPUT_RH_CORTEX = LABEL_DIR / "rh.cortex.label"

INPUT_LH_SPHERE_REG = SURF_DIR / "lh.sphere.reg"
INPUT_RH_SPHERE_REG = SURF_DIR / "rh.sphere.reg"


# ============================================================
# CLASIFICADORES DESIKAN-KILLIANY
# ============================================================

ATLAS_LH = (
    FREESURFER_HOME
    / "average"
    / "lh.curvature.buckner40.filled.desikan_killiany.2010-03-25.gcs"
)

ATLAS_RH = (
    FREESURFER_HOME
    / "average"
    / "rh.curvature.buckner40.filled.desikan_killiany.2010-03-25.gcs"
)


# ============================================================
# SALIDAS
# ============================================================

OUTPUT_LH = LABEL_DIR / "lh.aparc.annot"
OUTPUT_RH = LABEL_DIR / "rh.aparc.annot"


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
    INPUT_LH_CORTEX,
    INPUT_RH_CORTEX,
    INPUT_LH_SPHERE_REG,
    INPUT_RH_SPHERE_REG,
    ATLAS_LH,
    ATLAS_RH,
]

for file in required_inputs:
    if not file.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo necesario:\n{file}"
        )


# ============================================================
# CREAR DIRECTORIO LABEL
# ============================================================

LABEL_DIR.mkdir(
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

cd "{SUBJECT_DIR}"


# ==========================================================
# HEMISFERIO IZQUIERDO
# ==========================================================

echo ""
echo "============================================"
echo "CORTPARC - HEMISFERIO IZQUIERDO"
echo "============================================"

mris_ca_label \
-l "label/lh.cortex.label" \
-aseg "mri/aseg.presurf.mgz" \
"{SUBJECT_ID}" \
lh \
"lh.sphere.reg" \
"{ATLAS_LH}" \
"label/lh.aparc.annot"

if [ $? -ne 0 ]; then
    echo "ERROR en mris_ca_label LH."
    exit 1
fi


# ==========================================================
# HEMISFERIO DERECHO
# ==========================================================

echo ""
echo "============================================"
echo "CORTPARC - HEMISFERIO DERECHO"
echo "============================================"

mris_ca_label \
-l "label/rh.cortex.label" \
-aseg "mri/aseg.presurf.mgz" \
"{SUBJECT_ID}" \
rh \
"rh.sphere.reg" \
"{ATLAS_RH}" \
"label/rh.aparc.annot"

if [ $? -ne 0 ]; then
    echo "ERROR en mris_ca_label RH."
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
print("PASO - CORTPARC")
print("============================================")

print("Entradas:")
print(f"  ASEG       : {INPUT_ASEG}")
print(f"  LH cortex  : {INPUT_LH_CORTEX}")
print(f"  RH cortex  : {INPUT_RH_CORTEX}")
print(f"  LH sphere  : {INPUT_LH_SPHERE_REG}")
print(f"  RH sphere  : {INPUT_RH_SPHERE_REG}")

print()
print("Clasificadores:")
print(f"  LH : {ATLAS_LH}")
print(f"  RH : {ATLAS_RH}")

print()
print("Salidas:")
print(f"  LH : {OUTPUT_LH}")
print(f"  RH : {OUTPUT_RH}")

print()
print("Ejecutando mris_ca_label...")
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
        f"\nmris_ca_label terminó con código "
        f"{result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDAS
# ============================================================

if not OUTPUT_LH.exists():
    raise RuntimeError(
        f"\nNo se generó:\n{OUTPUT_LH}"
    )

if not OUTPUT_RH.exists():
    raise RuntimeError(
        f"\nNo se generó:\n{OUTPUT_RH}"
    )


# ============================================================
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ CORTPARC COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"LH : {OUTPUT_LH}")
print(f"RH : {OUTPUT_RH}")