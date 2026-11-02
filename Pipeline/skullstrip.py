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

INPUT_NU = MRI_DIR / "nu.mgz"

TALAIRACH_WITH_SKULL = (
    TRANSFORMS_DIR / "talairach_with_skull.lta"
)

BRAINMASK_AUTO = MRI_DIR / "brainmask.auto.mgz"

BRAINMASK = MRI_DIR / "brainmask.mgz"

ATLAS = (
    FREESURFER_HOME
    / "average"
    / "RB_all_withskull_2016-05-10.vc700.gca"
)

T1 = MRI_DIR / "T1.mgz"


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

if not INPUT_NU.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_NU}"
    )

if not T1.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{T1}"
    )

if not ATLAS.exists():
    raise FileNotFoundError(
        f"No se encontró el atlas:\n{ATLAS}"
    )


# ============================================================
# COMANDOS FREE SURFER
# ============================================================

command = f"""
export FREESURFER_HOME="{FREESURFER_HOME}"
export FS_LICENSE="{FS_LICENSE}"
export SUBJECTS_DIR="{SUBJECTS_DIR}"

source "$FREESURFER_HOME/SetUpFreeSurfer.sh"


echo ""
echo "============================================"
echo "SKULLSTRIP - PASO 1"
echo "mri_em_register"
echo "============================================"

mri_em_register \
-skull \
"{INPUT_NU}" \
"{ATLAS}" \
"{TALAIRACH_WITH_SKULL}"

if [ $? -ne 0 ]; then
    exit 1
fi


echo ""
echo "============================================"
echo "SKULLSTRIP - PASO 2"
echo "mri_watershed"
echo "============================================"

mri_watershed \
-T1 \
-brain_atlas \
"{ATLAS}" \
"{TALAIRACH_WITH_SKULL}" \
"{T1}" \
"{BRAINMASK_AUTO}"

if [ $? -ne 0 ]; then
    exit 2
fi


echo ""
echo "============================================"
echo "SKULLSTRIP - PASO 3"
echo "copiar brainmask.auto.mgz"
echo "============================================"

cp "{BRAINMASK_AUTO}" "{BRAINMASK}"

if [ $? -ne 0 ]; then
    exit 3
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
print("PASO 6 - SKULLSTRIP")
print("============================================")

print(f"Entrada nu.mgz         : {INPUT_NU}")
print(f"Entrada T1.mgz         : {T1}")
print(f"Atlas                   : {ATLAS}")
print(f"Transformación salida   : {TALAIRACH_WITH_SKULL}")
print(f"Brainmask automática    : {BRAINMASK_AUTO}")
print(f"Brainmask final         : {BRAINMASK}")

print()
print("Ejecutando FreeSurfer...")
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
        f"\nEl proceso skullstrip terminó "
        f"con código {result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDAS
# ============================================================

if not TALAIRACH_WITH_SKULL.exists():
    raise RuntimeError(
        f"No se generó:\n{TALAIRACH_WITH_SKULL}"
    )

if not BRAINMASK_AUTO.exists():
    raise RuntimeError(
        f"No se generó:\n{BRAINMASK_AUTO}"
    )

if not BRAINMASK.exists():
    raise RuntimeError(
        f"No se generó:\n{BRAINMASK}"
    )


# ============================================================
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ PASO 6 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"Transformación : {TALAIRACH_WITH_SKULL}")
print(f"Brainmask auto : {BRAINMASK_AUTO}")
print(f"Brainmask      : {BRAINMASK}")