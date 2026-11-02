import html
import logging
import os
import re
import signal
import subprocess
import sys
import shutil
import tempfile
import time
from pathlib import Path

import ctk
import qt
import slicer

from slicer.ScriptedLoadableModule import (
    ScriptedLoadableModule,
    ScriptedLoadableModuleWidget,
    ScriptedLoadableModuleLogic,
    ScriptedLoadableModuleTest,
)


# Debe coincidir con len(ORDEN) en Pipeline/pipeline_principal.py
# (lo comprueba VisualizacionTest).
TOTAL_PASOS = 31

# Lo que se muestra al usuario por cada script de ORDEN (mismas claves; lo
# comprueba VisualizacionTest).
DESCRIPCION_PASOS = {
    "input_t1.py": "Importación de la imagen T1",
    "conform.py": "Conformado de la imagen (1 mm isotrópico)",
    "talairach.py": "Registro al espacio Talairach",
    "nuintensitycor.py": "Corrección de inhomogeneidad de intensidad",
    "normalization.py": "Normalización de intensidad",
    "skullstrip.py": "Eliminación del cráneo",
    "gcareg.py": "Registro lineal al atlas",
    "canorm.py": "Normalización con el atlas",
    "careg.py": "Registro no lineal al atlas",
    "calabel.py": "Segmentación subcortical",
    "aseg_presurf.py": "Segmentación previa a las superficies",
    "normalization2.py": "Segunda normalización de intensidad",
    "maskbfs.py": "Máscara del cerebro normalizado",
    "segmentation.py": "Segmentación de la materia blanca",
    "mri_edit_wm_with_aseg.py": "Corrección de la materia blanca",
    "mri_pretess.py": "Preparación del teselado",
    "fill.py": "Separación de hemisferios",
    "mri_tesselate.py": "Teselado de la superficie",
    "mris_extract_main_component.py": "Limpieza de la superficie",
    "smooth1.py": "Primer suavizado de la superficie",
    "inflate1.py": "Primer inflado de la superficie",
    "qsphere.py": "Proyección esférica inicial",
    "fix.py": "Corrección topológica (paso largo)",
    "white.py": "Superficie de la materia blanca",
    "smooth2.py": "Segundo suavizado de la superficie",
    "inflate2.py": "Segundo inflado de la superficie",
    "sphere2.py": "Proyección esférica",
    "surfreg.py": "Registro esférico al atlas (paso largo)",
    "cortparc.py": "Parcelación cortical (Desikan)",
    "cortparc2.py": "Parcelación cortical (Destrieux)",
    "pial.py": "Superficie pial",
}

# Salida de FreeSurfer que necesitan la inferencia y la visualización, relativa
# a la carpeta del paciente.
ARCHIVOS_FREESURFER = [
    "surf/lh.pial",
    "surf/rh.pial",
    "label/lh.aparc.a2009s.annot",
    "label/rh.aparc.a2009s.annot",
]

# El ID da nombre a una carpeta y se pasa a FreeSurfer.
ID_VALIDO = re.compile(r"^[A-Za-z0-9._-]+$")

# Los scripts del pipeline insertan las rutas entre comillas dobles en un
# comando de bash: estos caracteres lo romperían o inyectarían órdenes.
CARACTERES_PELIGROSOS = re.compile(r'["$`\\]')

# Paciente de demostración (fsaverage + Resources/Demo).
ID_DEMO = "fsaverage_demo"

RECURSOS_DIR = Path(__file__).resolve().parent / "Resources"

# Prefijo de las preferencias guardadas con QSettings.
CLAVE_AJUSTES = "Visualizacion/"


def detectarFreeSurfer():
    """Instalación de FreeSurfer en $FREESURFER_HOME o en un lugar habitual (la versión más reciente), o ''."""

    candidatos = []

    if os.environ.get("FREESURFER_HOME"):
        candidatos.append(Path(os.environ["FREESURFER_HOME"]))

    def version(ruta):
        return [int(parte) if parte.isdigit() else -1 for parte in ruta.name.split(".")]

    for base in (Path("/Applications/freesurfer"), Path("/usr/local/freesurfer"), Path("/opt/freesurfer")):
        if base.is_dir():
            candidatos += sorted((p for p in base.iterdir() if p.is_dir()), key=version, reverse=True)
            candidatos.append(base)

    for candidato in candidatos:
        if (candidato / "SetUpFreeSurfer.sh").exists():
            return str(candidato)

    return ""


def nombreRegion(region):
    """'Pole_temporal L' -> 'Pole_temporal (hemisferio izquierdo)'."""

    nombre, _, hemisferio = str(region).strip().rpartition(" ")

    lado = {"L": "izquierdo", "R": "derecho"}.get(hemisferio)

    if not nombre or lado is None:
        return str(region)

    return f"{nombre} (hemisferio {lado})"


def formatoDuracion(segundos):
    """3725 -> '1 h 02 min 05 s'."""

    segundos = int(segundos)
    horas, resto = divmod(segundos, 3600)
    minutos, segundos = divmod(resto, 60)

    if horas:
        return f"{horas} h {minutos:02d} min {segundos:02d} s"

    return f"{minutos} min {segundos:02d} s"


def carpetaExtension(nombre):
    """
    Carpeta de la extensión que usa el módulo en tiempo de ejecución
    (Pipeline, Inferencia o VisualizacionML).

    En el árbol de fuentes está junto a Visualizacion/; en la extensión
    construida o instalada, en VisualizacionLib/ junto a Visualizacion.py
    (ver Visualizacion/CMakeLists.txt).
    """

    moduloDir = Path(__file__).resolve().parent

    empaquetada = moduloDir / "VisualizacionLib" / nombre

    if empaquetada.exists():
        return empaquetada

    return moduloDir.parent / nombre


#
# Visualizacion
#

class Visualizacion(ScriptedLoadableModule):

    def __init__(self, parent):

        ScriptedLoadableModule.__init__(self, parent)

        self.parent.title = "Clasificación de ZE"
        self.parent.categories = ["Epilepsy"]
        self.parent.dependencies = []
        self.parent.contributors = [
            "Juan Andrés Martínez Castellanos (Pontificia Universidad Javeriana)",
            "Ana Rebeca Torres Vargas (Pontificia Universidad Javeriana)",
        ]

        self.parent.helpText = """
Procesa la resonancia T1 de un paciente con FreeSurfer, estima con un
modelo de Machine Learning las regiones corticales con posible
epileptogenicidad (atlas Destrieux) y las muestra en 3D junto a los
electrodos EEG de superficie y SEEG.
<br><br>
<b>Uso rápido:</b> complete los pasos 1 a 3 del panel y pulse
<i>Procesar MRI nuevo</i> (varias horas) o, si el paciente ya fue
procesado, <i>Visualizar paciente ya procesado</i> (minutos). Para
probar la extensión sin datos propios, pulse
<i>Cargar datos de demostración</i>.
<br><br>
El botón <i>Manual de uso</i> del panel abre la guía completa:
formatos de los archivos, interpretación de los resultados y
solución de problemas.
<br><br>
<b>Aviso:</b> herramienta de apoyo a la investigación; sus resultados
no sustituyen la evaluación clínica.
"""

        self.parent.acknowledgementText = """
Desarrollado como trabajo de grado en la Pontificia Universidad
Javeriana. Usa FreeSurfer (https://surfer.nmr.mgh.harvard.edu) y
el atlas de Destrieux.
<br><br>
Licencia PolyForm Noncommercial 1.0.0: uso, estudio, modificación y
redistribución libres con fines no comerciales.
"""


#
# Widget
#

