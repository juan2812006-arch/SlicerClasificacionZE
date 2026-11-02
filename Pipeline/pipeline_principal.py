import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime


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

T1 = Path(
    os.environ["T1"]
)


# ============================================================
# DIRECTORIO DEL PIPELINE
# ============================================================

CODIGO_DIR = Path(__file__).resolve().parent


# ============================================================
# DIRECTORIO DEL SUJETO
# ============================================================

SUBJECT_DIR = SUBJECTS_DIR / SUBJECT_ID


# ============================================================
# ARCHIVOS DE ESTADO
# ============================================================

STATUS_FILE = Path(
    os.environ.get(
        "PIPELINE_STATUS_FILE",
        SUBJECT_DIR / ".pipeline_status.txt"
    )
)

CURRENT_FILE = Path(
    os.environ.get(
        "PIPELINE_CURRENT_FILE",
        SUBJECT_DIR / ".pipeline_current.txt"
    )
)

LOG_FILE = Path(
    os.environ.get(
        "PIPELINE_LOG_FILE",
        SUBJECT_DIR / "pipeline.log"
    )
)


# ============================================================
# ORDEN DE EJECUCIÓN
# ============================================================

ORDEN = [
    "input_t1.py",
    "conform.py",
    "talairach.py",
    "nuintensitycor.py",
    "normalization.py",
    "skullstrip.py",
    "gcareg.py",
    "canorm.py",
    "careg.py",
    "calabel.py",
    "aseg_presurf.py",
    "normalization2.py",
    "maskbfs.py",
    "segmentation.py",
    "mri_edit_wm_with_aseg.py",
    "mri_pretess.py",
    "fill.py",
    "mri_tesselate.py",
    "mris_extract_main_component.py",
    "smooth1.py",
    "inflate1.py",
    "qsphere.py",
    "fix.py",
    "white.py",
    "smooth2.py",
    "inflate2.py",
    "sphere2.py",
    "surfreg.py",
    "cortparc.py",
    "cortparc2.py",
    "pial.py",
]


# ============================================================
# CREAR DIRECTORIO DEL SUJETO
# ============================================================

SUBJECT_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# FUNCIONES DE ESTADO
# ============================================================

def escribir_estado(numero):
    STATUS_FILE.write_text(
        str(numero),
        encoding="utf-8"
    )


def escribir_script_actual(nombre):
    CURRENT_FILE.write_text(
        nombre,
        encoding="utf-8"
    )


def escribir_log(mensaje):

    print(mensaje, flush=True)

    with LOG_FILE.open(
        "a",
        encoding="utf-8"
    ) as f:

        f.write(
            mensaje + "\n"
        )


# ============================================================
# INICIO
# ============================================================

escribir_estado(0)
escribir_script_actual("Preparando pipeline")

if LOG_FILE.exists():
    LOG_FILE.unlink()


escribir_log("=" * 70)
escribir_log("PIPELINE FREESURFER — RECONSTRUCCIÓN CORTICAL HASTA PIAL")
escribir_log("=" * 70)

escribir_log("")
escribir_log("CONFIGURACIÓN:")
escribir_log(f"FreeSurfer:         {FREESURFER_HOME}")
escribir_log(f"Licencia:           {FS_LICENSE}")
escribir_log(f"T1:                 {T1}")
escribir_log(f"Subjects directory: {SUBJECTS_DIR}")
escribir_log(f"Subject ID:         {SUBJECT_ID}")
escribir_log(f"Subject directory:  {SUBJECT_DIR}")
escribir_log(f"Pipeline:           {CODIGO_DIR}")


# ============================================================
# VALIDACIONES
# ============================================================

escribir_log("")
escribir_log("=" * 70)
escribir_log("VALIDANDO CONFIGURACIÓN")
escribir_log("=" * 70)


if not FREESURFER_HOME.exists():

    escribir_log(
        f"ERROR: No se encontró FreeSurfer:\n{FREESURFER_HOME}"
    )

    escribir_estado(-1)
    escribir_script_actual("ERROR")
    sys.exit(1)


if not FS_LICENSE.exists():

    escribir_log(
        f"ERROR: No se encontró la licencia:\n{FS_LICENSE}"
    )

    escribir_estado(-1)
    escribir_script_actual("ERROR")
    sys.exit(1)


if not T1.exists():

    escribir_log(
        f"ERROR: No se encontró la imagen T1:\n{T1}"
    )

    escribir_estado(-1)
    escribir_script_actual("ERROR")
    sys.exit(1)


if not CODIGO_DIR.exists():

    escribir_log(
        f"ERROR: No se encontró el pipeline:\n{CODIGO_DIR}"
    )

    escribir_estado(-1)
    escribir_script_actual("ERROR")
    sys.exit(1)


escribir_log("✓ FreeSurfer encontrado")
escribir_log("✓ Licencia encontrada")
escribir_log("✓ MRI T1 encontrada")
escribir_log("✓ Directorio del pipeline encontrado")


# ============================================================
# COMPROBAR SCRIPTS
# ============================================================

