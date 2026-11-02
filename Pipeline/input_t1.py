import subprocess
from pathlib import Path
import os

# ============================================================
# CONFIGURACIÓN RECIBIDA DESDE LA EXTENSIÓN
# ============================================================

FREESURFER_HOME = Path(os.environ["FREESURFER_HOME"])
FS_LICENSE = Path(os.environ["FS_LICENSE"])
SUBJECTS_DIR = Path(os.environ["SUBJECTS_DIR"])
SUBJECT_ID = os.environ["SUBJECT_ID"]
T1 = Path(os.environ["T1"])


# ============================================================
# COMPROBACIONES
# ============================================================

if not FREESURFER_HOME.exists():
    raise FileNotFoundError(
        f"No se encontró FreeSurfer:\n{FREESURFER_HOME}"
    )

if not T1.exists():
    raise FileNotFoundError(
        f"No se encontró la imagen T1:\n{T1}"
    )

if not FS_LICENSE.exists():
    raise FileNotFoundError(
        f"No se encontró la licencia:\n{FS_LICENSE}"
    )


# ============================================================
# DIRECTORIOS
# ============================================================

SUBJECT_DIR = SUBJECTS_DIR / SUBJECT_ID
ORIG_DIR = SUBJECT_DIR / "mri" / "orig"

ORIG_DIR.mkdir(
    parents=True,
    exist_ok=True
)

OUTPUT = ORIG_DIR / "001.mgz"


# ============================================================
# COMANDO COMPLETO
# ============================================================

command = f"""
export FREESURFER_HOME="{FREESURFER_HOME}"
export FS_LICENSE="{FS_LICENSE}"
export SUBJECTS_DIR="{SUBJECTS_DIR}"

source "$FREESURFER_HOME/SetUpFreeSurfer.sh"

mri_convert "{T1}" "{OUTPUT}"
"""


# ============================================================
# INFORMACIÓN
# ============================================================

print()
print("============================================")
print("CONFIGURACIÓN")
print("============================================")
print(f"FREESURFER_HOME : {FREESURFER_HOME}")
print(f"FS_LICENSE      : {FS_LICENSE}")
print(f"SUBJECTS_DIR    : {SUBJECTS_DIR}")
print(f"SUBJECT_ID      : {SUBJECT_ID}")

print()
print("============================================")
print("PASO 1 - INPUT T1")
print("============================================")

print(f"Entrada : {T1}")
print(f"Salida  : {OUTPUT}")

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
# COMPROBAR ERROR
# ============================================================

if result.returncode != 0:

    raise RuntimeError(
        f"\nmri_convert terminó con código "
        f"{result.returncode}"
    )


# ============================================================
# COMPROBAR SALIDA
# ============================================================

if not OUTPUT.exists():

    raise RuntimeError(
        f"\nNo se generó el archivo esperado:\n{OUTPUT}"
    )


# ============================================================
# RESULTADO
# ============================================================

print()
print("============================================")
print("✓ PASO 1 COMPLETADO")
print("============================================")

print(f"Entrada : {T1}")
print(f"Salida  : {OUTPUT}")