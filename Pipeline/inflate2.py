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


# ------------------------------------------------------------
# ENTRADAS
# ------------------------------------------------------------

INPUT_LH = SURF_DIR / "lh.smoothwm"
INPUT_RH = SURF_DIR / "rh.smoothwm"


# ------------------------------------------------------------
# SALIDAS
# ------------------------------------------------------------

OUTPUT_LH = SURF_DIR / "lh.inflated"
OUTPUT_RH = SURF_DIR / "rh.inflated"


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


# ==========================================================
# HEMISFERIO IZQUIERDO
# ==========================================================

echo ""
echo "============================================"
echo "INFLATE2 - HEMISFERIO IZQUIERDO"
echo "============================================"

mris_inflate \
"lh.smoothwm" \
"lh.inflated"

if [ $? -ne 0 ]; then
    echo "ERROR en mris_inflate LH."
    exit 1
fi


# ==========================================================
# HEMISFERIO DERECHO
# ==========================================================

echo ""
echo "============================================"
echo "INFLATE2 - HEMISFERIO DERECHO"
echo "============================================"

mris_inflate \
"rh.smoothwm" \
"rh.inflated"

if [ $? -ne 0 ]; then
    echo "ERROR en mris_inflate RH."
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
print("PASO 26 - INFLATE2")
print("============================================")

print()
print("Hemisferio izquierdo:")
print(f"  Entrada : {INPUT_LH}")
print(f"  Salida  : {OUTPUT_LH}")

print()
print("Hemisferio derecho:")
print(f"  Entrada : {INPUT_RH}")
print(f"  Salida  : {OUTPUT_RH}")

print()
print("Ejecutando mris_inflate...")
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
        f"\nmris_inflate terminó con código "
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
print("✓ PASO 26 - INFLATE2 COMPLETADO")
print("============================================")

print(f"LH salida : {OUTPUT_LH}")
print(f"RH salida : {OUTPUT_RH}")