class VisualizacionWidget(ScriptedLoadableModuleWidget):

    def __init__(self, parent=None):

        ScriptedLoadableModuleWidget.__init__(
            self,
            parent
        )

        self.pipelineDir = carpetaExtension(
            "Pipeline"
        )

        # Modelo de SOZ y su adaptador (Inferencia/inferencia_ml.py).
        self.inferenciaDir = carpetaExtension(
            "Inferencia"
        )

        self.process = None

        # stdout del pipeline (pipeline.log); se cierra al terminar.
        self.pipelineLogFile = None

        self.timer = None

        self.totalSteps = TOTAL_PASOS

        self.currentStep = 0

        self.currentSubjectDir = None

        # Visualizador cortical ML creado al terminar el pipeline.
        self.mlVisualizer = None

        # Visualizador de EEG de superficie (discos 10-20) sobre la corteza.
        self.eegVisualizer = None

        # Visualizador de electrodos SEEG (barras) sobre la corteza.
        self.seegVisualizer = None

        # Control de lectura incremental de pipeline.log.
        self._logFileOffset = 0
        self._maxLogChars = 120000
        self._maxLogChunk = 32768

        # Instalación de FreeSurfer de la última ejecución (la visualización
        # ML la recibe; en «Visualizar paciente ya procesado» puede faltar).
        self.freesurferPath = None

        # Momento de inicio del pipeline (time.monotonic), para mostrar el
        # tiempo transcurrido.
        self._inicioPipeline = None

        # Ventana del manual de uso (no modal, se reutiliza).
        self._manualDialog = None

        # El pipeline y sus scripts existen (lo comprueba checkPipelineFiles).
        self._pipelineDisponible = False

    # ========================================================
    # SETUP
    # ========================================================

    def setup(self):

        ScriptedLoadableModuleWidget.setup(self)

        # ----------------------------------------------------
        # ENCABEZADO
        # ----------------------------------------------------

        titleLabel = qt.QLabel(
            "Clasificación de ZE"
        )

        titleLabel.setStyleSheet(
            "font-size: 22px; "
            "font-weight: bold; "
            "margin-bottom: 4px;"
        )

        self.layout.addWidget(titleLabel)

        descriptionLabel = qt.QLabel(
            "Procesa la resonancia T1 de un paciente con FreeSurfer, estima "
            "con un modelo de Machine Learning las regiones corticales con "
            "posible epileptogenicidad (atlas Destrieux) y las muestra en 3D "
            "junto a los electrodos EEG y SEEG.\n"
            "Complete los pasos en orden. Pase el cursor sobre cada campo "
            "para ver qué se espera en él."
        )

        descriptionLabel.wordWrap = True

        self.layout.addWidget(
            descriptionLabel
        )

        ayudaLayout = qt.QHBoxLayout()

        self.manualButton = qt.QPushButton(
            "Manual de uso"
        )

        self.manualButton.toolTip = (
            "Abre el manual: preparación de los archivos, pasos, "
            "interpretación de los resultados y solución de problemas."
        )

        self.manualButton.clicked.connect(
            self.onAbrirManual
        )

        ayudaLayout.addWidget(
            self.manualButton
        )

        self.demoButton = qt.QPushButton(
            "Cargar datos de demostración"
        )

        self.demoButton.toolTip = (
            "Prepara un paciente de prueba con el cerebro de referencia "
            "«fsaverage» de FreeSurfer y datos clínicos SINTÉTICOS, para "
            "probar la extensión en unos minutos sin procesar un MRI.\n"
            "Requiere haber indicado FreeSurfer en el paso 1."
        )

        self.demoButton.clicked.connect(
            self.onCargarDemo
        )

        ayudaLayout.addWidget(
            self.demoButton
        )

        self.layout.addLayout(
            ayudaLayout
        )

        # ====================================================
        # 1. FREESURFER
        # ====================================================

        self.freesurferSection = ctk.ctkCollapsibleButton()
        self.freesurferSection.text = "1. FreeSurfer"
        self.layout.addWidget(self.freesurferSection)

        freesurferForm = qt.QFormLayout(
            self.freesurferSection
        )

        self.freesurferPathEdit = self._crearCampoRuta(
            freesurferForm,
            "Instalación:",
            "Carpeta de instalación de FreeSurfer",
            "Carpeta que contiene SetUpFreeSurfer.sh y license.txt "
            "(por ejemplo /Applications/freesurfer/8.2.0).",
            lambda: self._buscarCarpeta(
                self.freesurferPathEdit,
                "Seleccione la instalación de FreeSurfer"
            )
        )

        self._agregarNota(
            freesurferForm,
            "Necesaria para procesar un MRI nuevo y para los datos de "
            "demostración. Se recuerda entre sesiones."
        )

        # ====================================================
        # 2. PACIENTE
        # ====================================================

        self.pacienteSection = ctk.ctkCollapsibleButton()
        self.pacienteSection.text = "2. Paciente"
        self.layout.addWidget(self.pacienteSection)

        pacienteForm = qt.QFormLayout(
            self.pacienteSection
        )

        self.subjectIdEdit = qt.QLineEdit()

        self.subjectIdEdit.placeholderText = (
            "Ejemplo: paciente01"
        )

        self.subjectIdEdit.toolTip = (
            "Identificador del paciente. Da nombre a su carpeta de "
            "resultados. Solo letras, números, '-', '_' y '.', sin "
            "espacios ni tildes."
        )

        self.subjectIdEdit.textChanged.connect(
            self.actualizarEstadoFormulario
        )

        pacienteForm.addRow(
            "ID del paciente *:",
            self.subjectIdEdit
        )

        self.subjectsDirEdit = self._crearCampoRuta(
            pacienteForm,
            "Carpeta de resultados *:",
            "Carpeta donde se guardan los pacientes",
            "Carpeta común de resultados (SUBJECTS_DIR de FreeSurfer). Cada "
            "paciente se guarda en una subcarpeta con su ID. Se recuerda "
            "entre sesiones.",
            lambda: self._buscarCarpeta(
                self.subjectsDirEdit,
                "Seleccione la carpeta de resultados"
            )
        )

        self.subjectDirLabel = self._agregarNota(
            pacienteForm,
            ""
        )

        self.t1PathEdit = self._crearCampoRuta(
            pacienteForm,
            "Imagen T1:",
            "Resonancia T1 (.nii, .nii.gz o .mgz)",
            "Resonancia magnética T1 del paciente. Solo es necesaria para "
            "«Procesar MRI nuevo».",
            lambda: self._buscarArchivo(
                self.t1PathEdit,
                "Seleccione la imagen MRI T1",
                "Imágenes T1 (*.nii *.nii.gz *.mgz);;Todos los archivos (*)"
            )
        )

        # ====================================================
        # 3. DATOS CLÍNICOS
        # ====================================================

        self.clinicosSection = ctk.ctkCollapsibleButton()
        self.clinicosSection.text = "3. Datos clínicos"
        self.layout.addWidget(self.clinicosSection)

        clinicosForm = qt.QFormLayout(
            self.clinicosSection
        )

        self.featuresFilePathEdit = self._crearCampoRuta(
            clinicosForm,
            "Características *:",
            "CSV con las características sEEG por región",
            "CSV con una fila por región Destrieux (148) y las columnas "
            "region_destrieux, seeg_EI_valor, seeg_HFO_valor, "
            "seeg_ER_valor y seeg_SE_valor. Separador ';' con decimal ',' "
            "o ',' con decimal '.'. Las regiones no implantadas van vacías.",
            lambda: self._buscarArchivo(
                self.featuresFilePathEdit,
                "Seleccione el archivo de características del paciente",
                "CSV (*.csv);;Todos los archivos (*)"
            )
        )

        self.eegFilePathEdit = self._crearCampoRuta(
            clinicosForm,
            "EEG de superficie:",
            "Opcional: CSV con los electrodos 10-20",
            "Opcional. CSV con un electrodo por fila en la primera columna "
            "(Fp1, Cz, O2...), con o sin encabezado 'electrode'. Si se deja "
            "vacío no se dibujan electrodos EEG.",
            lambda: self._buscarArchivo(
                self.eegFilePathEdit,
                "Seleccione el archivo de electrodos EEG",
                "CSV (*.csv);;Todos los archivos (*)"
            )
        )

        self.seegFilePathEdit = self._crearCampoRuta(
            clinicosForm,
            "SEEG:",
            "Opcional: TSV con los canales SEEG",
            "Opcional. TSV con las columnas Channel (canales bipolares como "
            "A1-A2 o contactos como A1) y World (x y z en mm, espacio del "
            "escáner de la T1). Si se deja vacío no se dibujan electrodos "
            "SEEG.",
            lambda: self._buscarArchivo(
                self.seegFilePathEdit,
                "Seleccione el archivo de electrodos SEEG",
                "TSV (*.tsv);;Todos los archivos (*)"
            )
        )

        self._agregarNota(
            clinicosForm,
            "* Obligatorio. Los archivos se copian a la carpeta del "
            "paciente (caracteristicas/ y electrodos/)."
        )

        # ====================================================
        # 4. EJECUTAR
        # ====================================================

        ejecutarSection = ctk.ctkCollapsibleButton()
        ejecutarSection.text = "4. Ejecutar"
        self.layout.addWidget(ejecutarSection)

        ejecutarLayout = qt.QVBoxLayout(
            ejecutarSection
        )

        self.estadoFormularioLabel = qt.QLabel()
        self.estadoFormularioLabel.wordWrap = True
        self.estadoFormularioLabel.setTextFormat(qt.Qt.RichText)

        ejecutarLayout.addWidget(
            self.estadoFormularioLabel
        )

        self.runButton = qt.QPushButton(
            "Procesar MRI nuevo (FreeSurfer, varias horas)"
        )

        self.runButton.setMinimumHeight(
            40
        )

        self.runButton.clicked.connect(
            self.onRunPipeline
        )

        ejecutarLayout.addWidget(
            self.runButton
        )

        self.visualizeButton = qt.QPushButton(
            "Visualizar paciente ya procesado (minutos)"
        )

        self.visualizeButton.setMinimumHeight(
            40
        )

        self.visualizeButton.clicked.connect(
            self.onVisualizarProcesado
        )

        ejecutarLayout.addWidget(
            self.visualizeButton
        )

        self.cancelButton = qt.QPushButton(
            "Cancelar procesamiento"
        )

        self.cancelButton.toolTip = (
            "Detiene FreeSurfer. Habrá que volver a procesar el paciente "
            "desde el principio."
        )

        self.cancelButton.enabled = False

        self.cancelButton.clicked.connect(
            self.onCancelPipeline
        )

        ejecutarLayout.addWidget(
            self.cancelButton
        )

        self.progressBar = qt.QProgressBar()
        self.progressBar.minimum = 0
        self.progressBar.maximum = self.totalSteps
        self.progressBar.value = 0

        ejecutarLayout.addWidget(
            self.progressBar
        )

        self.progressLabel = qt.QLabel(
            f"0 / {self.totalSteps} pasos"
        )

        ejecutarLayout.addWidget(
            self.progressLabel
        )

        self.elapsedLabel = qt.QLabel(
            ""
        )

        ejecutarLayout.addWidget(
            self.elapsedLabel
        )

        self.statusLabel = qt.QLabel(
            "Estado: esperando configuración"
        )

        self.statusLabel.wordWrap = True

        self.statusLabel.setStyleSheet(
            "font-weight: bold;"
        )

        ejecutarLayout.addWidget(
            self.statusLabel
        )

        # ====================================================
        # 5. RESULTADOS
        # ====================================================

        resultadosSection = ctk.ctkCollapsibleButton()
        resultadosSection.text = "5. Resultados"
        self.layout.addWidget(resultadosSection)

        resultadosLayout = qt.QVBoxLayout(
            resultadosSection
        )

        self.resultadosLabel = qt.QLabel(
            "Aún no hay resultados. Al terminar se abre el panel "
            "«Resultados de epileptogenicidad ML» a la derecha de la "
            "vista 3D."
        )

        self.resultadosLabel.wordWrap = True

        resultadosLayout.addWidget(
            self.resultadosLabel
        )

        resultadosBotones = qt.QHBoxLayout()

        self.showResultsButton = qt.QPushButton(
            "Mostrar panel de resultados"
        )

        self.showResultsButton.toolTip = (
            "Vuelve a abrir el panel de resultados si se cerró."
        )

        self.showResultsButton.enabled = False

        self.showResultsButton.clicked.connect(
            self.onMostrarResultados
        )

        resultadosBotones.addWidget(
            self.showResultsButton
        )

        self.openFolderButton = qt.QPushButton(
            "Abrir carpeta del paciente"
        )

        self.openFolderButton.toolTip = (
            "Abre la carpeta con los archivos generados (predicciones, "
            "registro del procesamiento y salida de FreeSurfer)."
        )

        self.openFolderButton.enabled = False

        self.openFolderButton.clicked.connect(
            self.onAbrirCarpetaSujeto
        )

        resultadosBotones.addWidget(
            self.openFolderButton
        )

        resultadosLayout.addLayout(
            resultadosBotones
        )

        # ====================================================
        # REGISTRO DETALLADO
        # ====================================================

        registroSection = ctk.ctkCollapsibleButton()
        registroSection.text = "Registro detallado"
        registroSection.collapsed = True
        self.layout.addWidget(registroSection)

        registroLayout = qt.QVBoxLayout(
            registroSection
        )

        self.logText = qt.QTextEdit()

        self.logText.setReadOnly(
            True
        )

        self.logText.setMinimumHeight(
            220
        )

        registroLayout.addWidget(
            self.logText
        )

        self.layout.addStretch(
            1
        )

        # ====================================================
        # ESTADO INICIAL
        # ====================================================

        self.restaurarPreferencias()

        self.checkPipelineFiles()

        self.actualizarEstadoFormulario()

    # ========================================================
    # CONSTRUCCIÓN DEL FORMULARIO
    # ========================================================

    def _crearCampoRuta(self, formLayout, etiqueta, placeholder, ayuda, alBuscar):

        """
        Fila del formulario con un campo de texto y un botón «Buscar...».
        Devuelve el campo.
        """

        campo = qt.QLineEdit()
        campo.placeholderText = placeholder
        campo.toolTip = ayuda

        campo.textChanged.connect(
            self.actualizarEstadoFormulario
        )

        boton = qt.QPushButton(
            "Buscar..."
        )

        boton.toolTip = ayuda

        boton.clicked.connect(
            alBuscar
        )

        fila = qt.QHBoxLayout()
        fila.addWidget(campo, 1)
        fila.addWidget(boton)

        formLayout.addRow(
            etiqueta,
            fila
        )

        return campo

    def _agregarNota(self, formLayout, texto):

        nota = qt.QLabel(
            texto
        )

        nota.wordWrap = True

        nota.setStyleSheet(
            "color: #666666; font-size: 11px;"
        )

        formLayout.addRow(
            nota
        )

        return nota

    # ========================================================
    # SELECCIONAR RUTAS
    # ========================================================

    def _carpetaInicial(self, campo):

        """Carpeta del valor actual del campo, o la última usada."""

        texto = campo.text.strip()

        if texto:
            ruta = Path(texto)
            return str(ruta if ruta.is_dir() else ruta.parent)

        return qt.QSettings().value(
            CLAVE_AJUSTES + "ultimaCarpeta",
            str(Path.home())
        )

    def _recordarCarpeta(self, ruta):

        ruta = Path(ruta)

        qt.QSettings().setValue(
            CLAVE_AJUSTES + "ultimaCarpeta",
            str(ruta if ruta.is_dir() else ruta.parent)
        )

    def _buscarCarpeta(self, campo, titulo):

        carpeta = qt.QFileDialog.getExistingDirectory(
            slicer.util.mainWindow(),
            titulo,
            self._carpetaInicial(campo)
        )

        if carpeta:
            campo.setText(carpeta)
            self._recordarCarpeta(carpeta)

    def _buscarArchivo(self, campo, titulo, filtro):

        ruta = qt.QFileDialog.getOpenFileName(
            slicer.util.mainWindow(),
            titulo,
            self._carpetaInicial(campo),
            filtro
        )

        if ruta:
            campo.setText(ruta)
            self._recordarCarpeta(ruta)

    # ========================================================
    # PREFERENCIAS
    # ========================================================

    def restaurarPreferencias(self):

        """
        Recupera FreeSurfer y la carpeta de resultados de la sesión
        anterior; si FreeSurfer no se había indicado, lo busca.
        """

        ajustes = qt.QSettings()

        freesurfer = (
            ajustes.value(CLAVE_AJUSTES + "freesurfer", "")
            or detectarFreeSurfer()
        )

        self.freesurferPathEdit.setText(
            freesurfer
        )

        self.subjectsDirEdit.setText(
            ajustes.value(CLAVE_AJUSTES + "subjectsDir", "")
        )

    def guardarPreferencias(self):

        formulario = self.leerFormulario()

        ajustes = qt.QSettings()

        ajustes.setValue(
            CLAVE_AJUSTES + "freesurfer",
            formulario["freesurfer"]
        )

        ajustes.setValue(
            CLAVE_AJUSTES + "subjectsDir",
            formulario["subjectsDir"]
        )

    # ========================================================
    # VALIDACIÓN DEL FORMULARIO
    # ========================================================

    def leerFormulario(self):

        """Valores del formulario, sin espacios a los lados."""

        return {
            "freesurfer": self.freesurferPathEdit.text.strip(),
            "t1": self.t1PathEdit.text.strip(),
            "subjectId": self.subjectIdEdit.text.strip(),
            "subjectsDir": self.subjectsDirEdit.text.strip(),
            "features": self.featuresFilePathEdit.text.strip(),
            "eeg": self.eegFilePathEdit.text.strip(),
            "seeg": self.seegFilePathEdit.text.strip(),
        }

    def validarFormulario(self, modo):

        """
        Problemas (texto para el usuario) que impiden ejecutar el modo
        "completo" (FreeSurfer + inferencia + visualización) o "procesado"
        (inferencia + visualización de un paciente que ya tiene la salida
        de FreeSurfer).

        Solo mira rutas y extensiones; el contenido de los archivos se
        comprueba al pulsar el botón (prevalidarArchivos).
        """

        formulario = self.leerFormulario()

        problemas = []

        if modo == "completo":

            freesurfer = formulario["freesurfer"]

            if os.name == "nt":
                problemas.append(
                    "Procesar un MRI nuevo requiere macOS o Linux: "
                    "FreeSurfer no funciona en Windows. Sí puede visualizar "
                    "pacientes ya procesados."
                )
            elif not freesurfer:
                problemas.append(
                    "Indique la instalación de FreeSurfer (paso 1)."
                )
            elif not (Path(freesurfer) / "SetUpFreeSurfer.sh").exists():
                problemas.append(
                    "La carpeta de FreeSurfer no contiene SetUpFreeSurfer.sh."
                )
            elif not (Path(freesurfer) / "license.txt").exists():
                problemas.append(
                    "Falta license.txt en la carpeta de FreeSurfer (la "
                    "licencia es gratuita: "
                    "surfer.nmr.mgh.harvard.edu/registration.html)."
                )

            if not self._pipelineDisponible:
                problemas.append(
                    "No se encontraron los scripts del pipeline (ver "
                    "Registro detallado)."
                )

            for campo, nombre in (
                ("freesurfer", "La carpeta de FreeSurfer"),
                ("subjectsDir", "La carpeta de resultados"),
                ("t1", "La ruta de la imagen T1"),
            ):
                if CARACTERES_PELIGROSOS.search(formulario[campo] or ""):
                    problemas.append(
                        f"{nombre} contiene comillas, '$', '`' o '\\', que "
                        "FreeSurfer no admite: renombre la carpeta o "
                        "elija otra."
                    )

        if not formulario["subjectId"]:
            problemas.append(
                "Escriba el ID del paciente (paso 2)."
            )
        elif not ID_VALIDO.match(formulario["subjectId"]):
            problemas.append(
                "El ID del paciente solo puede tener letras, números, '-', "
                "'_' y '.' (sin espacios ni tildes)."
            )

        if not formulario["subjectsDir"]:
            problemas.append(
                "Seleccione la carpeta de resultados (paso 2)."
            )

        if modo == "completo":

            t1 = formulario["t1"]

            if not t1:
                problemas.append(
                    "Seleccione la imagen T1 (paso 2)."
                )
            elif not Path(t1).is_file():
                problemas.append(
                    "La imagen T1 indicada no existe."
                )
            elif not t1.lower().endswith((".nii", ".nii.gz", ".mgz")):
                problemas.append(
                    "La imagen T1 debe ser .nii, .nii.gz o .mgz."
                )

        elif formulario["subjectId"] and formulario["subjectsDir"]:

            subjectDir = (
                Path(formulario["subjectsDir"])
                / formulario["subjectId"]
            )

            faltan = [
                relativo
                for relativo in ARCHIVOS_FREESURFER
                if not (subjectDir / relativo).exists()
            ]

            if faltan:
                problemas.append(
                    "El paciente no tiene la salida de FreeSurfer en "
                    f"{subjectDir} (falta {faltan[0]}). Procese antes su MRI."
                )
            elif (
                formulario["seeg"]
                and not (subjectDir / "mri" / "orig.mgz").exists()
            ):
                problemas.append(
                    "Para dibujar el SEEG hace falta mri/orig.mgz en la "
                    "carpeta del paciente."
                )

        problemas += self._validarArchivo(
            formulario["features"],
            "el archivo de características",
            (".csv",),
            obligatorio=True
        )

        problemas += self._validarArchivo(
            formulario["eeg"],
            "el archivo EEG",
            (".csv",)
        )

        problemas += self._validarArchivo(
            formulario["seeg"],
            "el archivo SEEG",
            (".tsv",)
        )

        return problemas

    @staticmethod
    def _validarArchivo(ruta, nombre, extensiones, obligatorio=False):

        if not ruta:
            return (
                [f"Seleccione {nombre} (paso 3)."]
                if obligatorio
                else []
            )

        if not Path(ruta).is_file():
            return [f"No existe {nombre}: {ruta}"]

        if not ruta.lower().endswith(extensiones):
            return [
                f"{nombre[0].upper()}{nombre[1:]} debe ser "
                f"{' o '.join(extensiones)}."
            ]

        return []

    def actualizarEstadoFormulario(self, *args):

        """
        Habilita cada botón de ejecución según lo que falte y lo explica
        bajo «4. Ejecutar». Se llama al cambiar cualquier campo.
        """

        if getattr(self, "estadoFormularioLabel", None) is None:
            return

        formulario = self.leerFormulario()

        if formulario["subjectsDir"] and formulario["subjectId"]:
            self.subjectDirLabel.setText(
                "Carpeta del paciente: "
                f"{Path(formulario['subjectsDir']) / formulario['subjectId']}"
            )
        else:
            self.subjectDirLabel.setText(
                "Los resultados se guardarán en "
                "<carpeta de resultados>/<ID del paciente>."
            )

        # Mientras se procesa, los botones quedan bloqueados.
        if self.process is not None:
            return

        lineas = []

        for modo, boton, nombre, ayuda in (
            (
                "completo",
                self.runButton,
                "Procesar MRI nuevo",
                "Ejecuta FreeSurfer sobre la T1 (varias horas), el modelo y "
                "la visualización.",
            ),
            (
                "procesado",
                self.visualizeButton,
                "Visualizar paciente ya procesado",
                "Para un paciente que ya tiene la salida de FreeSurfer en su "
                "carpeta: ejecuta el modelo y la visualización (minutos).",
            ),
        ):

            problemas = self.validarFormulario(modo)

            boton.enabled = not problemas

            boton.toolTip = (
                ayuda
                + (
                    "\n\nFalta:\n• " + "\n• ".join(problemas)
                    if problemas
                    else ""
                )
            )

            if problemas:
                elementos = "".join(
                    f"<li>{html.escape(problema)}</li>"
                    for problema in problemas[:4]
                )
                lineas.append(
                    f"<b>{nombre}</b>: falta"
                    f"<ul style='margin-top:0; margin-bottom:0'>{elementos}</ul>"
                )
            else:
                lineas.append(
                    f"<b>{nombre}</b>: "
                    "<span style='color:#1b7a1b'>✓ listo</span>"
                )

        self.estadoFormularioLabel.setText(
            "<br>".join(lineas)
        )

    def _bloquearFormulario(self, bloquear):

        """Durante el procesamiento no se pueden cambiar los datos."""

        for widget in (
            self.freesurferSection,
            self.pacienteSection,
            self.clinicosSection,
            self.demoButton,
        ):
            widget.enabled = not bloquear

        if bloquear:
            self.runButton.enabled = False
            self.visualizeButton.enabled = False

        self.cancelButton.enabled = bloquear

    # ========================================================
    # VERIFICAR PIPELINE
    # ========================================================

    def checkPipelineFiles(self):

        self._pipelineDisponible = (
            self.pipelineDir / "pipeline_principal.py"
        ).exists()

        if not self._pipelineDisponible:

            self.log(
                f"✗ ERROR: No se encontró pipeline_principal.py en {self.pipelineDir}."
            )

            self.statusLabel.setText(
                "Estado: ERROR — no se encontraron los scripts del pipeline"
            )

            return

        self.log(
            f"✓ Pipeline: {self.pipelineDir}"
        )

        self.statusLabel.setText(
            "Estado: complete los pasos 1 a 3"
        )

    # ========================================================
    # LOG
    # ========================================================

    def log(self, message):

        self.logText.append(
            message
        )

        # Forzar actualización visual
        qt.QApplication.processEvents()

    # ========================================================
    # AYUDA Y DEMOSTRACIÓN
    # ========================================================

    def onAbrirManual(self):

        """Muestra Resources/Docs/MANUAL_USUARIO.md en una ventana no modal."""

        manual = RECURSOS_DIR / "Docs" / "MANUAL_USUARIO.md"

        if not manual.exists():
            slicer.util.errorDisplay(
                f"No se encontró el manual de uso:\n{manual}"
            )
            return

        if self._manualDialog is None:

            dialogo = qt.QDialog(
                slicer.util.mainWindow()
            )

            dialogo.setWindowTitle(
                "Clasificación de ZE — Manual de uso"
            )

            dialogo.resize(
                820,
                900
            )

            dialogoLayout = qt.QVBoxLayout(
                dialogo
            )

            navegador = qt.QTextBrowser()
            navegador.setOpenExternalLinks(True)
            navegador.setSearchPaths([str(manual.parent)])
            navegador.setMarkdown(manual.read_text(encoding="utf-8"))

            # Las capturas se muestran al ancho de la ventana, no a su
            # tamaño real (que obligaría a desplazarse en horizontal).
            navegador.setHtml(
                navegador.toHtml().replace(
                    "<img ",
                    '<img width="740" '
                )
            )

            dialogoLayout.addWidget(
                navegador
            )

            cerrarButton = qt.QPushButton(
                "Cerrar"
            )

            # Con lambda: PythonQt pasaría el bool de clicked(bool) a
            # QDialog.close(), que no admite argumentos, y no cerraría.
            cerrarButton.clicked.connect(
                lambda: dialogo.close()
            )

            dialogoLayout.addWidget(
                cerrarButton
            )

            self._manualDialog = dialogo

        self._manualDialog.show()

        try:
            self._manualDialog.raise_()
        except Exception:
            pass

    def onCargarDemo(self):

        """
        Prepara el paciente de demostración (cerebro fsaverage de FreeSurfer
        + datos sintéticos de Resources/Demo) y rellena el formulario.
        """

        freesurfer = self.freesurferPathEdit.text.strip()

        fsaverage = (
            Path(freesurfer) / "subjects" / "fsaverage"
            if freesurfer
            else None
        )

        if fsaverage is None or not fsaverage.is_dir():

            slicer.util.errorDisplay(
                "La demostración usa el cerebro de referencia «fsaverage» "
                "que incluye FreeSurfer.\n\n"
                "Indique primero en el paso 1 la carpeta de instalación de "
                "FreeSurfer."
            )

            return

        subjectsPath = Path(
            self.subjectsDirEdit.text.strip()
            or Path.home() / "ClasificacionZE_resultados"
        )

        subjectDir = subjectsPath / ID_DEMO

        try:

            for relativo in ARCHIVOS_FREESURFER + ["mri/orig.mgz"]:

                destino = subjectDir / relativo

                if not destino.exists():
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(fsaverage / relativo, destino)

        except Exception as e:

            slicer.util.errorDisplay(
                "No se pudo preparar el paciente de demostración en "
                f"{subjectDir}:\n{e}"
            )

            return

        demoDir = RECURSOS_DIR / "Demo"

        self.subjectIdEdit.setText(ID_DEMO)
        self.subjectsDirEdit.setText(str(subjectsPath))
        self.t1PathEdit.setText("")
        self.featuresFilePathEdit.setText(str(demoDir / "caracteristicas_demo.csv"))
        self.eegFilePathEdit.setText(str(demoDir / "eeg_superficie_demo.csv"))
        self.seegFilePathEdit.setText(str(demoDir / "seeg_dipolos_demo.tsv"))

        self.log(
            f"✓ Paciente de demostración preparado en {subjectDir} "
            "(fsaverage + datos sintéticos)."
        )

        self.statusLabel.setText(
            "Estado: datos de demostración cargados — pulse «Visualizar "
            "paciente ya procesado»"
        )

        slicer.util.infoDisplay(
            "Datos de demostración listos.\n\n"
            f"Paciente: {ID_DEMO} (cerebro de referencia fsaverage)\n"
            "Datos clínicos: SINTÉTICOS, no corresponden a ningún paciente.\n\n"
            "Pulse «Visualizar paciente ya procesado» en el paso 4.",
            windowTitle="Datos de demostración"
        )

    # ========================================================
    # RESULTADOS
    # ========================================================

    def onMostrarResultados(self):

        if self.mlVisualizer is not None:
            self.mlVisualizer.mostrarPanel()

    def onAbrirCarpetaSujeto(self):

        if self.currentSubjectDir is None:
            return

        qt.QDesktopServices.openUrl(
            qt.QUrl.fromLocalFile(str(self.currentSubjectDir))
        )

    # ========================================================
    # PREPARAR EL PACIENTE
    # ========================================================

    def _preguntar(self, texto, opciones, porDefecto=0, titulo="Clasificación de ZE"):

        """
        Diálogo con un botón por opción; devuelve el índice elegido (o -1
        si se cierra). En modo testing devuelve porDefecto sin mostrarlo.
        """

        if slicer.app.testingEnabled():
            return porDefecto

        caja = qt.QMessageBox(
            slicer.util.mainWindow()
        )

        caja.setWindowTitle(titulo)
        caja.setIcon(qt.QMessageBox.Question)
        caja.setText(texto)

        botones = [
            caja.addButton(opcion, qt.QMessageBox.AcceptRole)
            for opcion in opciones
        ]

        caja.setDefaultButton(botones[porDefecto])

        caja.exec_()

        pulsado = caja.clickedButton()

        for indice, boton in enumerate(botones):
            if boton == pulsado:
                return indice

        return -1

    def prevalidarArchivos(self, formulario):

        """
        Lee el contenido de los archivos clínicos (no solo la ruta) para
        avisar antes de empezar. Devuelve (errores, avisos).
        """

        errores = []
        avisos = []

        try:

            inferencia_ml = self.importarInferencia()

            implantadas = inferencia_ml.validarCaracteristicas(
                formulario["features"]
            )

            self.log(
                f"✓ Características válidas: {implantadas} regiones implantadas."
            )

        except Exception as e:

            errores.append(
                str(e)
            )

        self._importarVisualizacionML()

        if formulario["eeg"]:

            try:

                from visualizacion_electrodos import (
                    VisualizacionElectrodos,
                    leerNombresArchivoEEG,
                )

                nombres = leerNombresArchivoEEG(formulario["eeg"])

                otros = [
                    nombre
                    for nombre in nombres
                    if nombre not in VisualizacionElectrodos.STANDARD_1020
                ]

                if len(otros) == len(nombres):
                    errores.append(
                        "El archivo EEG no contiene ningún electrodo del "
                        "sistema 10-20 reconocido (por ejemplo Fp1, Cz, O2)."
                    )
                elif otros:
                    avisos.append(
                        "Electrodos EEG que no se dibujarán (no están en el "
                        f"montage 10-20): {', '.join(otros)}"
                    )

            except Exception as e:

                errores.append(
                    f"No se pudo leer el archivo EEG: {e}"
                )

        if formulario["seeg"]:

            try:

                from visualizacion_electrodos_barra import (
                    leerDipolos,
                    reconstruirContactos,
                )

                electrodos = leerDipolos(formulario["seeg"])

                validos = [
                    nombre
                    for nombre, entrada in electrodos.items()
                    if reconstruirContactos(entrada)
                ]

                if not validos:
                    errores.append(
                        "El archivo SEEG no contiene electrodos válidos (se "
                        "esperan las columnas Channel y World, con canales "
                        "como A1-A2)."
                    )
                else:
                    self.log(
                        f"✓ SEEG válido: {len(validos)} electrodos."
                    )

            except Exception as e:

                errores.append(
                    f"No se pudo leer el archivo SEEG: {e}"
                )

        return errores, avisos

    @staticmethod
    def _copiarAlSujeto(origen, destino):

        """Copia origen a destino, salvo que ya sean el mismo archivo."""

        destino.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        if destino.exists() and Path(origen).resolve() == destino.resolve():
            return

        shutil.copy2(
            origen,
            destino
        )

    def copiarArchivosSujeto(self, formulario, subjectDir):

        """
        Copia características, EEG y SEEG a la carpeta del paciente. Si
        EEG o SEEG no se seleccionaron, borra la copia de una ejecución
        anterior para no mostrar electrodos de otra sesión.
        """

        destinos = (
            ("features", subjectDir / "caracteristicas" / "caracteristicas_modelo.csv"),
            ("eeg", subjectDir / "electrodos" / "eeg_superficie.csv"),
            ("seeg", subjectDir / "electrodos" / "seeg_dipolos.tsv"),
        )

        try:

            for clave, destino in destinos:

                if formulario[clave]:

                    self._copiarAlSujeto(
                        formulario[clave],
                        destino
                    )

                    self.log(
                        f"✓ Copiado a: {destino}"
                    )

                elif destino.exists():

                    destino.unlink()

        except Exception as e:

            slicer.util.errorDisplay(
                "No se pudieron copiar los archivos a la carpeta del "
                f"paciente:\n{e}"
            )

            return False

        return True

    # ========================================================
    # VISUALIZAR PACIENTE YA PROCESADO
    # ========================================================

    def onVisualizarProcesado(self):

        """
        Ejecuta la inferencia y la visualización de un paciente que ya
        tiene la salida de FreeSurfer, sin volver a procesar su MRI.
        """

        formulario = self.leerFormulario()

        problemas = self.validarFormulario(
            "procesado"
        )

        if problemas:

            slicer.util.errorDisplay(
                "No se puede visualizar el paciente:\n\n• "
                + "\n• ".join(problemas)
            )

            return

        if not self.asegurarDependenciasInferencia():
            return

        errores, avisos = self.prevalidarArchivos(
            formulario
        )

        if errores:

            slicer.util.errorDisplay(
                "Revise los datos clínicos (paso 3):\n\n• "
                + "\n• ".join(errores)
            )

            return

        for aviso in avisos:
            self.log(
                f"⚠ {aviso}"
            )

        self.guardarPreferencias()

        subjectDir = (
            Path(formulario["subjectsDir"])
            / formulario["subjectId"]
        )

        if not self.copiarArchivosSujeto(formulario, subjectDir):
            return

        self.currentSubjectDir = subjectDir

        self.freesurferPath = (
            Path(formulario["freesurfer"])
            if formulario["freesurfer"]
            else None
        )

        self.progressBar.value = 0
        self.progressLabel.setText("FreeSurfer: no se vuelve a ejecutar")
        self.elapsedLabel.setText("")

        qt.QApplication.setOverrideCursor(
            qt.Qt.WaitCursor
        )

        try:
            self.iniciarInferenciaML()
        finally:
            qt.QApplication.restoreOverrideCursor()

    # ========================================================
    # EJECUTAR PIPELINE
    # ========================================================

    def onRunPipeline(self):

        formulario = self.leerFormulario()

        problemas = self.validarFormulario(
            "completo"
        )

        if problemas:

            slicer.util.errorDisplay(
                "No se puede iniciar el procesamiento:\n\n• "
                + "\n• ".join(problemas)
            )

            return

        freesurferPath = Path(formulario["freesurfer"])
        licensePath = freesurferPath / "license.txt"
        t1Path = Path(formulario["t1"])
        subjectId = formulario["subjectId"]
        subjectsPath = Path(formulario["subjectsDir"])
        subjectDir = subjectsPath / subjectId

        # ========================================================
        # PACIENTE YA PROCESADO: OFRECER SOLO VISUALIZAR
        # ========================================================

        if all((subjectDir / relativo).exists() for relativo in ARCHIVOS_FREESURFER):

            eleccion = self._preguntar(
                f"El paciente «{subjectId}» ya tiene la salida de "
                f"FreeSurfer en:\n{subjectDir}\n\n¿Qué desea hacer?",
                [
                    "Visualizar sin reprocesar",
                    "Reprocesar (sobrescribe, varias horas)",
                    "Cancelar",
                ]
            )

            if eleccion == 0:
                self.onVisualizarProcesado()
                return

            if eleccion != 1:
                return

        # ========================================================
        # DEPENDENCIAS Y CONTENIDO (antes de FreeSurfer, que tarda horas)
        # ========================================================

        if not self.asegurarDependenciasInferencia():
            return

        errores, avisos = self.prevalidarArchivos(
            formulario
        )

        if errores:

            slicer.util.errorDisplay(
                "Corrija estos problemas antes de empezar (el "
                "procesamiento tarda horas y fallaría al final):\n\n• "
                + "\n• ".join(errores)
            )

            return

        # ========================================================
        # CONFIRMAR
        # ========================================================

        resumen = (
            f"Se procesará el paciente «{subjectId}».\n\n"
            f"• T1: {t1Path.name}\n"
            f"• Carpeta del paciente: {subjectDir}\n"
            f"• EEG: {'sí' if formulario['eeg'] else 'no'}    "
            f"• SEEG: {'sí' if formulario['seeg'] else 'no'}\n\n"
            "FreeSurfer tarda varias horas. Puede seguir usando Slicer "
            "mientras tanto, pero no lo cierre: al cerrarlo se detiene el "
            "procesamiento."
        )

        if (subjectDir / "mri").exists():
            resumen += (
                "\n\n⚠ La carpeta del paciente ya contiene resultados "
                "anteriores, que se sobrescribirán."
            )

        if avisos:
            resumen += "\n\n⚠ " + "\n⚠ ".join(avisos)

        if not slicer.util.confirmOkCancelDisplay(
            resumen,
            windowTitle="Confirmar procesamiento"
        ):
            return

        self.guardarPreferencias()

        # Guardar la instalación seleccionada para que la
        # visualización ML automática pueda reutilizarla cuando
        # termine el pipeline.
        self.freesurferPath = freesurferPath

        # ========================================================
        # CREAR DIRECTORIO Y COPIAR ARCHIVOS
        # ========================================================

        try:

            subjectsPath.mkdir(
                parents=True,
                exist_ok=True
            )

        except Exception as e:

            slicer.util.errorDisplay(
                f"No se pudo crear el directorio:\n{e}"
            )

            return

        if not self.copiarArchivosSujeto(formulario, subjectDir):
            return

        pipelineScript = (
            self.pipelineDir /
            "pipeline_principal.py"
        )

        # ========================================================
        # GUARDAR SUJETO ACTUAL
        # ========================================================

        self.currentSubjectDir = (
            subjectDir
        )

        # ========================================================
        # LIMPIAR INTERFAZ
        # ========================================================

        self.logText.clear()

        self.progressBar.value = 0

        self.progressLabel.setText(
            f"0 / {self.totalSteps} pasos"
        )

        self.statusLabel.setText(
            "Estado: iniciando procesamiento..."
        )

        # ========================================================
        # MOSTRAR CONFIGURACIÓN
        # ========================================================

        self.log("=" * 70)
        self.log("CONFIGURACIÓN DEL PIPELINE")
        self.log("=" * 70)
        self.log(f"FreeSurfer: {freesurferPath}")
        self.log(f"Licencia: {licensePath}")
        self.log(f"MRI T1: {t1Path}")
        self.log(f"Subject ID: {subjectId}")
        self.log(f"Subjects Directory: {subjectsPath}")
        self.log(f"Archivo EEG seleccionado: {formulario['eeg'] or '(ninguno)'}")
        self.log(f"Archivo SEEG seleccionado: {formulario['seeg'] or '(ninguno)'}")
        self.log(f"Archivo de características seleccionado: {formulario['features']}")
        self.log(f"Subject Directory: {subjectDir}")
        self.log(f"Pipeline: {pipelineScript}")

        for aviso in avisos:
            self.log(f"⚠ {aviso}")

        # ========================================================
        # VARIABLES DE ENTORNO
        # ========================================================

        env = os.environ.copy()

        env["FREESURFER_HOME"] = (
            str(freesurferPath)
        )

        env["FS_LICENSE"] = (
            str(licensePath)
        )

        env["SUBJECTS_DIR"] = (
            str(subjectsPath)
        )

        env["SUBJECT_ID"] = (
            subjectId
        )

        env["T1"] = (
            str(t1Path)
        )

        env["FEATURES_FILE"] = (
            str(subjectDir / "caracteristicas" / "caracteristicas_modelo.csv")
        )

        runDir = Path(
            tempfile.mkdtemp(
                prefix="Visualizacion_epilepsia_"
            )
        )

        statusFile = runDir / "pipeline_status.txt"
        currentFile = runDir / "pipeline_current.txt"
        logFile = runDir / "pipeline.log"

        env["PIPELINE_STATUS_FILE"] = str(statusFile)
        env["PIPELINE_CURRENT_FILE"] = str(currentFile)
        env["PIPELINE_LOG_FILE"] = str(logFile)
        self.statusFile = statusFile
        self.currentFile = currentFile
        self.logFile = logFile

        self.pipelineLogFile = open(
            logFile,
            "a",
            encoding="utf-8"
        )

        # ========================================================
        # PYTHON
        # ========================================================

        pythonExecutable = (
            sys.executable
        )

        self.log(
            f"Python: {pythonExecutable}"
        )

        # ========================================================
        # EJECUTAR PROCESO
        # ========================================================

        try:

            # Reiniciar la lectura incremental para esta ejecución.
            self._logFileOffset = 0
            self.logText.clear()

            self.process = subprocess.Popen(
                [
                    pythonExecutable,
                    "-u",
                    str(pipelineScript)
                ],
                cwd=str(
                    self.pipelineDir
                ),
                env=env,
                stdout=self.pipelineLogFile,
                stderr=subprocess.STDOUT,
                start_new_session=True
            )

        except Exception as e:

            self.pipelineLogFile.close()
            self.pipelineLogFile = None

            self.log(
                f"✗ ERROR AL INICIAR PIPELINE: {e}"
            )

            self.statusLabel.setText(
                "Estado: error al iniciar el procesamiento"
            )

            slicer.util.errorDisplay(
                f"No se pudo iniciar el procesamiento:\n{e}"
            )

            return

        self._bloquearFormulario(True)

        self._inicioPipeline = time.monotonic()

        self.statusLabel.setText(
            "Estado: procesando con FreeSurfer..."
        )

        # ========================================================
        # TIMER PARA CONSULTAR ESTADO
        # ========================================================

        self.timer = qt.QTimer()

        self.timer.setInterval(
            1000
        )

        self.timer.timeout.connect(
            self.updatePipelineStatus
        )

        self.timer.start()

        self.log(
            ""
        )

        self.log(
            "✓ Pipeline iniciado en segundo plano."
        )

        self.log(
            "La interfaz continuará disponible "
            "mientras FreeSurfer trabaja."
        )

    def updatePipelineStatus(self):
        """
        Actualiza progreso y estado sin volver a leer pipeline.log completo.

        Solo procesa el texto nuevo desde la última consulta y limita el
        tamaño del texto visible para mantener Slicer responsivo.
        """
        if self.currentSubjectDir is None:
            return

        statusFile = self.statusFile
        currentFile = self.currentFile

        if self._inicioPipeline is not None:
            self.elapsedLabel.setText(
                "Tiempo transcurrido: "
                f"{formatoDuracion(time.monotonic() - self._inicioPipeline)}"
            )

        # ========================================================
        # LEER PASO
        # ========================================================
        if statusFile.exists():
            try:
                step = int(
                    statusFile.read_text(
                        encoding="utf-8"
                    ).strip()
                )

                if step == -1:
                    self.progressBar.value = 0
                    self.statusLabel.setText(
                        "Estado: ERROR en el pipeline"
                    )
                    self.finishPipeline(False)
                    return

                if step >= 0:
                    self.currentStep = step
                    self.progressBar.value = min(
                        step,
                        self.totalSteps
                    )
                    self.progressLabel.setText(
                        f"{step} / {self.totalSteps} pasos"
                    )

            except Exception:
                pass

        # ========================================================
        # LEER SCRIPT ACTUAL
        # ========================================================
        if currentFile.exists():
            try:
                currentScript = (
                    currentFile.read_text(
                        encoding="utf-8"
                    ).strip()
                )

                if currentScript:
                    if currentScript == "COMPLETADO":
                        self.statusLabel.setText(
                            "Estado: FreeSurfer completado"
                        )
                    elif currentScript.startswith("ERROR"):
                        self.statusLabel.setText(
                            f"Estado: {currentScript}"
                        )
                    elif currentScript in DESCRIPCION_PASOS:
                        self.statusLabel.setText(
                            f"Paso {self.currentStep}/{self.totalSteps}: "
                            f"{DESCRIPCION_PASOS[currentScript]}"
                        )
                    else:
                        self.statusLabel.setText(
                            f"Estado: {currentScript}"
                        )

            except Exception:
                pass

        # ========================================================
        # LEER SOLO EL TEXTO NUEVO DEL LOG
        # ========================================================
        logFile = self.logFile

        if logFile.exists():
            try:
                fileSize = logFile.stat().st_size

                # Si el archivo fue truncado, empezar de nuevo.
                if fileSize < self._logFileOffset:
                    self._logFileOffset = 0

                if fileSize > self._logFileOffset:
                    with logFile.open(
                        "r",
                        encoding="utf-8",
                        errors="replace"
                    ) as f:
                        f.seek(self._logFileOffset)
                        newText = f.read(self._maxLogChunk)
                        self._logFileOffset = f.tell()

                    if newText:
                        self.logText.moveCursor(
                            qt.QTextCursor.End
                        )
                        self.logText.insertPlainText(
                            newText
                        )

                        # Mantener el widget ligero aunque el log sea grande.
                        currentText = self.logText.toPlainText()

                        if len(currentText) > self._maxLogChars:
                            self.logText.setPlainText(
                                currentText[-self._maxLogChars:]
                            )

                        self.logText.moveCursor(
                            qt.QTextCursor.End
                        )
                        self.logText.verticalScrollBar().setValue(
                            self.logText.verticalScrollBar().maximum()
                        )

            except Exception:
                pass

        # ========================================================
        # COMPROBAR PROCESO
        # ========================================================
        if self.process is not None:
            returnCode = self.process.poll()

            if returnCode is not None:
                if returnCode == 0:
                    self.finishPipeline(True)
                else:
                    self.finishPipeline(False)

    @staticmethod
    def _importarVisualizacionML():

        """Añade VisualizacionML/ a sys.path para importar sus visualizadores."""

        visualizacionMLDirString = str(
            carpetaExtension("VisualizacionML")
        )

        if visualizacionMLDirString not in sys.path:

            sys.path.insert(
                0,
                visualizacionMLDirString
            )

    def importarInferencia(self):

        """
        Importa Inferencia/inferencia_ml.py (y con él soz_inferencia.py)
        añadiendo la carpeta a sys.path, como VisualizacionML.
        """

        inferenciaDirString = str(self.inferenciaDir)

        if inferenciaDirString not in sys.path:

            sys.path.insert(
                0,
                inferenciaDirString
            )

        import inferencia_ml

        return inferencia_ml

    def asegurarDependenciasInferencia(self):

        """
        Comprueba el modelo y las dependencias de la inferencia
        (pandas, joblib, scikit-learn con la versión del entrenamiento)
        y las instala en el Python de Slicer si faltan.

        Devuelve True si la inferencia se puede ejecutar.
        """

        try:

            inferencia_ml = self.importarInferencia()

        except Exception as e:

            slicer.util.errorDisplay(
                "No se pudo cargar el módulo de inferencia "
                f"({self.inferenciaDir}):\n{e}"
            )

            return False

        if not inferencia_ml.MODELO_FILE.exists():

            slicer.util.errorDisplay(
                "No se encontró el modelo entrenado:\n"
                f"{inferencia_ml.MODELO_FILE}"
            )

            return False

        faltantes = inferencia_ml.dependenciasFaltantes()

        if not faltantes:

            return True

        # El catálogo de extensiones exige consentimiento explícito antes
        # de descargar nada.
        if self._preguntar(
            "Para ejecutar el modelo hay que instalar en el Python de "
            f"Slicer: {', '.join(faltantes)}.\n\n"
            "Se descargarán de PyPI (pypi.org) una sola vez; puede tardar "
            "unos minutos. ¿Instalar ahora?",
            ["Instalar", "Cancelar"]
        ) != 0:

            self.log(
                "Instalación de dependencias cancelada: el modelo no se "
                "puede ejecutar sin ellas."
            )

            return False

        self.log(
            "Instalando dependencias del modelo: "
            f"{', '.join(faltantes)} (solo la primera vez)..."
        )

        qt.QApplication.setOverrideCursor(
            qt.Qt.WaitCursor
        )

        try:

            slicer.util.pip_install(
                faltantes
            )

        except Exception as e:

            qt.QApplication.restoreOverrideCursor()

            slicer.util.errorDisplay(
                "No se pudieron instalar las dependencias del modelo "
                f"({', '.join(faltantes)}):\n{e}"
            )

            return False

        qt.QApplication.restoreOverrideCursor()

        faltantes = inferencia_ml.dependenciasFaltantes()

        if faltantes:

            slicer.util.errorDisplay(
                "Siguen faltando dependencias del modelo tras la "
                f"instalación: {', '.join(faltantes)}"
            )

            return False

        if "sklearn" in sys.modules:

            # Una versión anterior ya importada sigue en memoria.
            self.log(
                "⚠ scikit-learn ya estaba cargado en esta sesión: "
                "reinicie Slicer para usar la versión instalada."
            )

        self.log(
            "✓ Dependencias del modelo instaladas."
        )

        return True

    def iniciarInferenciaML(self):

        """
        Ejecuta el modelo de SOZ sobre las características del sujeto
        (caracteristicas/caracteristicas_modelo.csv) cuando FreeSurfer
        terminó, y después lanza la visualización ML.

        Escribe en la carpeta del sujeto:
            - predicciones_soz_modelo.csv (tabla del modelo; la probabilidad
              calibrada solo está aquí, la interfaz no la muestra)
            - predicciones_epileptogenicidad.csv (lo que se visualiza)
        """

        if self.currentSubjectDir is None:
            self.log(
                "⚠ No hay sujeto actual para la inferencia."
            )
            return

        self.log(
            ""
        )

        self.log(
            "=" * 70
        )

        self.log(
            "INFERENCIA DEL MODELO DE SOZ"
        )

        self.log(
            "=" * 70
        )

        self.statusLabel.setText(
            "Estado: ejecutando inferencia del modelo..."
        )

        if not self.asegurarDependenciasInferencia():

            self.statusLabel.setText(
                "Estado: pipeline terminado, "
                "pero faltan dependencias del modelo"
            )

            return

        try:

            inferencia_ml = self.importarInferencia()

            resultado = inferencia_ml.ejecutarInferencia(
                self.currentSubjectDir
            )

        except Exception as e:

            self.log(
                "✗ ERROR EN LA INFERENCIA DEL MODELO:"
            )

            self.log(
                str(e)
            )

            import traceback

            self.log(
                traceback.format_exc()
            )

            self.statusLabel.setText(
                "Estado: la inferencia del modelo falló"
            )

            slicer.util.errorDisplay(
                "El modelo no pudo calcular las predicciones:\n\n"
                f"{e}\n\n"
                "Revise el archivo de características (paso 3). El detalle "
                "técnico está en «Registro detallado».",
                windowTitle="Error en la inferencia"
            )

            return

        regiones = "".join(
            f"<li>{html.escape(nombreRegion(region))}</li>"
            for region in resultado["marcadas"]
        )

        self.resultadosLabel.setText(
            f"<b>Paciente:</b> {html.escape(self.currentSubjectDir.name)}<br>"
            f"<b>Regiones implantadas evaluadas:</b> {resultado['n_implantadas']}<br>"
            "<b>Regiones clasificadas como epileptogénicas</b> "
            f"({resultado['n_marcadas']}, en rojo en la vista 3D):"
            f"<ul style='margin-top:0'>{regiones}</ul>"
        )

        self.openFolderButton.enabled = True

        for aviso in resultado["avisos"]:
            self.log(
                f"⚠ {aviso}"
            )

        self.log(
            f"✓ Parcelas implantadas evaluadas: {resultado['n_implantadas']}"
        )

        self.log(
            "✓ Regiones clasificadas como epileptogénicas: "
            f"{resultado['n_marcadas']} "
            f"(regiones coloreadas: {resultado['n_mostradas']})"
        )

        for region in resultado["marcadas"]:
            self.log(
                f"   - {nombreRegion(region)}"
            )

        self.log(
            f"✓ Predicciones del modelo: {resultado['archivo_modelo']}"
        )

        self.log(
            f"✓ Predicciones para visualizar: {resultado['archivo_visual']}"
        )

        self.iniciarVisualizacionML()

    def iniciarVisualizacionML(self):

        """
        Inicia automáticamente la visualización cortical ML cuando
        el pipeline de FreeSurfer terminó correctamente.

        Requiere:
            - lh.pial / rh.pial
            - lh.aparc.a2009s.annot / rh.aparc.a2009s.annot
            - predicciones_epileptogenicidad.csv

        Los electrodos EEG (electrodos/eeg_superficie.csv) y SEEG
        (electrodos/seeg_dipolos.tsv) son opcionales: si no están, no se
        dibujan ni aparecen sus controles en el panel.
        """

        if self.currentSubjectDir is None:
            self.log(
                "⚠ No hay sujeto actual para visualizar."
            )
            return

        subjectDir = Path(
            self.currentSubjectDir
        )

        predictionsFile = (
            subjectDir
            / "predicciones_epileptogenicidad.csv"
        )

        lhPial = (
            subjectDir
            / "surf"
            / "lh.pial"
        )

        rhPial = (
            subjectDir
            / "surf"
            / "rh.pial"
        )

        lhAnnot = (
            subjectDir
            / "label"
            / "lh.aparc.a2009s.annot"
        )

        rhAnnot = (
            subjectDir
            / "label"
            / "rh.aparc.a2009s.annot"
        )

        requiredFiles = [
            predictionsFile,
            lhPial,
            rhPial,
            lhAnnot,
            rhAnnot
        ]

        missingFiles = [
            str(path)
            for path in requiredFiles
            if not path.exists()
        ]

        if missingFiles:

            self.log(
                "⚠ No se puede iniciar la visualización ML "
                "porque faltan archivos:"
            )

            for path in missingFiles:
                self.log(
                    f"   - {path}"
                )

            self.statusLabel.setText(
                "Estado: faltan datos para la visualización"
            )

            slicer.util.errorDisplay(
                "No se puede mostrar la visualización porque faltan "
                "archivos:\n\n• " + "\n• ".join(missingFiles)
            )

            return

        try:

            # ------------------------------------------------------
            # Cerrar visualizador anterior.
            # ------------------------------------------------------

            if self.mlVisualizer is not None:

                try:
                    self.mlVisualizer.cerrar()
                except Exception:
                    pass

                self.mlVisualizer = None

            if self.seegVisualizer is not None:

                try:
                    self.seegVisualizer.cerrar()
                except Exception:
                    pass

                self.seegVisualizer = None

            if self.eegVisualizer is not None:

                try:
                    self.eegVisualizer.cerrar()
                except Exception:
                    pass

                self.eegVisualizer = None

            # ------------------------------------------------------
            # Importar el módulo ML incluido en la extensión.
            # ------------------------------------------------------

            self._importarVisualizacionML()

            from visualizacion_ml import VisualizacionML

            # ------------------------------------------------------
            # Crear y ejecutar visualización.
            # ------------------------------------------------------

            self.log(
                ""
            )

            self.log(
                "=" * 70
            )

            self.log(
                "INICIANDO VISUALIZACIÓN CORTICAL ML"
            )

            self.log(
                "=" * 70
            )

            self.mlVisualizer = VisualizacionML(
                subjectDir,
                self.freesurferPath
            )

            mlResult = self.mlVisualizer.ejecutar()

            self.iniciarVisualizacionEEG(
                subjectDir,
                mlResult
            )

            self.iniciarVisualizacionSEEG(
                subjectDir,
                mlResult
            )

            self.statusLabel.setText(
                "Estado: listo — explore los resultados en el panel "
                "«Resultados de epileptogenicidad ML» (a la derecha)"
            )

            self.showResultsButton.enabled = True

            self.openFolderButton.enabled = True

            self.log(
                "✓ Visualización cortical ML completada."
            )

            self.log(
                "✓ Seleccione una región en la tabla del panel de "
                "resultados para enfocarla en la vista 3D."
            )

        except Exception as e:

            self.log(
                "✗ ERROR AL INICIAR VISUALIZACIÓN ML:"
            )

            self.log(
                str(e)
            )

            import traceback

            self.log(
                traceback.format_exc()
            )

            self.statusLabel.setText(
                "Estado: la visualización falló"
            )

            slicer.util.errorDisplay(
                "No se pudo mostrar la visualización 3D:\n\n"
                f"{e}\n\n"
                "Las predicciones sí se guardaron en la carpeta del "
                "paciente. El detalle técnico está en «Registro detallado».",
                windowTitle="Error en la visualización"
            )

    def iniciarVisualizacionEEG(self, subjectDir, mlResult):

        """
        Dibuja los electrodos EEG de superficie (10-20) alrededor de la
        corteza si el sujeto tiene electrodos/eeg_superficie.csv. Un fallo
        aquí no interrumpe el resto de la visualización.
        """

        eegFile = (
            Path(subjectDir)
            / "electrodos"
            / "eeg_superficie.csv"
        )

        if not eegFile.exists():
            self.log(
                "ℹ Sin archivo EEG: no se dibujan electrodos de superficie."
            )
            return

        try:

            from visualizacion_electrodos import (
                VisualizacionElectrodos
            )

            self.eegVisualizer = VisualizacionElectrodos(
                subjectDir,
                lhModel=mlResult.get("lh"),
                rhModel=mlResult.get("rh")
            )

            if not self.eegVisualizer.ejecutar():
                self.log(
                    "⚠ No se pudieron dibujar los electrodos EEG de "
                    "superficie (ver consola de Python para el detalle)."
                )
                self.eegVisualizer = None
                return

            # Los controles van en el grupo superior del panel ML
            # (siempre visible); si no existe, al final del panel.
            controlsLayout = (
                getattr(self.mlVisualizer, "controlsLayout", None)
                or self.mlVisualizer.resultsLayout
            )

            if controlsLayout is not None:
                self.eegVisualizer.crearControlVisibilidad(
                    controlsLayout
                )
                self.mlVisualizer.mostrarControles()

            self.log(
                "✓ Electrodos EEG de superficie representados: "
                f"{len(self.eegVisualizer._loadedNames)} electrodos."
            )

        except Exception as e:

            self.log(
                f"✗ ERROR EN VISUALIZACIÓN EEG DE SUPERFICIE: {e}"
            )

            import traceback

            self.log(
                traceback.format_exc()
            )

            if self.eegVisualizer is not None:
                try:
                    self.eegVisualizer.cerrar()
                except Exception:
                    pass

            self.eegVisualizer = None

    def iniciarVisualizacionSEEG(self, subjectDir, mlResult):

        """
        Dibuja los electrodos SEEG como barras sobre la corteza si el
        sujeto tiene electrodos/seeg_dipolos.tsv. Un fallo aquí no
        interrumpe la visualización ML.
        """

        seegFile = (
            Path(subjectDir)
            / "electrodos"
            / "seeg_dipolos.tsv"
        )

        if not seegFile.exists():
            self.log(
                "ℹ Sin archivo SEEG: no se dibujan electrodos de profundidad."
            )
            return

        try:

            from visualizacion_electrodos_barra import (
                VisualizacionElectrodosBarra
            )

            self.seegVisualizer = VisualizacionElectrodosBarra(
                subjectDir,
                seegFile,
                lhModel=mlResult.get("lh"),
                rhModel=mlResult.get("rh")
            )

            if not self.seegVisualizer.ejecutar():
                self.log(
                    "⚠ No se pudieron dibujar los electrodos SEEG "
                    "(ver consola de Python para el detalle)."
                )
                self.seegVisualizer = None
                return

            # Los controles van en el grupo superior del panel ML
            # (siempre visible); si no existe, al final del panel.
            controlsLayout = (
                getattr(self.mlVisualizer, "controlsLayout", None)
                or self.mlVisualizer.resultsLayout
            )

            if controlsLayout is not None:
                self.seegVisualizer.crearControlVisibilidad(
                    controlsLayout
                )
                self.mlVisualizer.mostrarControles()

            # Corteza más translúcida para ver las barras (el control
            # deslizante del panel ML refleja y permite cambiar este valor).
            self.mlVisualizer.establecerOpacidadCorteza(
                self.seegVisualizer.OPACIDAD_CORTEZA
            )

            self.log(
                "✓ Electrodos SEEG representados: "
                f"{len(self.seegVisualizer._listaElectrodos)} electrodos, "
                f"{len(self.seegVisualizer._contactos)} contactos."
            )

        except Exception as e:

            self.log(
                f"✗ ERROR EN VISUALIZACIÓN SEEG: {e}"
            )

            import traceback

            self.log(
                traceback.format_exc()
            )

            if self.seegVisualizer is not None:
                try:
                    self.seegVisualizer.cerrar()
                except Exception:
                    pass

            self.seegVisualizer = None

    def finishPipeline(self, success, cancelado=False):

        # ========================================================
        # DETENER TIMER
        # ========================================================

        if self.timer is not None:

            self.timer.stop()

            self.timer.deleteLater()

            self.timer = None

        if self._inicioPipeline is not None:

            self.elapsedLabel.setText(
                "Duración del procesamiento: "
                f"{formatoDuracion(time.monotonic() - self._inicioPipeline)}"
            )

            self._inicioPipeline = None

        # Paso que falló, según el archivo de estado ("ERROR: <script>").
        pasoFallido = None

        currentFile = getattr(self, "currentFile", None)

        if not success and currentFile is not None and currentFile.exists():

            try:
                texto = currentFile.read_text(encoding="utf-8").strip()
            except Exception:
                texto = ""

            if texto.startswith("ERROR: "):
                pasoFallido = texto[len("ERROR: "):]


        # ========================================================
        # ÉXITO
        # ========================================================

        if success:

            self.progressBar.value = (
                self.totalSteps
            )

            self.progressLabel.setText(
                f"{self.totalSteps} / "
                f"{self.totalSteps} pasos"
            )

            self.statusLabel.setText(
                "Estado: pipeline completado correctamente"
            )

            self.log(
                ""
            )

            self.log(
                "=" * 70
            )

            self.log(
                "✓ PIPELINE COMPLETADO CORRECTAMENTE"
            )

            self.log(
                "=" * 70
            )


            # ----------------------------------------------------
            # COMPROBAR RESULTADO FINAL
            # ----------------------------------------------------

            if self.currentSubjectDir:

                lhPial = (
                    self.currentSubjectDir /
                    "surf" /
                    "lh.pial"
                )

                rhPial = (
                    self.currentSubjectDir /
                    "surf" /
                    "rh.pial"
                )

                self.log(
                    ""
                )

                self.log(
                    "Superficies pial requeridas:"
                )

                self.log(
                    str(lhPial)
                )

                self.log(
                    str(rhPial)
                )

                if lhPial.exists() and rhPial.exists():

                    self.log(
                        "✓ SUPERFICIES PIAL ENCONTRADAS"
                    )

                    self.statusLabel.setText(
                        "Estado: terminado — superficies pial encontradas"
                    )

                    # ------------------------------------------------
                    # LANZAR LA INFERENCIA Y DESPUÉS LA VISUALIZACIÓN ML
                    # ------------------------------------------------

                    qt.QTimer.singleShot(100, self.iniciarInferenciaML)

                else:

                    self.log(
                        "⚠ El pipeline terminó, "
                        "pero no se encontraron ambas superficies pial."
                    )

                    if not lhPial.exists():
                        self.log(f"   - Falta: {lhPial}")
                    if not rhPial.exists():
                        self.log(f"   - Falta: {rhPial}")


        # ========================================================
        # ERROR
        # ========================================================

        else:

            self.statusLabel.setText(
                "Estado: pipeline cancelado"
                if cancelado
                else "Estado: ERROR en el pipeline"
            )

            self.log(
                ""
            )

            self.log(
                "=" * 70
            )

            self.log(
                "✗ PIPELINE CANCELADO POR EL USUARIO"
                if cancelado
                else "✗ PIPELINE TERMINÓ CON ERROR"
            )

            self.log(
                "=" * 70
            )


        # ========================================================
        # LIBERAR PROCESO
        # ========================================================

        if self.pipelineLogFile is not None:

            try:
                self.pipelineLogFile.close()
            except Exception:
                pass

            self.pipelineLogFile = None

        # Copia del registro junto al paciente, para revisarlo o
        # compartirlo después (el original está en un directorio temporal).
        registroPaciente = None

        logFile = getattr(self, "logFile", None)

        if (
            self.process is not None
            and logFile is not None
            and logFile.exists()
            and self.currentSubjectDir is not None
        ):

            registroPaciente = (
                Path(self.currentSubjectDir) / "registro_pipeline.log"
            )

            try:
                shutil.copy2(logFile, registroPaciente)
                self.log(f"Registro guardado en: {registroPaciente}")
            except Exception:
                registroPaciente = None

        self.process = None

        self._bloquearFormulario(False)

        self.actualizarEstadoFormulario()

        if not success and not cancelado:

            if pasoFallido in DESCRIPCION_PASOS:
                numero = list(DESCRIPCION_PASOS).index(pasoFallido) + 1
                donde = (
                    f"en el paso {numero}/{self.totalSteps}: "
                    f"{DESCRIPCION_PASOS[pasoFallido]} ({pasoFallido})"
                )
                self.statusLabel.setText(
                    f"Estado: ERROR {donde}"
                )
            else:
                donde = "antes de completar FreeSurfer"

            slicer.util.errorDisplay(
                f"El procesamiento se detuvo {donde}.\n\n"
                "Causas frecuentes: imagen T1 de baja calidad o que no es "
                "una T1, licencia de FreeSurfer no válida o falta de "
                "espacio en disco.\n\n"
                + (
                    f"Registro completo:\n{registroPaciente}"
                    if registroPaciente is not None
                    else "El detalle está en «Registro detallado»."
                ),
                windowTitle="Error en el procesamiento"
            )

    # ========================================================
    # CANCELAR PIPELINE
    # ========================================================

    def onCancelPipeline(self):

        if self.process is None:
            return

        if not slicer.util.confirmOkCancelDisplay(
            "¿Cancelar el pipeline?\n\n"
            "Se detendrán los comandos de FreeSurfer en curso y habrá "
            "que volver a ejecutarlo desde el principio."
        ):
            return

        # El timer sigue activo mientras el diálogo está abierto: el
        # pipeline pudo terminar entre tanto.
        if self.process is None:
            return

        self.detenerProceso()

        self.finishPipeline(
            False,
            cancelado=True
        )

    def detenerProceso(self):

        """
        Termina el pipeline y los comandos de FreeSurfer que lanzó. Como
        se inició con start_new_session=True, todos comparten el grupo de
        procesos de pipeline_principal.py.
        """

        if self.process is None or self.process.poll() is not None:
            return

        try:
            os.killpg(self.process.pid, signal.SIGTERM)
        except (AttributeError, ProcessLookupError, PermissionError):
            self.process.terminate()

        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except (AttributeError, ProcessLookupError, PermissionError):
                self.process.kill()
            self.process.wait()

    # ========================================================
    # LIMPIEZA (RELOAD / CIERRE DE SLICER)
    # ========================================================

    def cleanup(self):

        """
        Slicer la llama al recargar el módulo o cerrar la aplicación:
        detiene el pipeline en curso y libera el timer, los observadores
        de la vista 3D, los actores y el panel de resultados.
        """

        if self.timer is not None:
            self.timer.stop()
            self.timer = None

        self.detenerProceso()
        self.process = None

        if self.pipelineLogFile is not None:
            try:
                self.pipelineLogFile.close()
            except Exception:
                pass
            self.pipelineLogFile = None

        for visualizador in (
            self.seegVisualizer,
            self.eegVisualizer,
            self.mlVisualizer
        ):
            if visualizador is not None:
                try:
                    visualizador.cerrar()
                except Exception:
                    pass

        self.seegVisualizer = None
        self.eegVisualizer = None
        self.mlVisualizer = None

        if self._manualDialog is not None:
            try:
                self._manualDialog.close()
                self._manualDialog.deleteLater()
            except Exception:
                pass
            self._manualDialog = None