escribir_log("")
escribir_log("=" * 70)
escribir_log("COMPROBANDO SCRIPTS")
escribir_log("=" * 70)


faltantes = []


for numero, nombre in enumerate(
    ORDEN,
    start=1
):

    archivo = CODIGO_DIR / nombre

    if archivo.exists():

        escribir_log(
            f"✓ {numero:02d}  {nombre}"
        )

    else:

        escribir_log(
            f"✗ {numero:02d}  {nombre}"
        )

        faltantes.append(
            nombre
        )


if faltantes:

    escribir_log("")
    escribir_log("=" * 70)
    escribir_log("NO SE PUEDE EJECUTAR EL PIPELINE")
    escribir_log("=" * 70)

    for nombre in faltantes:

        escribir_log(
            f"Falta: {nombre}"
        )

    escribir_estado(-1)
    escribir_script_actual("ERROR")

    sys.exit(1)


escribir_log("")
escribir_log("=" * 70)
escribir_log("TODOS LOS SCRIPTS ESTÁN PRESENTES")
escribir_log("=" * 70)


# ============================================================
# EJECUTAR SCRIPT
# ============================================================

def ejecutar_script(
    numero,
    total,
    nombre
):

    archivo = CODIGO_DIR / nombre

    escribir_estado(numero)
    escribir_script_actual(nombre)

    escribir_log("")
    escribir_log("=" * 70)
    escribir_log(
        f"PASO {numero}/{total}"
    )
    escribir_log(
        f"Ejecutando: {nombre}"
    )
    escribir_log("=" * 70)

    inicio = datetime.now()

    resultado = subprocess.run(
        [
            sys.executable,
            "-u",
            str(archivo)
        ],
        cwd=str(CODIGO_DIR),
        env=os.environ.copy()
    )

    fin = datetime.now()
    duracion = fin - inicio

    if resultado.returncode != 0:

        escribir_estado(-1)
        escribir_script_actual(
            f"ERROR: {nombre}"
        )

        escribir_log("")
        escribir_log("=" * 70)
        escribir_log("ERROR EN EL PIPELINE")
        escribir_log("=" * 70)

        escribir_log(
            f"Script que falló: {nombre}"
        )

        escribir_log(
            f"Código de salida: {resultado.returncode}"
        )

        escribir_log(
            f"Duración: {duracion}"
        )

        escribir_log(
            "Los pasos posteriores NO se ejecutaron."
        )

        sys.exit(
            resultado.returncode
        )

    escribir_log("")
    escribir_log("-" * 70)
    escribir_log(
        f"✓ {nombre} terminado correctamente"
    )
    escribir_log(
        f"Duración: {duracion}"
    )
    escribir_log("-" * 70)


# ============================================================
# EJECUCIÓN DEL PIPELINE
# ============================================================

inicio_total = datetime.now()

total = len(ORDEN)


for numero, nombre in enumerate(
    ORDEN,
    start=1
):

    ejecutar_script(
        numero,
        total,
        nombre
    )


# ============================================================
# VERIFICACIÓN FINAL DE LAS SUPERFICIES PIAL
# ============================================================

LH_PIAL = SUBJECT_DIR / "surf" / "lh.pial"
RH_PIAL = SUBJECT_DIR / "surf" / "rh.pial"

fin_total = datetime.now()

duracion_total = (
    fin_total -
    inicio_total
)


escribir_log("")
escribir_log("=" * 70)
escribir_log("VERIFICACIÓN FINAL — SUPERFICIES PIAL")
escribir_log("=" * 70)

escribir_log(
    f"Superficie pial izquierda: {LH_PIAL}"
)

escribir_log(
    f"Superficie pial derecha:   {RH_PIAL}"
)


if LH_PIAL.exists() and RH_PIAL.exists():

    escribir_estado(total)
    escribir_script_actual("COMPLETADO")

    escribir_log("")
    escribir_log("✓ SUPERFICIES PIAL ENCONTRADAS")
    escribir_log("")
    escribir_log("=" * 70)
    escribir_log("PIPELINE COMPLETADO CORRECTAMENTE")
    escribir_log("=" * 70)

    escribir_log(
        f"Número de scripts ejecutados: {total}"
    )

    escribir_log(
        f"Duración total: {duracion_total}"
    )

    escribir_log(
        "Punto de finalización: generación de superficies pial"
    )

else:

    escribir_estado(-1)
    escribir_script_actual(
        "ERROR: No se encontraron las superficies pial"
    )

    escribir_log("")
    escribir_log("=" * 70)
    escribir_log("ERROR: SUPERFICIES PIAL NO ENCONTRADAS")
    escribir_log("=" * 70)

    if not LH_PIAL.exists():
        escribir_log(
            f"✗ No se encontró: {LH_PIAL}"
        )

    if not RH_PIAL.exists():
        escribir_log(
            f"✗ No se encontró: {RH_PIAL}"
        )

    escribir_log(
        "El pipeline no se considera completado."
    )

    sys.exit(1)