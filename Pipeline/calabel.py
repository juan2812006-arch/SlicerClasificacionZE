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


# ------------------------------------------------------------
# ENTRADAS
# ------------------------------------------------------------

INPUT_NORM = MRI_DIR / "norm.mgz"

INPUT_M3Z = TRANSFORMS_DIR / "talairach.m3z"


# ------------------------------------------------------------
# ATLAS
# ------------------------------------------------------------

ATLAS = (
    FREESURFER_HOME
    / "average"
    / "RB_all_2016-05-10.vc700.gca"
)


# ------------------------------------------------------------
# SALIDAS
# ------------------------------------------------------------

OUTPUT_CALABEL = (
    MRI_DIR / "aseg.auto_noCCseg.mgz"
)

OUTPUT_CC = (
    MRI_DIR / "aseg.auto.mgz"
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

if not INPUT_NORM.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_NORM}"
    )

if not INPUT_M3Z.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_M3Z}"
    )

if not ATLAS.exists():
    raise FileNotFoundError(
        f"No se encontró el atlas:\n{ATLAS}"
    )


# ============================================================
# COMANDOS DE FREESURFER
# ============================================================

command = f"""
export FREESURFER_HOME="{FREESURFER_HOME}"
export FS_LICENSE="{FS_LICENSE}"
export SUBJECTS_DIR="{SUBJECTS_DIR}"

source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

cd "{MRI_DIR}"


echo ""
echo "============================================"
echo "PASO 10A - CALABEL"
echo "============================================"

mri_ca_label \
-relabel_unlikely 9 .3 \
-prior 0.5 \
-align \
"norm.mgz" \
"transforms/talairach.m3z" \
"{ATLAS}" \
"aseg.auto_noCCseg.mgz"


if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: mri_ca_label falló."
    exit 1
fi


echo ""
echo "============================================"
echo "CALABEL COMPLETADO"
echo "============================================"

echo "Generado:"
echo "aseg.auto_noCCseg.mgz"


echo ""
echo "============================================"
echo "PASO 10B - MRI_CC"
echo "============================================"

mri_cc \
-lta "transforms/cc_up.lta" \
-aseg "aseg.auto_noCCseg.mgz" \
-o "aseg.auto.mgz" \
"{SUBJECT_ID}"


if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: mri_cc falló."
    exit 2
fi


echo ""
echo "============================================"
echo "MRI_CC COMPLETADO"
echo "============================================"

echo "Generado:"
echo "aseg.auto.mgz"
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
print("PASO 10 - CALABEL + MRI_CC")
print("============================================")

print(f"Norm              : {INPUT_NORM}")
print(f"Talairach M3Z     : {INPUT_M3Z}")
print(f"Atlas             : {ATLAS}")
print(f"Salida calabel    : {OUTPUT_CALABEL}")
print(f"Salida mri_cc     : {OUTPUT_CC}")

print()
print("Ejecutando procesos de FreeSurfer...")
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
        f"\nEl proceso terminó con código "
        f"{result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDAS
# ============================================================

if not OUTPUT_CALABEL.exists():
    raise RuntimeError(
        f"\nNo se generó:\n{OUTPUT_CALABEL}"
    )

if not OUTPUT_CC.exists():
    raise RuntimeError(
        f"\nNo se generó:\n{OUTPUT_CC}"
    )


# ============================================================
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ PASO 10 COMPLETADO CORRECTAMENTE")
print("============================================")

print()
print("Salidas:")

print(f"1. {OUTPUT_CALABEL}")
print(f"2. {OUTPUT_CC}")