#
# Test
#

class VisualizacionTest(ScriptedLoadableModuleTest):

    """
    Pruebas que no necesitan FreeSurfer: contrato de pasos con el
    pipeline, inferencia del modelo, lectura de SEEG y cancelación.
    Se ejecutan con "Reload and Test" o con ctest
    (slicer_add_python_unittest en Visualizacion/CMakeLists.txt).
    """

    def setUp(self):

        slicer.mrmlScene.Clear()

        for nombre in ("Inferencia", "VisualizacionML"):

            ruta = str(carpetaExtension(nombre))

            if ruta not in sys.path:
                sys.path.insert(0, ruta)

    def _faltanDependenciasModelo(self):

        """
        True si faltan pandas/scikit-learn/... (p. ej. en los servidores
        que compilan el catálogo de extensiones): los tests del modelo se
        omiten en vez de fallar, porque instalarlos requiere el
        consentimiento del usuario.
        """

        import inferencia_ml

        faltantes = inferencia_ml.dependenciasFaltantes()

        if faltantes:
            logging.warning(
                "Test del modelo omitido; faltan: " + ", ".join(faltantes)
            )

        return bool(faltantes)

    def runTest(self):

        for nombre in sorted(dir(self)):

            if nombre.startswith("test_"):
                self.setUp()
                getattr(self, nombre)()

    def test_totalPasosCoincideConPipeline(self):

        self.delayDisplay("Contrato de pasos con pipeline_principal.py")

        import ast

        pipelineDir = carpetaExtension("Pipeline")

        arbol = ast.parse(
            (pipelineDir / "pipeline_principal.py").read_text(encoding="utf-8")
        )

        orden = next(
            ast.literal_eval(nodo.value)
            for nodo in arbol.body
            if isinstance(nodo, ast.Assign)
            and any(getattr(t, "id", None) == "ORDEN" for t in nodo.targets)
        )

        self.assertEqual(len(orden), TOTAL_PASOS)

        for script in orden:
            self.assertTrue((pipelineDir / script).exists(), script)

        # Cada paso tiene su descripción, en el mismo orden.
        self.assertEqual(list(DESCRIPCION_PASOS), orden)

    def test_formatoDuracion(self):

        self.delayDisplay("Formato del tiempo transcurrido")

        self.assertEqual(formatoDuracion(65), "1 min 05 s")
        self.assertEqual(formatoDuracion(3725), "1 h 02 min 05 s")

        self.assertEqual(
            nombreRegion("Pole_temporal L"),
            "Pole_temporal (hemisferio izquierdo)"
        )
        self.assertEqual(
            nombreRegion("S_calcarine R"),
            "S_calcarine (hemisferio derecho)"
        )

    def test_validarCaracteristicas(self):

        self.delayDisplay("Validación del archivo de características")

        if self._faltanDependenciasModelo():
            return

        import inferencia_ml

        demo = RECURSOS_DIR / "Demo" / "caracteristicas_demo.csv"

        self.assertEqual(inferencia_ml.validarCaracteristicas(demo), 21)

        with tempfile.TemporaryDirectory() as tmp:

            # Faltan columnas sEEG.
            malo = Path(tmp) / "malo.csv"
            malo.write_text(
                "region_destrieux;edad\nPole_temporal L;30\n",
                encoding="utf-8"
            )

            with self.assertRaises(ValueError):
                inferencia_ml.validarCaracteristicas(malo)

            # Columnas correctas, pero sin ninguna región implantada.
            lineas = demo.read_text(encoding="utf-8-sig").splitlines()
            vacio = Path(tmp) / "vacio.csv"
            vacio.write_text(
                "\n".join(
                    [lineas[0]]
                    + [linea.split(";")[0] + ";;;;" for linea in lineas[1:]]
                ),
                encoding="utf-8"
            )

            with self.assertRaises(ValueError):
                inferencia_ml.validarCaracteristicas(vacio)

    def test_botonCerrarManual(self):

        self.delayDisplay("El botón «Cerrar» del manual cierra la ventana")

        widget = slicer.modules.visualizacion.widgetRepresentation().self()

        widget.onAbrirManual()

        dialogo = widget._manualDialog

        self.assertTrue(dialogo.isVisible())

        cerrar = [
            boton
            for boton in dialogo.findChildren(qt.QPushButton)
            if boton.text == "Cerrar"
        ][0]

        cerrar.click()
        slicer.app.processEvents()

        self.assertFalse(dialogo.isVisible())

    def test_rutasConCaracteresPeligrosos(self):

        self.delayDisplay("Rutas que romperían los comandos de FreeSurfer")

        widget = slicer.modules.visualizacion.widgetRepresentation().self()
        anterior = widget.subjectsDirEdit.text

        try:
            widget.subjectsDirEdit.setText('/tmp/pacientes"x')
            self.assertTrue(any(
                "carpeta de resultados contiene" in p
                for p in widget.validarFormulario("completo")
            ))

            widget.subjectsDirEdit.setText("/tmp/pacientes $(whoami)")
            self.assertTrue(any(
                "carpeta de resultados contiene" in p
                for p in widget.validarFormulario("completo")
            ))

            widget.subjectsDirEdit.setText("/tmp/pacientes normales")
            self.assertFalse(any(
                "contiene comillas" in p
                for p in widget.validarFormulario("completo")
            ))
        finally:
            widget.subjectsDirEdit.setText(anterior)

    def test_datosDemostracion(self):

        self.delayDisplay("Datos de demostración")

        from visualizacion_electrodos import (
            VisualizacionElectrodos,
            leerNombresArchivoEEG,
        )
        from visualizacion_electrodos_barra import (
            leerDipolos,
            reconstruirContactos,
        )

        demoDir = RECURSOS_DIR / "Demo"

        nombres = leerNombresArchivoEEG(demoDir / "eeg_superficie_demo.csv")

        self.assertEqual(len(nombres), 19)
        self.assertTrue(
            all(n in VisualizacionElectrodos.STANDARD_1020 for n in nombres)
        )

        electrodos = leerDipolos(demoDir / "seeg_dipolos_demo.tsv")

        self.assertEqual(sorted(electrodos), ["FM", "TM", "TP"])

        for entrada in electrodos.values():
            self.assertEqual(len(reconstruirContactos(entrada)), 10)

    def test_etiquetaYProbabilidadVisual(self):

        self.delayDisplay("Etiquetas y probabilidad visual")

        import inferencia_ml

        self.assertEqual(
            inferencia_ml.etiquetaVisual("G_and_S_frontomargin L"),
            "ctx_lh_G_and_S_frontomargin"
        )
        self.assertEqual(
            inferencia_ml.etiquetaVisual("Pole_occipital R"),
            "ctx_rh_Pole_occipital"
        )

        with self.assertRaises(ValueError):
            inferencia_ml.etiquetaVisual("Pole_occipital")

        self.assertEqual(
            inferencia_ml.probabilidadVisual(inferencia_ml.MARCADA, 0.2, 0.6),
            1.0
        )
        self.assertAlmostEqual(
            inferencia_ml.probabilidadVisual("propagación", 0.3, 0.6),
            0.5
        )
        self.assertEqual(
            inferencia_ml.probabilidadVisual("propagación", float("nan"), 0.6),
            0.0
        )

    def test_inferenciaSujetoSintetico(self):

        self.delayDisplay("Inferencia del modelo sobre un sujeto sintético")

        if self._faltanDependenciasModelo():
            return

        import csv

        import numpy as np

        import inferencia_ml
        import soz_inferencia

        modelo = inferencia_ml.cargarModelo()

        regiones = sorted(
            {region for par in modelo["vecinos"] for region in par}
        )
        columnas = list(
            dict.fromkeys([*soz_inferencia.SEEG, *modelo["features"]])
        )
        implantadas = 40
        rng = np.random.default_rng(0)

        with tempfile.TemporaryDirectory() as tmp:

            sujeto = Path(tmp)
            (sujeto / "caracteristicas").mkdir()

            with (
                sujeto / "caracteristicas" / "caracteristicas_modelo.csv"
            ).open("w", encoding="utf-8", newline="") as archivo:

                escritor = csv.writer(archivo)
                escritor.writerow(["region_destrieux", *columnas])

                for i, region in enumerate(regiones):
                    valores = (
                        [f"{v:.6f}" for v in rng.random(len(columnas))]
                        if i < implantadas
                        else [""] * len(columnas)
                    )
                    escritor.writerow([region, *valores])

            resultado = inferencia_ml.ejecutarInferencia(sujeto)

            self.assertEqual(resultado["n_implantadas"], implantadas)
            self.assertGreater(resultado["n_marcadas"], 0)
            self.assertEqual(len(resultado["marcadas"]), resultado["n_marcadas"])
            self.assertTrue(
                all(r.endswith((" L", " R")) for r in resultado["marcadas"])
            )
            self.assertTrue(resultado["archivo_modelo"].exists())

            with resultado["archivo_visual"].open(
                encoding="utf-8", newline=""
            ) as archivo:
                filas = list(csv.DictReader(archivo))

        self.assertEqual(len(filas), resultado["n_mostradas"])

        probabilidades = [float(fila["probabilidad"]) for fila in filas]

        self.assertTrue(
            all(fila["label"].startswith(("ctx_lh_", "ctx_rh_")) for fila in filas)
        )
        self.assertTrue(all(0.0 < p <= 1.0 for p in probabilidades))
        self.assertEqual(
            sum(p == 1.0 for p in probabilidades),
            resultado["n_marcadas"]
        )

    def test_encuadreParcelaSeleccionada(self):

        self.delayDisplay("Zoom al seleccionar una parcela: cabe entera")

        import math

        from visualizacion_ml import VisualizacionML

        distancia = VisualizacionML._distanciaEncuadre
        tangente = math.tan(math.radians(30.0) / 2.0)

        # Parcela mediana: su diámetro ocupa la mitad de la vista.
        d = distancia(25.0, 30.0, 1.5)
        self.assertAlmostEqual(2 * 25.0 / (2 * d * tangente), 0.5)

        # Vista más alta que ancha: manda el lado horizontal (más lejos).
        self.assertGreater(distancia(25.0, 30.0, 0.7), d)

        # Parcela pequeña: no se acerca más que la distancia mínima.
        self.assertEqual(
            distancia(3.0, 30.0, 1.5), VisualizacionML.DISTANCIA_MINIMA
        )

        # Parcela grande: no se aleja más que la vista general, salvo que
        # no quepa; nunca ocupa más del 90 % de la vista.
        self.assertEqual(distancia(40.0, 30.0, 1.5, 200.0), 200.0)
        d = distancia(70.0, 30.0, 1.5, 200.0)
        self.assertLessEqual(2 * 70.0 / (2 * d * tangente), 0.9 + 1e-9)

    def test_reconstruccionContactosSEEG(self):

        self.delayDisplay("Reconstrucción de contactos SEEG")

        from visualizacion_electrodos_barra import (
            leerDipolos,
            reconstruirContactos,
        )

        with tempfile.TemporaryDirectory() as tmp:

            tsv = Path(tmp) / "seeg_dipolos.tsv"
            tsv.write_text(
                "Channel\tWorld\n"
                "A1-A2\t0 0 1.75\n"
                "A2-A3\t0 0 5.25\n"
                "A3-A4\t0 0 8.75\n"
                "B1\t10 0 0\n"
                "B2\t10 0 3.5\n",
                encoding="utf-8"
            )

            electrodos = leerDipolos(tsv)

        self.assertEqual(sorted(electrodos), ["A", "B"])

        contactosA = reconstruirContactos(electrodos["A"])

        self.assertEqual([n for n, _ in contactosA], [1, 2, 3, 4])

        for (_, punto), z in zip(contactosA, [0.0, 3.5, 7.0, 10.5]):
            self.assertAlmostEqual(float(punto[2]), z)

        self.assertEqual(len(reconstruirContactos(electrodos["B"])), 2)

    def test_cancelarDetieneProcesosHijos(self):

        self.delayDisplay("Cancelar detiene el pipeline y sus hijos")

        if not hasattr(os, "killpg"):
            return

        import time
        import types

        with tempfile.TemporaryDirectory() as tmp:

            pidFile = Path(tmp) / "hijo.pid"

            # Como pipeline_principal.py: un proceso en sesión propia que
            # lanza un hijo de larga duración (el comando de FreeSurfer).
            proceso = subprocess.Popen(
                ["bash", "-c", f'sleep 60 & echo $! > "{pidFile}"; wait'],
                start_new_session=True
            )

            for _ in range(50):
                if pidFile.exists() and pidFile.read_text().strip():
                    break
                time.sleep(0.1)

            hijo = int(pidFile.read_text())

            VisualizacionWidget.detenerProceso(
                types.SimpleNamespace(process=proceso)
            )

        self.assertIsNotNone(proceso.poll())

        for _ in range(50):
            try:
                os.kill(hijo, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            self.fail(f"El proceso hijo {hijo} sigue vivo tras cancelar.")
