import os
import subprocess
from pathlib import Path


# ============================================================
# CONFIGURACIÓN RECIBIDA DESDE SLICER
# ============================================================

FREESURFER_HOME = Path(
    os.environ["FREESURFER_HOME"]
)

FS_LICENSE = Path(
    os.environ["FS_LICENSE"]
)

SUBJECTS_DIR = Path(
    os.environ["SUBJECTS_DIR"]
)

SUBJECT_ID = os.environ["SUBJECT_ID"]


# ============================================================
# RUTAS DEL SUJETO
# ============================================================

SUBJECT_DIR = SUBJECTS_DIR / SUBJECT_ID

MRI_DIR = SUBJECT_DIR / "mri"

INPUT = MRI_DIR / "orig.mgz"

TRANSFORMS_DIR = MRI_DIR / "transforms"

TRANSFORMS_DIR.mkdir(
    parents=True,
    exist_ok=True
)

ORIG_NU = MRI_DIR / "orig_nu.mgz"

TALAIRACH_AUTO = TRANSFORMS_DIR / "talairach.auto.xfm"

TALAIRACH = TRANSFORMS_DIR / "talairach.xfm"


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

if not INPUT.exists():
    raise FileNotFoundError(
        f"No se encontró el archivo de entrada:\n{INPUT}"
    )


# ============================================================
# COMANDOS DE FREESURFER
# ============================================================

command = f"""
export FREESURFER_HOME="{FREESURFER_HOME}"
export FS_LICENSE="{FS_LICENSE}"
export SUBJECTS_DIR="{SUBJECTS_DIR}"

source "$FREESURFER_HOME/SetUpFreeSurfer.sh"


echo ""
echo "============================================"
echo "TALAIRACH - PASO 1"
echo "mri_nu_correct.mni"
echo "============================================"


mri_nu_correct.mni \
--n 1 \
--proto-iters 1000 \
--distance 50 \
--no-rescale \
--i "{INPUT}" \
--o "{ORIG_NU}"


if [ $? -ne 0 ]; then
    exit 1
fi


echo ""
echo "============================================"
echo "TALAIRACH - PASO 2"
echo "talairach_avi"
echo "============================================"


talairach_avi \
--i "{ORIG_NU}" \
--xfm "{TALAIRACH_AUTO}"


if [ $? -ne 0 ]; then
    exit 2
fi


echo ""
echo "============================================"
echo "TALAIRACH - PASO 3"
echo "copiar talairach.auto.xfm"
echo "============================================"


cp "{TALAIRACH_AUTO}" "{TALAIRACH}"


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
print("PASO 3 - TALAIRACH")
print("============================================")

print(f"Entrada : {INPUT}")
print(f"Salida  : {TALAIRACH}")

print()
print("Ejecutando proceso Talairach...")
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
        f"\nEl proceso Talairach terminó con código "
        f"{result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDAS
# ============================================================

if not ORIG_NU.exists():

    raise RuntimeError(
        f"\nNo se generó:\n{ORIG_NU}"
    )

if not TALAIRACH_AUTO.exists():

    raise RuntimeError(
        f"\nNo se generó:\n{TALAIRACH_AUTO}"
    )

if not TALAIRACH.exists():

    raise RuntimeError(
        f"\nNo se generó:\n{TALAIRACH}"
    )


# ============================================================
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ PASO 3 COMPLETADO CORRECTAMENTE")
print("============================================")

print(f"Entrada             : {INPUT}")
print(f"Salida intermedia   : {ORIG_NU}")
print(f"Transformación auto : {TALAIRACH_AUTO}")
print(f"Transformación final: {TALAIRACH}")