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
# ENTRADA PRINCIPAL
# ------------------------------------------------------------

INPUT_FILLED = MRI_DIR / "filled.mgz"


# ------------------------------------------------------------
# INTERMEDIOS
# ------------------------------------------------------------

PRETESS_LH = MRI_DIR / "filled-pretess255.mgz"
PRETESS_RH = MRI_DIR / "filled-pretess127.mgz"


# ------------------------------------------------------------
# SALIDAS
# ------------------------------------------------------------

OUTPUT_LH = SUBJECT_DIR / "surf" / "lh.orig.nofix"
OUTPUT_RH = SUBJECT_DIR / "surf" / "rh.orig.nofix"


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

if not INPUT_FILLED.exists():
    raise FileNotFoundError(
        f"No se encontró:\n{INPUT_FILLED}"
    )


# ============================================================
# CREAR DIRECTORIO SURF
# ============================================================

SURF_DIR = SUBJECT_DIR / "surf"

SURF_DIR.mkdir(
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

cd "{MRI_DIR}"


echo ""
echo "============================================"
echo "TESSSELLATE - HEMISFERIO IZQUIERDO"
echo "============================================"

echo "Paso 1: mri_pretess"

mri_pretess \
"filled.mgz" \
255 \
"norm.mgz" \
"filled-pretess255.mgz"

if [ $? -ne 0 ]; then
    echo "ERROR en mri_pretess para hemisferio izquierdo."
    exit 1
fi


echo ""
echo "Paso 2: mri_tessellate"

mri_tessellate \
"filled-pretess255.mgz" \
255 \
"../surf/lh.orig.nofix"

if [ $? -ne 0 ]; then
    echo "ERROR en mri_tessellate para hemisferio izquierdo."
    exit 2
fi


echo ""
echo "============================================"
echo "TESSSELLATE - HEMISFERIO DERECHO"
echo "============================================"

echo "Paso 3: mri_pretess"

mri_pretess \
"filled.mgz" \
127 \
"norm.mgz" \
"filled-pretess127.mgz"

if [ $? -ne 0 ]; then
    echo "ERROR en mri_pretess para hemisferio derecho."
    exit 3
fi


echo ""
echo "Paso 4: mri_tessellate"

mri_tessellate \
"filled-pretess127.mgz" \
127 \
"../surf/rh.orig.nofix"

if [ $? -ne 0 ]; then
    echo "ERROR en mri_tessellate para hemisferio derecho."
    exit 4
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
print("PASO 18 - TESSELLATE")
print("============================================")

print(f"Entrada : {INPUT_FILLED}")

print()
print("Izquierdo:")
print(f"  Intermedio : {PRETESS_LH}")
print(f"  Salida     : {OUTPUT_LH}")

print()
print("Derecho:")
print(f"  Intermedio : {PRETESS_RH}")
print(f"  Salida     : {OUTPUT_RH}")

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
        f"\nEl proceso tessellate terminó con código "
        f"{result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDAS
# ============================================================

if not PRETESS_LH.exists():
    raise RuntimeError(
        f"\nNo se generó:\n{PRETESS_LH}"
    )

if not PRETESS_RH.exists():
    raise RuntimeError(
        f"\nNo se generó:\n{PRETESS_RH}"
    )

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
print("✓ PASO 18 COMPLETADO CORRECTAMENTE")
print("============================================")

print()
print("Hemmisferio izquierdo:")
print(f"  {PRETESS_LH}")
print(f"  {OUTPUT_LH}")

print()
print("Hemisferio derecho:")
print(f"  {PRETESS_RH}")
print(f"  {OUTPUT_RH}")