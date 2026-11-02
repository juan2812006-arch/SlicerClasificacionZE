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
SURF_DIR = SUBJECT_DIR / "surf"

INPUT_LH = SURF_DIR / "lh.orig.nofix"
INPUT_RH = SURF_DIR / "rh.orig.nofix"


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

if not INPUT_LH.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_LH}"
    )

if not INPUT_RH.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_RH}"
    )


# ============================================================
# COMANDO DE FREESURFER
# ============================================================

command = f"""
export FREESURFER_HOME="{FREESURFER_HOME}"
export FS_LICENSE="{FS_LICENSE}"
export SUBJECTS_DIR="{SUBJECTS_DIR}"

source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

cd "{SURF_DIR}"

echo ""
echo "============================================"
echo "HEMISFERIO IZQUIERDO"
echo "============================================"

mris_extract_main_component \
"lh.orig.nofix" \
"lh.orig.nofix"

if [ $? -ne 0 ]; then
    echo "ERROR en lh.orig.nofix"
    exit 1
fi


echo ""
echo "============================================"
echo "HEMISFERIO DERECHO"
echo "============================================"

mris_extract_main_component \
"rh.orig.nofix" \
"rh.orig.nofix"

if [ $? -ne 0 ]; then
    echo "ERROR en rh.orig.nofix"
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
print("PASO 19 - MRIS_EXTRACT_MAIN_COMPONENT")
print("============================================")

print(f"Entrada LH : {INPUT_LH}")
print(f"Entrada RH : {INPUT_RH}")

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
        f"\nmris_extract_main_component terminó "
        f"con código {result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDAS
# ============================================================

if not INPUT_LH.exists():
    raise RuntimeError(
        f"No se encontró después del proceso:\n{INPUT_LH}"
    )

if not INPUT_RH.exists():
    raise RuntimeError(
        f"No se encontró después del proceso:\n{INPUT_RH}"
    )


# ============================================================
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ PASO 19 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"LH: {INPUT_LH}")
print(f"RH: {INPUT_RH}")