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


# ============================================================
# ARCHIVOS DE ENTRADA
# ============================================================

LH_ORIG_NOFIX = SURF_DIR / "lh.orig.nofix"
RH_ORIG_NOFIX = SURF_DIR / "rh.orig.nofix"

LH_INFLATED_NOFIX = SURF_DIR / "lh.inflated.nofix"
RH_INFLATED_NOFIX = SURF_DIR / "rh.inflated.nofix"

LH_QSPHERE_NOFIX = SURF_DIR / "lh.qsphere.nofix"
RH_QSPHERE_NOFIX = SURF_DIR / "rh.qsphere.nofix"


# ============================================================
# ARCHIVOS DE SALIDA / TRABAJO
# ============================================================

LH_ORIG = SURF_DIR / "lh.orig"
RH_ORIG = SURF_DIR / "rh.orig"

LH_INFLATED = SURF_DIR / "lh.inflated"
RH_INFLATED = SURF_DIR / "rh.inflated"


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
    LH_ORIG_NOFIX,
    RH_ORIG_NOFIX,
    LH_INFLATED_NOFIX,
    RH_INFLATED_NOFIX,
    LH_QSPHERE_NOFIX,
    RH_QSPHERE_NOFIX,
]

for file in required_files:
    if not file.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo necesario:\n{file}"
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
echo "FIX - HEMISFERIO IZQUIERDO"
echo "============================================"

echo ""
echo "1. Copiando lh.orig.nofix -> lh.orig"

cp "lh.orig.nofix" "lh.orig"

if [ $? -ne 0 ]; then
    echo "ERROR copiando lh.orig.nofix"
    exit 1
fi


echo ""
echo "2. Copiando lh.inflated.nofix -> lh.inflated"

cp "lh.inflated.nofix" "lh.inflated"

if [ $? -ne 0 ]; then
    echo "ERROR copiando lh.inflated.nofix"
    exit 2
fi


echo ""
echo "3. Ejecutando mris_fix_topology"

mris_fix_topology \
-mgz \
-sphere "qsphere.nofix" \
-ga "{SUBJECT_ID}" \
lh

if [ $? -ne 0 ]; then
    echo "ERROR en mris_fix_topology LH"
    exit 3
fi


echo ""
echo "4. Ejecutando mris_euler_number"

mris_euler_number "lh.orig"

if [ $? -ne 0 ]; then
    echo "ERROR en mris_euler_number LH"
    exit 4
fi


echo ""
echo "5. Ejecutando mris_remove_intersection"

mris_remove_intersection \
"lh.orig" \
"lh.orig"

if [ $? -ne 0 ]; then
    echo "ERROR en mris_remove_intersection LH"
    exit 5
fi


echo ""
echo "6. Eliminando lh.inflated"

rm "lh.inflated"

if [ $? -ne 0 ]; then
    echo "ERROR eliminando lh.inflated"
    exit 6
fi


# ==========================================================
# HEMISFERIO DERECHO
# ==========================================================

echo ""
echo "============================================"
echo "FIX - HEMISFERIO DERECHO"
echo "============================================"

echo ""
echo "1. Copiando rh.orig.nofix -> rh.orig"

cp "rh.orig.nofix" "rh.orig"

if [ $? -ne 0 ]; then
    echo "ERROR copiando rh.orig.nofix"
    exit 7
fi


echo ""
echo "2. Copiando rh.inflated.nofix -> rh.inflated"

cp "rh.inflated.nofix" "rh.inflated"

if [ $? -ne 0 ]; then
    echo "ERROR copiando rh.inflated.nofix"
    exit 8
fi


echo ""
echo "3. Ejecutando mris_fix_topology"

mris_fix_topology \
-mgz \
-sphere "qsphere.nofix" \
-ga "{SUBJECT_ID}" \
rh

if [ $? -ne 0 ]; then
    echo "ERROR en mris_fix_topology RH"
    exit 9
fi


echo ""
echo "4. Ejecutando mris_euler_number"

mris_euler_number "rh.orig"

if [ $? -ne 0 ]; then
    echo "ERROR en mris_euler_number RH"
    exit 10
fi


echo ""
echo "5. Ejecutando mris_remove_intersection"

mris_remove_intersection \
"rh.orig" \
"rh.orig"

if [ $? -ne 0 ]; then
    echo "ERROR en mris_remove_intersection RH"
    exit 11
fi


echo ""
echo "6. Eliminando rh.inflated"

rm "rh.inflated"

if [ $? -ne 0 ]; then
    echo "ERROR eliminando rh.inflated"
    exit 12
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
print("PASO 23 - FIX")
print("============================================")

print("Entradas:")
print(f"  LH orig.nofix      : {LH_ORIG_NOFIX}")
print(f"  RH orig.nofix      : {RH_ORIG_NOFIX}")
print(f"  LH inflated.nofix  : {LH_INFLATED_NOFIX}")
print(f"  RH inflated.nofix  : {RH_INFLATED_NOFIX}")
print(f"  LH qsphere.nofix   : {LH_QSPHERE_NOFIX}")
print(f"  RH qsphere.nofix   : {RH_QSPHERE_NOFIX}")

print()
print("Salidas principales:")
print(f"  LH orig             : {LH_ORIG}")
print(f"  RH orig             : {RH_ORIG}")

print()
print("Ejecutando bloque completo de FIX...")
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
        f"\nEl proceso fix terminó con código "
        f"{result.returncode}."
    )


# ============================================================
# COMPROBAR SALIDAS PRINCIPALES
# ============================================================

if not LH_ORIG.exists():
    raise RuntimeError(
        f"\nNo se generó:\n{LH_ORIG}"
    )

if not RH_ORIG.exists():
    raise RuntimeError(
        f"\nNo se generó:\n{RH_ORIG}"
    )


# ============================================================
# COMPROBAR QUE inflated FUE ELIMINADO
# ============================================================

if LH_INFLATED.exists():
    raise RuntimeError(
        f"\nNo se eliminó correctamente:\n{LH_INFLATED}"
    )

if RH_INFLATED.exists():
    raise RuntimeError(
        f"\nNo se eliminó correctamente:\n{RH_INFLATED}"
    )


# ============================================================
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ PASO 23 - FIX COMPLETADO CORRECTAMENTE")
print("============================================")

print()
print(f"LH orig : {LH_ORIG}")
print(f"RH orig : {RH_ORIG}")

print()
print("Los archivos lh.inflated y rh.inflated")
print("fueron eliminados según el flujo de recon-all.")