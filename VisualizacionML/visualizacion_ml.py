import csv
from pathlib import Path

import numpy as np
import vtk
from vtk.util.numpy_support import (
    numpy_to_vtk,
    numpy_to_vtkIdTypeArray,
    vtk_to_numpy,
)

import qt
import slicer


try:
    import nibabel as nib
except ImportError:
    nib = None


# Mezcla con blanco aplicada al mapa de calor: 0 = colores originales,
# 1 = blanco. Con 0.45 se conservan los mismos tonos pero más suaves.
ACLARADO_MAPA_CALOR = 0.45


def _aclararColor(color, factor=ACLARADO_MAPA_CALOR):
    return tuple(c + (1.0 - c) * factor for c in color)


class VisualizacionML:
    """
    Visualización 3D exclusivamente de la corteza cerebral
    utilizando las superficies reales generadas por FreeSurfer.

    Corteza:
        surf/lh.pial
        surf/rh.pial

    Parcellación Destrieux:
        label/lh.aparc.a2009s.annot
        label/rh.aparc.a2009s.annot

    Resultado ML:
        predicciones_epileptogenicidad.csv

    Las regiones corticales no presentes en la tabla ML
    se muestran en gris.

    Las regiones presentes en la tabla ML se colorean
    según su probabilidad de epileptogenicidad.

    Por ahora no se representan estructuras subcorticales.
    """

    def __init__(self, subjectDir, freesurferHome):

        self.subjectDir = Path(subjectDir)
        # Puede ser None al visualizar un paciente ya procesado.
        self.freesurferHome = (
            Path(freesurferHome) if freesurferHome else None
        )

        # ----------------------------------------------------------
        # Superficies corticales
        # ----------------------------------------------------------

        self.lhPialFile = (
            self.subjectDir
            / "surf"
            / "lh.pial"
        )

        self.rhPialFile = (
            self.subjectDir
            / "surf"
            / "rh.pial"
        )

        # ----------------------------------------------------------
        # Anotaciones Destrieux
        # ----------------------------------------------------------

        self.lhAnnotFile = (
            self.subjectDir
            / "label"
            / "lh.aparc.a2009s.annot"
        )

        self.rhAnnotFile = (
            self.subjectDir
            / "label"
            / "rh.aparc.a2009s.annot"
        )

        # ----------------------------------------------------------
        # Predicciones ML
        # ----------------------------------------------------------

        self.predictionsFile = (
            self.subjectDir
            / "predicciones_epileptogenicidad.csv"
        )

        self.lhModel = None
        self.rhModel = None

        # Modelos independientes de las regiones ML.
        # Cada región predicha tendrá su propia superficie con un
        # único color. Esto evita que Slicer aplique una LUT a toda
        # la corteza y garantiza que solo las parcelas predichas
        # queden coloreadas.
        self.mlModels = []

        # ----------------------------------------------------------
        # Control de resultados mediante tabla
        # ----------------------------------------------------------
        self.tableRows = []
        self.selectedMLNode = None
        self.resultsDockWidget = None
        self.resultsLayout = None
        self.controlsGroup = None
        self.controlsLayout = None
        self.opacitySlider = None
        self.opacityValueLabel = None
        self.resultsTable = None
        self.regionInfoLabel = None
        self.clearSelectionButton = None
        self._changingTableSelection = False
        self._savedCameraState = None
        self._baseExteriorCameraState = None

        self.predicciones = {}


    # ==============================================================
    # LECTURA DEL CSV
    # ==============================================================

    def leerPredicciones(self):
        """
        Lee:

        label,probabilidad
        ctx_lh_G_and_S_frontomargin,0.87
        ctx_lh_G_and_S_occipital_inf,0.12
        ...

        Solo se aceptan etiquetas corticales Destrieux.
        """

        if not self.predictionsFile.exists():

            raise FileNotFoundError(
                "No se encontró el archivo de predicciones ML:\n"
                f"{self.predictionsFile}"
            )

        predicciones = {}

        with self.predictionsFile.open(
            "r",
            encoding="utf-8-sig",
            newline=""
        ) as archivo:

            lector = csv.DictReader(archivo)

            if lector.fieldnames is None:

                raise ValueError(
                    "El archivo CSV está vacío."
                )

            if "label" not in lector.fieldnames:

                raise ValueError(
                    "El archivo debe contener la columna "
                    "'label'."
                )

            if "probabilidad" not in lector.fieldnames:

                raise ValueError(
                    "El archivo debe contener la columna "
                    "'probabilidad'."
                )

            for numeroFila, fila in enumerate(
                lector,
                start=2
            ):

                label = fila["label"].strip()

                if not label:
                    continue

                # --------------------------------------------------
                # Solo cortex Destrieux
                # --------------------------------------------------

                if not (
                    label.startswith("ctx_lh_")
                    or label.startswith("ctx_rh_")
                ):

                    print(
                        f"[ML] Ignorando etiqueta no cortical: "
                        f"{label}"
                    )

                    continue

                try:

                    probabilidad = float(
                        fila["probabilidad"]
                    )

                except (TypeError, ValueError):

                    raise ValueError(
                        f"Probabilidad inválida en la fila "
                        f"{numeroFila}: {label}"
                    )

                if not 0.0 <= probabilidad <= 1.0:

                    raise ValueError(
                        f"La probabilidad de '{label}' "
                        "debe estar entre 0 y 1."
                    )

                predicciones[label] = probabilidad

        if not predicciones:

            raise ValueError(
                "No se encontraron regiones corticales "
                "válidas en el CSV."
            )

        self.predicciones = predicciones

        print(
            f"[ML] Regiones corticales encontradas: "
            f"{len(predicciones)}"
        )

        return predicciones

    # ==============================================================
    # CREAR COLORES DE SUPERFICIE
    # ==============================================================

    def normalizarNombreAnnotation(
        self,
        nombre,
        hemisferio
    ):
        """
        Normaliza el nombre de una región Destrieux del .annot.

        Ejemplo:
            ANNOT: G_and_S_paracentral
            CSV:   ctx_lh_G_and_S_paracentral
        """

        if isinstance(nombre, bytes):
            nombre = nombre.decode(
                "utf-8",
                errors="ignore"
            )

        nombre = str(nombre).strip()

        if nombre.startswith("ctx_lh_"):
            nombre = nombre[7:]

        elif nombre.startswith("ctx_rh_"):
            nombre = nombre[7:]

        return nombre

    # ==============================================================
    # CREAR SUPERFICIE BASE GRIS
    # ==============================================================

    def prepararSuperficieBaseGris(
        self,
        modelNode
    ):
        """
        La superficie pial completa se muestra uniformemente en gris.

        No se utilizan escalares ni LUT para la superficie base.
        """

        displayNode = (
            modelNode.GetDisplayNode()
        )

        if displayNode is None:

            modelNode.CreateDefaultDisplayNodes()

            displayNode = (
                modelNode.GetDisplayNode()
            )

        displayNode.SetScalarVisibility(
            False
        )

        displayNode.SetColor(
            0.70,
            0.70,
            0.70
        )

        displayNode.SetOpacity(
            0.7
        )

        displayNode.SetVisibility3D(
            True
        )

        displayNode.BackfaceCullingOff()

    # ==============================================================
    # COLOR SEGÚN PROBABILIDAD
    # ==============================================================

    def colorPorProbabilidad(
        self,
        probabilidad
    ):
        """
        Convierte una probabilidad [0,1] en RGB mediante un
        mapa de calor continuo:

            0.0  -> gris
            0.25 -> amarillo
            0.55 -> naranja
            1.0  -> rojo

        La transición es continua para que diferencias pequeñas
        entre probabilidades también produzcan diferencias suaves
        de color.
        """

        probabilidad = max(0.0, min(1.0, float(probabilidad)))

        # Puntos de control del mapa de calor.
        # RGB normalizado [0,1].
        puntos = [
            (0.00, (0.55, 0.55, 0.55)),  # gris
            (0.25, (1.00, 0.92, 0.00)),  # amarillo
            (0.55, (1.00, 0.55, 0.00)),  # naranja
            (1.00, (0.90, 0.00, 0.00)),  # rojo
        ]

        for i in range(len(puntos) - 1):
            p0, c0 = puntos[i]
            p1, c1 = puntos[i + 1]

            if probabilidad <= p1:
                t = (probabilidad - p0) / (p1 - p0)
                return _aclararColor(tuple(
                    c0[j] + t * (c1[j] - c0[j])
                    for j in range(3)
                ))

        return _aclararColor(puntos[-1][1])

    # ==============================================================
    # COLOR GRIS
    # ==============================================================

    def colorGris(self):

        return (
            0.70,
            0.70,
            0.70
        )

    # ==============================================================
    # LEER ANNOTATION DE FREESURFER
    # ==============================================================

    def leerAnnotation(
        self,
        annotFile
    ):
        """
        Lee un archivo .annot de FreeSurfer.

        Devuelve:
            labels
            nombres

        Cada vértice de la superficie tiene asociado
        un índice de región.
        """

        if nib is None:

            raise ImportError(
                "No está instalado nibabel en el Python de Slicer.\n\n"
                "Ejecuta en la consola Python de Slicer:\n\n"
                "slicer.util.pip_install('nibabel')"
            )

        if not annotFile.exists():

            raise FileNotFoundError(
                "No se encontró la anotación:\n"
                f"{annotFile}"
            )

        (
            labels,
            colorTable,
            names
        ) = nib.freesurfer.io.read_annot(
            str(annotFile),
            orig_ids=False
        )

        nombres = []

        for nombre in names:

            if isinstance(
                nombre,
                bytes
            ):

                nombre = nombre.decode(
                    "utf-8",
                    errors="ignore"
                )

            nombres.append(
                str(nombre)
            )

        print(
            f"[ANNOT] {annotFile.name}: "
            f"{len(nombres)} etiquetas"
        )

        return (
            labels,
            nombres
        )

    # ==============================================================
    # SEPARAR VISUALMENTE EL OVERLAY DE LA SUPERFICIE BASE
    # ==============================================================

    def desplazarOverlaySobreSuperficie(
        self,
        vertices,
        normals,
        distancia=0.30
    ):
        """Desplaza vértices según sus normales usando NumPy."""
        vertices = np.asarray(vertices, dtype=np.float32)
        normals = np.asarray(normals, dtype=np.float32)

        if vertices.shape != normals.shape:
            raise RuntimeError(
                "Los vértices y las normales no tienen la misma forma."
            )

        return vertices + (float(distancia) * normals)

    # ==============================================================
    # CREAR OVERLAYS ML POR REGIÓN
    # ==============================================================

    def crearOverlaysML(
        self,
        modelNode,
        labels,
        names,
        hemisferio
    ):
        """
        Crea un modelo independiente para cada región predicha.

        La extracción de caras se realiza con NumPy y las estructuras
        VTK se construyen en bloque. Esto evita recorrer cientos de
        miles de caras mediante llamadas Python/VTK.
        """

        polyData = modelNode.GetPolyData()

        if polyData is None:
            raise RuntimeError(
                f"La superficie {modelNode.GetName()} no contiene geometría."
            )

        numeroVertices = polyData.GetNumberOfPoints()

        if numeroVertices != len(labels):
            raise RuntimeError(
                "La cantidad de vértices no coincide con el ANNOT.\n"
                f"Superficie: {numeroVertices}\n"
                f"ANNOT: {len(labels)}"
            )

        vertices = vtk_to_numpy(
            polyData.GetPoints().GetData()
        ).astype(np.float32, copy=False)

        rawCells = vtk_to_numpy(
            polyData.GetPolys().GetData()
        )

        if rawCells.size % 4 != 0:
            raise RuntimeError(
                "La malla cortical no tiene una representación triangular válida."
            )

        faces = rawCells.reshape((-1, 4))[:, 1:4].astype(
            np.int64,
            copy=False
        )

        labelsArray = np.asarray(labels)

        # Calcular normales una sola vez por hemisferio.
        normalsFilter = vtk.vtkPolyDataNormals()
        normalsFilter.SetInputData(polyData)
        normalsFilter.ComputePointNormalsOn()
        normalsFilter.ComputeCellNormalsOff()
        normalsFilter.ConsistencyOn()
        normalsFilter.SplittingOff()
        normalsFilter.Update()

        normalsOutput = normalsFilter.GetOutput()
        normalArray = normalsOutput.GetPointData().GetNormals()

        if normalArray is None:
            raise RuntimeError(
                "No fue posible calcular las normales de la corteza."
            )

        normals = vtk_to_numpy(normalArray).astype(
            np.float32,
            copy=False
        )

        prefijo = (
            "ctx_lh_"
            if hemisferio.lower() == "lh"
            else "ctx_rh_"
        )

        prediccionesHemisferio = {
            label[len(prefijo):]: probabilidad
            for label, probabilidad in self.predicciones.items()
            if label.startswith(prefijo)
        }

        print(
            f"[ML] Predicciones {hemisferio.upper()}: "
            f"{len(prediccionesHemisferio)}"
        )

        if not prediccionesHemisferio:
            return []

        indicesPorNombre = {}
        for indice, nombre in enumerate(names):
            nombreNormalizado = self.normalizarNombreAnnotation(
                nombre,
                hemisferio
            )
            indicesPorNombre[nombreNormalizado] = indice

        overlays = []
        regionesEncontradas = 0

        for nombreRegion, probabilidad in sorted(
            prediccionesHemisferio.items()
        ):
            if nombreRegion not in indicesPorNombre:
                print(
                    f"[ML] ADVERTENCIA: {prefijo}{nombreRegion} "
                    "no se encontró en el ANNOT."
                )
                continue

            indiceRegion = indicesPorNombre[nombreRegion]

            # ------------------------------------------------------
            # Asignación de triángulos a regiones.
            #
            # La versión anterior exigía que los tres vértices del
            # triángulo pertenecieran a la misma parcela. En los
            # límites entre regiones esto deja caras sin asignar y la
            # superficie gris de fondo queda visible como pequeños
            # huecos.
            #
            # Aquí cada triángulo se asigna a una única región usando
            # la mayoría de sus tres etiquetas. Si las tres son
            # diferentes (caso muy puntual en una frontera), se usa
            # de forma determinista la etiqueta del tercer vértice.
            # De esta forma no se descartan las caras de frontera.
            # ------------------------------------------------------
            faceLabels = labelsArray[faces]
            v0 = faceLabels[:, 0]
            v1 = faceLabels[:, 1]
            v2 = faceLabels[:, 2]

            faceRegionLabels = np.where(
                v0 == v1,
                v0,
                np.where(v0 == v2, v0, v2)
            )

            mask = faceRegionLabels == indiceRegion
            regionFacesOld = faces[mask]

            if regionFacesOld.size == 0:
                print(
                    f"[ML] ADVERTENCIA: no se pudieron extraer caras "
                    f"para {nombreRegion}."
                )
                continue

            # Compactar los índices de vértices.
            uniqueVertices, inverse = np.unique(
                regionFacesOld.reshape(-1),
                return_inverse=True
            )

            regionFaces = inverse.reshape((-1, 3)).astype(
                np.int64,
                copy=False
            )

            regionVertices = vertices[uniqueVertices]
            regionNormals = normals[uniqueVertices]

            # Separación de 0.30 mm para evitar z-fighting.
            regionVertices = self.desplazarOverlaySobreSuperficie(
                regionVertices,
                regionNormals,
                distancia=0.30
            )

            # Construcción VTK en bloque.
            points = vtk.vtkPoints()
            points.SetData(
                numpy_to_vtk(
                    np.ascontiguousarray(regionVertices),
                    deep=True,
                    array_type=vtk.VTK_FLOAT
                )
            )

            connectivity = np.ascontiguousarray(
                regionFaces.reshape(-1),
                dtype=np.int64
            )
            offsets = np.arange(
                0,
                connectivity.size + 1,
                3,
                dtype=np.int64
            )

            cellArray = vtk.vtkCellArray()
            cellArray.SetData(
                numpy_to_vtkIdTypeArray(offsets, deep=True),
                numpy_to_vtkIdTypeArray(connectivity, deep=True)
            )

            regionPolyData = vtk.vtkPolyData()
            regionPolyData.SetPoints(points)
            regionPolyData.SetPolys(cellArray)
            regionPolyData.Modified()

            overlayNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLModelNode"
            )

            overlayNode.SetName(
                f"{self.subjectDir.name}_ML_"
                f"{hemisferio.upper()}_"
                f"{nombreRegion}"
            )

            overlayNode.SetAttribute(
                "MLLabel",
                f"{prefijo}{nombreRegion}"
            )
            overlayNode.SetAttribute(
                "MLRegion",
                nombreRegion
            )
            overlayNode.SetAttribute(
                "MLHemisphere",
                hemisferio.upper()
            )
            overlayNode.SetAttribute(
                "MLProbability",
                f"{probabilidad:.6f}"
            )
            overlayNode.SetAttribute(
                "MLVertexCount",
                str(len(uniqueVertices))
            )
            overlayNode.SetAttribute(
                "MLAnnotationIndex",
                str(indiceRegion)
            )

            overlayNode.SetAndObservePolyData(regionPolyData)
            overlayNode.CreateDefaultDisplayNodes()

            displayNode = overlayNode.GetDisplayNode()
            color = self.colorPorProbabilidad(probabilidad)

            displayNode.SetScalarVisibility(False)
            displayNode.SetColor(*color)
            displayNode.SetOpacity(0.7)
            displayNode.SetVisibility3D(True)
            displayNode.BackfaceCullingOff()

            overlays.append(overlayNode)
            regionesEncontradas += 1

            print(
                f"[ML] {hemisferio.upper()} {nombreRegion}: "
                f"probabilidad={probabilidad:.3f}, "
                f"vértices={len(uniqueVertices)}, "
                f"caras={len(regionFaces)}"
            )

        print(
            f"[ML] Regiones {hemisferio.upper()} mostradas: "
            f"{regionesEncontradas}"
        )

        return overlays

    # ==============================================================
    # APLICAR COLORES A SUPERFICIE
    # ==============================================================

    def aplicarColoresSuperficie(
        self,
        modelNode,
        annotFile,
        hemisferio
    ):
        """
        Deja toda la superficie pial en gris y crea encima
        únicamente las regiones que tienen predicción ML.
        """

        (
            labels,
            names
        ) = self.leerAnnotation(
            annotFile
        )

        polyData = (
            modelNode.GetPolyData()
        )

        if polyData is None:
            raise RuntimeError(
                f"La superficie "
                f"{modelNode.GetName()} "
                "no contiene geometría."
            )

        numeroVertices = (
            polyData.GetNumberOfPoints()
        )

        numeroLabels = len(labels)

        print(
            f"[Superficie] "
            f"{modelNode.GetName()}"
        )

        print(
            f"[Superficie] Vértices VTK: "
            f"{numeroVertices}"
        )

        print(
            f"[Superficie] Vértices ANNOT: "
            f"{numeroLabels}"
        )

        if numeroVertices != numeroLabels:

            raise RuntimeError(
                "El número de vértices de la superficie "
                "no coincide con el número de vértices "
                "de la anotación.\n\n"
                f"Superficie: {numeroVertices}\n"
                f"ANNOT: {numeroLabels}"
            )

        # Toda la corteza queda gris.
        self.prepararSuperficieBaseGris(
            modelNode
        )

        # Las regiones ML se crean como modelos independientes.
        overlays = self.crearOverlaysML(
            modelNode,
            labels,
            names,
            hemisferio
        )

        self.mlModels.extend(
            overlays
        )

        print(
            "[Superficie] ✓ Corteza base gris "
            "y overlays ML aplicados."
        )

    # ==============================================================
    # CARGAR SUPERFICIE PIAL
    # ==============================================================

    def cargarSuperficie(
        self,
        surfaceFile,
        nombre
    ):
        """
        Lee una superficie FreeSurfer .pial y construye el vtkPolyData
        evitando bucles Python sobre cientos de miles de elementos.
        """

        if nib is None:
            raise ImportError(
                "No está instalado nibabel en el Python de Slicer.\n\n"
                "Ejecuta en la consola Python de Slicer:\n\n"
                "slicer.util.pip_install('nibabel')"
            )

        surfaceFile = Path(surfaceFile)

        if not surfaceFile.exists():
            raise FileNotFoundError(
                f"No se encontró la superficie:\n{surfaceFile}"
            )

        print(
            f"[Superficie] Cargando {surfaceFile.name}"
        )

        try:
            vertices, faces = nib.freesurfer.io.read_geometry(
                str(surfaceFile)
            )
        except Exception as e:
            raise RuntimeError(
                f"No se pudo leer la superficie FreeSurfer:\n"
                f"{surfaceFile}\n\n"
                f"Error: {e}"
            ) from e

        vertices = np.asarray(vertices, dtype=np.float32)
        faces = np.asarray(faces, dtype=np.int64)

        if vertices.ndim != 2 or vertices.shape[1] != 3:
            raise RuntimeError(
                f"La superficie {surfaceFile.name} no tiene "
                "coordenadas XYZ válidas."
            )

        if faces.ndim != 2 or faces.shape[1] != 3:
            raise RuntimeError(
                f"La superficie {surfaceFile.name} no tiene "
                "triángulos válidos."
            )

        print(
            f"[Superficie] Vértices FreeSurfer: {vertices.shape[0]}"
        )
        print(
            f"[Superficie] Triángulos FreeSurfer: {faces.shape[0]}"
        )

        points = vtk.vtkPoints()
        points.SetData(
            numpy_to_vtk(
                np.ascontiguousarray(vertices),
                deep=True,
                array_type=vtk.VTK_FLOAT
            )
        )

        connectivity = np.ascontiguousarray(
            faces.reshape(-1),
            dtype=np.int64
        )
        offsets = np.arange(
            0,
            connectivity.size + 1,
            3,
            dtype=np.int64
        )

        triangles = vtk.vtkCellArray()
        triangles.SetData(
            numpy_to_vtkIdTypeArray(offsets, deep=True),
            numpy_to_vtkIdTypeArray(connectivity, deep=True)
        )

        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetPolys(triangles)
        polyData.Modified()

        modelNode = slicer.mrmlScene.AddNewNodeByClass(
            "vtkMRMLModelNode",
            nombre
        )
        # Marca la corteza de la extensión para quitarla al visualizar
        # otro paciente (limpiarVisualizacionAnterior).
        modelNode.SetAttribute("MLCorteza", "1")
        modelNode.SetAndObservePolyData(polyData)
        modelNode.CreateDefaultDisplayNodes()

        displayNode = modelNode.GetDisplayNode()
        if displayNode is None:
            raise RuntimeError(
                f"No se pudo crear el nodo de visualización para {nombre}."
            )

        displayNode.SetVisibility3D(True)
        displayNode.SetOpacity(0.7)
        displayNode.BackfaceCullingOff()

        print(
            f"[Superficie] ✓ {nombre} creada correctamente."
        )
        print(
            f"[Superficie] VTK: {polyData.GetNumberOfPoints()} vértices, "
            f"{polyData.GetNumberOfPolys()} triángulos."
        )

        return modelNode

    # ==============================================================
    # CARGAR CORTEZA COMPLETA
    # ==============================================================

    def crearCortezaCompleta(self):
        """
        Carga las superficies pial izquierda y derecha
        y aplica la parcellación Destrieux + ML.
        """

        print("")
        print(
            "=" * 70
        )

        print(
            "CREANDO CORTEZA SOBRE SUPERFICIES FREESURFER"
        )

        print(
            "=" * 70
        )

        # ----------------------------------------------------------
        # Hemisferio izquierdo
        # ----------------------------------------------------------

        self.lhModel = (
            self.cargarSuperficie(
                self.lhPialFile,
                f"{self.subjectDir.name}_LH_Pial"
            )
        )

        self.aplicarColoresSuperficie(
            self.lhModel,
            self.lhAnnotFile,
            "lh"
        )

        # ----------------------------------------------------------
        # Hemisferio derecho
        # ----------------------------------------------------------

        self.rhModel = (
            self.cargarSuperficie(
                self.rhPialFile,
                f"{self.subjectDir.name}_RH_Pial"
            )
        )

        self.aplicarColoresSuperficie(
            self.rhModel,
            self.rhAnnotFile,
            "rh"
        )

        print(
            "[Corteza] ✓ Ambos hemisferios creados."
        )

    # ==============================================================
    # CREAR SUPERFICIES SUBCORTICALES
    # ==============================================================

    # ==============================================================
    # PREPARAR VISTA 3D
    # ==============================================================

    def prepararVista3D(self):
        """
        Cambia a vista 3D y ajusta la cámara.
        """

        layoutManager = (
            slicer.app.layoutManager()
        )

        layoutManager.setLayout(
            slicer.vtkMRMLLayoutNode.SlicerLayoutOneUp3DView
        )

        slicer.util.resetThreeDViews()

        print(
            "[Vista] ✓ Vista 3D preparada."
        )

    # ==============================================================
    # TABLA DE RESULTADOS ML
    # ==============================================================

    def crearPanelResultados(self):
        """Crea el panel lateral de resultados ML."""
        if self.resultsDockWidget is not None:
            return

        self.resultsDockWidget = qt.QDockWidget(
            "Resultados de epileptogenicidad ML",
            slicer.util.mainWindow()
        )
        self.resultsDockWidget.setObjectName(
            "EpileptogenicidadMLResultadosDock"
        )
        self.resultsDockWidget.setMinimumWidth(380)
        self.resultsDockWidget.setAllowedAreas(
            qt.Qt.LeftDockWidgetArea | qt.Qt.RightDockWidgetArea
        )

        container = qt.QWidget()
        layout = qt.QVBoxLayout(container)
        self.resultsLayout = layout

        title = qt.QLabel("Resultados ML — Atlas Destrieux")
        title.setStyleSheet(
            "font-size: 15px; font-weight: bold; padding: 4px;"
        )
        layout.addWidget(title)

        description = qt.QLabel(
            "Regiones corticales predichas por el modelo, "
            "ordenadas de mayor a menor probabilidad visual.\n"
            "Seleccione una fila para enfocar la región en 3D."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addWidget(self._crearLeyenda())

        # Controles de transparencia (y de electrodos, si se cargan), sobre
        # la tabla para que siempre sean visibles.
        self.controlsGroup = qt.QGroupBox("Transparencia")
        self.controlsLayout = qt.QVBoxLayout(self.controlsGroup)

        opacityRow = qt.QHBoxLayout()
        opacityRow.addWidget(qt.QLabel("Opacidad de la corteza:"))
        self.opacitySlider = qt.QSlider(qt.Qt.Horizontal)
        self.opacitySlider.setRange(10, 100)
        self.opacitySlider.setValue(70)
        self.opacitySlider.setMinimumWidth(140)
        self.opacityValueLabel = qt.QLabel("70%")
        self.opacityValueLabel.setMinimumWidth(36)
        self.opacitySlider.valueChanged.connect(
            self._alCambiarOpacidadCorteza
        )
        opacityRow.addWidget(self.opacitySlider, 1)
        opacityRow.addWidget(self.opacityValueLabel)
        self.controlsLayout.addLayout(opacityRow)

        layout.addWidget(self.controlsGroup)

        self.resultsTable = qt.QTableWidget()
        self.resultsTable.setColumnCount(3)
        self.resultsTable.setHorizontalHeaderLabels(
            ["Región", "Hemisferio", "Probabilidad visual"]
        )
        self.resultsTable.setSelectionBehavior(
            qt.QAbstractItemView.SelectRows
        )
        self.resultsTable.setSelectionMode(
            qt.QAbstractItemView.SingleSelection
        )
        self.resultsTable.setEditTriggers(
            qt.QAbstractItemView.NoEditTriggers
        )
        self.resultsTable.setAlternatingRowColors(True)
        self.resultsTable.verticalHeader().setVisible(False)
        self.resultsTable.setSortingEnabled(False)
        self.resultsTable.setMinimumHeight(110)
        self.resultsTable.setMaximumHeight(220)

        header = self.resultsTable.horizontalHeader()
        header.setSectionResizeMode(0, qt.QHeaderView.Stretch)
        header.setSectionResizeMode(1, qt.QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, qt.QHeaderView.ResizeToContents)

        layout.addWidget(self.resultsTable)

        probabilityNote = qt.QLabel(
            "Probabilidad visual: 100% = región clasificada como "
            "epileptogénica por el modelo; valores menores = propagación "
            "hacia regiones vecinas de las clasificadas; gris = sin "
            "relación."
        )
        probabilityNote.setWordWrap(True)
        probabilityNote.setStyleSheet(
            "color: #666666; font-size: 11px;"
        )
        layout.addWidget(probabilityNote)

        self.regionInfoLabel = qt.QLabel(
            "<b>Ninguna región seleccionada.</b><br>"
            "Seleccione una fila de la tabla."
        )
        self.regionInfoLabel.setWordWrap(True)
        self.regionInfoLabel.setMinimumHeight(85)
        self.regionInfoLabel.setStyleSheet(
            "padding: 8px; border: 1px solid #cccccc;"
        )
        layout.addWidget(self.regionInfoLabel)

        self.clearSelectionButton = qt.QPushButton(
            "Quitar selección y restaurar vista"
        )
        self.clearSelectionButton.clicked.connect(
            self.deseleccionarRegion
        )
        layout.addWidget(self.clearSelectionButton)
        layout.addStretch(1)

        self.resultsDockWidget.setWidget(container)

        slicer.util.mainWindow().addDockWidget(
            qt.Qt.RightDockWidgetArea,
            self.resultsDockWidget
        )

        self.resultsTable.itemSelectionChanged.connect(
            self.onRegionTableSelectionChanged
        )

    def _crearLeyenda(self):
        """
        Barra con el mapa de calor de colorPorProbabilidad, para leer el
        color de cada región en la vista 3D.
        """
        def hexColor(probabilidad):
            r, g, b = self.colorPorProbabilidad(probabilidad)
            return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"

        paradas = ", ".join(
            f"stop:{p} {hexColor(p)}" for p in (0.0, 0.25, 0.55, 1.0)
        )

        leyenda = qt.QWidget()
        leyendaLayout = qt.QVBoxLayout(leyenda)
        leyendaLayout.setContentsMargins(4, 0, 4, 0)
        leyendaLayout.setSpacing(2)

        leyendaLayout.addWidget(qt.QLabel("<b>Leyenda: probabilidad visual</b>"))

        barra = qt.QLabel()
        barra.setFixedHeight(14)
        barra.setStyleSheet(
            "border: 1px solid #999999; background: qlineargradient("
            f"x1:0, y1:0, x2:1, y2:0, {paradas});"
        )
        barra.setToolTip(
            "Color de cada región en la vista 3D según su probabilidad visual."
        )
        leyendaLayout.addWidget(barra)

        marcas = qt.QHBoxLayout()
        for texto in ("0%", "50%", "100% (epileptogénica)"):
            marca = qt.QLabel(texto)
            marca.setStyleSheet("font-size: 11px;")
            marcas.addWidget(marca)
            if texto != "100% (epileptogénica)":
                marcas.addStretch(1)
        leyendaLayout.addLayout(marcas)

        gris = qt.QLabel(
            "Gris: región sin relación con las clasificadas como "
            "epileptogénicas."
        )
        gris.setStyleSheet("color: #666666; font-size: 11px;")
        leyendaLayout.addWidget(gris)

        return leyenda

    def mostrarPanel(self):
        """Vuelve a mostrar el panel de resultados si el usuario lo cerró."""
        if self.resultsDockWidget is None:
            return
        self.resultsDockWidget.show()
        try:
            self.resultsDockWidget.raise_()
        except Exception:
            pass

    def mostrarControles(self):
        """
        Se llama cuando un visualizador de electrodos añadió sus controles:
        el título del grupo pasa a mencionar los electrodos.
        """
        if getattr(self, "controlsGroup", None) is not None:
            self.controlsGroup.setTitle("Transparencia y electrodos")
            self.controlsGroup.setVisible(True)

    def _alCambiarOpacidadCorteza(self, valor):
        """Aplica la opacidad a la corteza y a las regiones coloreadas."""
        if getattr(self, "opacityValueLabel", None) is not None:
            self.opacityValueLabel.setText(f"{int(valor)}%")

        for nodo in [self.lhModel, self.rhModel] + list(self.mlModels):
            try:
                display = nodo.GetDisplayNode()
                if display is not None:
                    display.SetOpacity(float(valor) / 100.0)
            except Exception:
                pass

    def establecerOpacidadCorteza(self, opacidad):
        """Mueve el control deslizante (y aplica el valor, 0-1)."""
        slider = getattr(self, "opacitySlider", None)
        if slider is not None:
            slider.setValue(int(round(float(opacidad) * 100)))
        else:
            self._alCambiarOpacidadCorteza(float(opacidad) * 100)

    def poblarTablaResultados(self):
        """Carga las predicciones corticales ordenadas de mayor a menor."""
        if self.resultsTable is None:
            return

        predictions = []

        for node in self.mlModels:
            probabilityText = node.GetAttribute("MLProbability")
            region = node.GetAttribute("MLRegion")
            hemisphere = node.GetAttribute("MLHemisphere")

            if probabilityText is None:
                continue

            try:
                probability = float(probabilityText)
            except (TypeError, ValueError):
                continue

            predictions.append({
                "node": node,
                "region": region or node.GetName(),
                "hemisphere": hemisphere or "—",
                "probability": probability,
            })

        predictions.sort(
            key=lambda item: item["probability"],
            reverse=True
        )
        self.tableRows = predictions

        self.resultsTable.blockSignals(True)
        self.resultsTable.setRowCount(0)

        for item in predictions:
            row = self.resultsTable.rowCount
            self.resultsTable.insertRow(row)

            regionItem = qt.QTableWidgetItem(item["region"])
            hemisphereItem = qt.QTableWidgetItem(
                self._hemisphereTexto(item["hemisphere"])
            )
            probabilityItem = qt.QTableWidgetItem(
                f"{item['probability'] * 100:.1f}%"
            )
            probabilityItem.setTextAlignment(qt.Qt.AlignCenter)

            regionItem.setToolTip(
                f"{item['node'].GetAttribute('MLLabel') or item['region']}\n"
                "Clic para enfocar la región en la vista 3D."
            )

            # Referencia directa al MRML node, evitando cualquier picking 3D.
            regionItem.setData(
                qt.Qt.UserRole,
                item["node"].GetID()
            )

            # Muestra del color utilizado en el cerebro.
            displayNode = item["node"].GetDisplayNode()
            if displayNode is not None:
                try:
                    r, g, b = displayNode.GetColor()
                    regionItem.setBackground(
                        qt.QColor(
                            int(r * 255),
                            int(g * 255),
                            int(b * 255)
                        )
                    )
                except Exception:
                    pass

            self.resultsTable.setItem(row, 0, regionItem)
            self.resultsTable.setItem(row, 1, hemisphereItem)
            self.resultsTable.setItem(row, 2, probabilityItem)

        self.resultsTable.blockSignals(False)

    def _hemisphereTexto(self, hemisphere):
        return {
            "lh": "Izquierdo",
            "rh": "Derecho",
            "LH": "Izquierdo",
            "RH": "Derecho",
        }.get(hemisphere, hemisphere)

    def onRegionTableSelectionChanged(self):
        """Procesa la selección de una fila."""
        if self._changingTableSelection:
            return

        selectedRows = self.resultsTable.selectionModel().selectedRows()

        if not selectedRows:
            self.deseleccionarRegion()
            return

        row = selectedRows[0].row()
        if row < 0 or row >= len(self.tableRows):
            return

        self.seleccionarRegion(self.tableRows[row]["node"])

    def _guardarEstadoCamara(self):
        """Guarda la cámara actual para poder restaurarla al deseleccionar."""
        threeDView = self._obtenerThreeDView()
        if threeDView is None:
            return

        try:
            renderer = (
                threeDView.renderWindow()
                .GetRenderers()
                .GetFirstRenderer()
            )
            if renderer is None:
                return

            camera = renderer.GetActiveCamera()
            self._savedCameraState = {
                "position": list(camera.GetPosition()),
                "focalPoint": list(camera.GetFocalPoint()),
                "viewUp": list(camera.GetViewUp()),
                "parallelScale": camera.GetParallelScale(),
                "viewAngle": camera.GetViewAngle(),
                "clippingRange": list(camera.GetClippingRange()),
            }
        except Exception:
            self._savedCameraState = None

    def _obtenerEstadoCamaraActual(self):
        threeDView = self._obtenerThreeDView()
        if threeDView is None:
            return None
        try:
            renderer = threeDView.renderWindow().GetRenderers().GetFirstRenderer()
            if renderer is None:
                return None
            camera = renderer.GetActiveCamera()
            return {
                "position": list(camera.GetPosition()),
                "focalPoint": list(camera.GetFocalPoint()),
                "viewUp": list(camera.GetViewUp()),
                "parallelScale": camera.GetParallelScale(),
                "viewAngle": camera.GetViewAngle(),
                "clippingRange": list(camera.GetClippingRange()),
            }
        except Exception:
            return None

    def _guardarVistaExteriorBase(self):
        """Guarda una vista exterior estable del cerebro completo."""
        threeDView = self._obtenerThreeDView()
        if threeDView is None:
            return
        try:
            renderer = threeDView.renderWindow().GetRenderers().GetFirstRenderer()
            if renderer is None:
                return
            camera = renderer.GetActiveCamera()
            self._baseExteriorCameraState = {
                "position": list(camera.GetPosition()),
                "focalPoint": list(camera.GetFocalPoint()),
                "viewUp": list(camera.GetViewUp()),
                "parallelScale": camera.GetParallelScale(),
                "viewAngle": camera.GetViewAngle(),
                "clippingRange": list(camera.GetClippingRange()),
            }
        except Exception:
            self._baseExteriorCameraState = None

    def _restaurarVistaExteriorBase(self):
        """Restaura la vista exterior estable usada como referencia para el enfoque."""
        state = getattr(self, "_baseExteriorCameraState", None)
        threeDView = self._obtenerThreeDView()
        if not state or threeDView is None:
            return False
        try:
            renderer = threeDView.renderWindow().GetRenderers().GetFirstRenderer()
            if renderer is None:
                return False
            camera = renderer.GetActiveCamera()
            camera.SetPosition(*state["position"])
            camera.SetFocalPoint(*state["focalPoint"])
            camera.SetViewUp(*state["viewUp"])
            camera.SetParallelScale(state["parallelScale"])
            camera.SetViewAngle(state["viewAngle"])
            camera.SetClippingRange(*state["clippingRange"])
            renderer.ResetCameraClippingRange()
            threeDView.forceRender()
            return True
        except Exception as e:
            print(f"[Tabla ML] No se pudo restaurar la vista exterior: {e}")
            return False

    def seleccionarRegion(self, node):
        """Selecciona una región y la enfoca siempre partiendo de la vista exterior base."""
        if node is None:
            return

        if self.selectedMLNode is None:
            self._guardarEstadoCamara()

        self.selectedMLNode = node

        for mlNode in self.mlModels:
            displayNode = mlNode.GetDisplayNode()
            if displayNode is not None:
                displayNode.SetVisibility(mlNode == node)

        for baseNode in (self.lhModel, self.rhModel):
            if baseNode is not None and baseNode.GetDisplayNode() is not None:
                baseNode.GetDisplayNode().SetVisibility(True)

        self.actualizarInformacionRegion(node)

        # Nunca usamos como punto de partida la cámara que el usuario
        # haya dejado dentro/cerca del cerebro. Primero volvemos a una
        # referencia exterior y luego enfocamos la región.
        self._restaurarVistaExteriorBase()
        self.enfocarRegion(node)

    def actualizarInformacionRegion(self, node):
        """Muestra los datos de la región seleccionada."""
        region = node.GetAttribute("MLRegion") or node.GetName()
        hemisphere = node.GetAttribute("MLHemisphere") or "—"
        probabilityText = node.GetAttribute("MLProbability") or "—"
        vertexCount = node.GetAttribute("MLVertexCount") or "—"
        annotationIndex = node.GetAttribute("MLAnnotationIndex") or "—"

        try:
            probabilityFormatted = f"{float(probabilityText) * 100:.1f}%"
        except (TypeError, ValueError):
            probabilityFormatted = probabilityText

        self.regionInfoLabel.setText(
            f"<b>Región seleccionada</b><br><br>"
            f"<b>Destrieux:</b> {region}<br>"
            f"<b>Hemisferio:</b> {self._hemisphereTexto(hemisphere)}<br>"
            f"<b>Probabilidad visual:</b> {probabilityFormatted}<br>"
            f"<b>Vértices:</b> {vertexCount}<br>"
            f"<b>Índice de anotación:</b> {annotationIndex}"
        )

    def deseleccionarRegion(self):
        """Quita la selección, muestra todas las regiones y restaura la vista del usuario."""
        if getattr(self, "_changingTableSelection", False):
            return

        self.selectedMLNode = None

        for mlNode in self.mlModels:
            displayNode = mlNode.GetDisplayNode()
            if displayNode is not None:
                displayNode.SetVisibility(True)

        if self.regionInfoLabel is not None:
            self.regionInfoLabel.setText(
                "<b>Ninguna región seleccionada.</b><br>"
                "Seleccione una fila de la tabla."
            )

        if self.resultsTable is not None:
            self._changingTableSelection = True
            try:
                self.resultsTable.clearSelection()
            finally:
                self._changingTableSelection = False

        self._restaurarEstadoCamara()

    def _restaurarEstadoCamara(self):
        """Restaura la cámara que tenía el usuario antes de seleccionar una región."""
        state = getattr(self, "_savedCameraState", None)
        if not state:
            return

        threeDView = self._obtenerThreeDView()
        if threeDView is None:
            return

        try:
            renderer = threeDView.renderWindow().GetRenderers().GetFirstRenderer()
            if renderer is None:
                return

            camera = renderer.GetActiveCamera()
            camera.SetPosition(*state["position"])
            camera.SetFocalPoint(*state["focalPoint"])
            camera.SetViewUp(*state["viewUp"])
            camera.SetParallelScale(state["parallelScale"])
            camera.SetViewAngle(state["viewAngle"])
            camera.SetClippingRange(*state["clippingRange"])

            renderer.ResetCameraClippingRange()
            threeDView.forceRender()

        except Exception as e:
            print(f"[Tabla ML] No se pudo restaurar la cámara: {e}")

        self._savedCameraState = None

    def enfocarRegion(self, node):
        """Enfoca una región desde el exterior usando la dirección de su superficie."""
        polyData = node.GetPolyData()
        if polyData is None or polyData.GetNumberOfPoints() == 0:
            return

        points = vtk_to_numpy(polyData.GetPoints().GetData()).astype(np.float64, copy=False)
        # Centro de la caja envolvente: en parcelas curvas (giros largos) la
        # media de los puntos cae dentro de la curva y la descentra.
        center = (points.min(axis=0) + points.max(axis=0)) / 2.0

        # Obtener normales de la región. Las normales apuntan hacia el exterior
        # de la corteza; su promedio proporciona una dirección de observación
        # estable y evita depender de la cámara previa del usuario.
        normalsFilter = vtk.vtkPolyDataNormals()
        normalsFilter.SetInputData(polyData)
        normalsFilter.ComputePointNormalsOn()
        normalsFilter.ComputeCellNormalsOff()
        normalsFilter.ConsistencyOn()
        normalsFilter.SplittingOff()
        normalsFilter.Update()
        normalArray = normalsFilter.GetOutput().GetPointData().GetNormals()

        if normalArray is not None and normalArray.GetNumberOfTuples() > 0:
            normals = vtk_to_numpy(normalArray).astype(np.float64, copy=False)
            outward = np.mean(normals, axis=0)
        else:
            outward = np.zeros(3, dtype=np.float64)

        norm = np.linalg.norm(outward)
        if norm < 1e-8:
            # Respaldo: dirección desde el centro del hemisferio hacia la región.
            baseNode = self.lhModel if node.GetAttribute("MLHemisphere") == "LH" else self.rhModel
            if baseNode is not None and baseNode.GetPolyData() is not None:
                basePoints = vtk_to_numpy(baseNode.GetPolyData().GetPoints().GetData()).astype(np.float64, copy=False)
                baseCenter = np.mean(basePoints, axis=0)
                outward = center - baseCenter
                norm = np.linalg.norm(outward)

        if norm < 1e-8:
            outward = np.array([0.0, 0.0, 1.0], dtype=np.float64)
            norm = 1.0

        outward /= norm

        threeDView = self._obtenerThreeDView()
        if threeDView is None:
            return
        renderer = threeDView.renderWindow().GetRenderers().GetFirstRenderer()
        if renderer is None:
            return

        camera = renderer.GetActiveCamera()

        # La cámara está en la vista exterior base (seleccionarRegion la
        # restaura antes de enfocar): su distancia es la de la vista general.
        radius = float(np.linalg.norm(points - center, axis=1).max())
        distance = self._distanciaEncuadre(
            radius,
            camera.GetViewAngle(),
            renderer.GetTiledAspectRatio(),
            camera.GetDistance()
        )
        cameraPosition = center + outward * distance

        camera.SetPosition(*cameraPosition.tolist())
        camera.SetFocalPoint(*center.tolist())

        # Conservamos un ViewUp estable de la vista exterior para evitar giros bruscos.
        baseState = getattr(self, "_baseExteriorCameraState", None)
        if baseState:
            camera.SetViewUp(*baseState["viewUp"])

        camera.SetClippingRange(max(0.1, distance * 0.01), max(3000.0, distance * 20.0))
        renderer.ResetCameraClippingRange()
        threeDView.forceRender()

    # Fracción del lado más estrecho de la vista 3D que ocupa la parcela
    # enfocada: el resto muestra la corteza de alrededor como contexto.
    FRACCION_ENCUADRE = 0.5
    # Fracción máxima: la parcela siempre cabe entera, con margen.
    FRACCION_MAXIMA = 0.9
    # Distancia mínima (mm): las parcelas pequeñas no se ven de tan cerca
    # que se pierda dónde están en el cerebro.
    DISTANCIA_MINIMA = 150.0

    @classmethod
    def _distanciaEncuadre(cls, radio, anguloVista, aspecto, distanciaVistaGeneral=None):
        """
        Distancia de la cámara al centro de una parcela de radio `radio` (mm)
        para que su diámetro ocupe FRACCION_ENCUADRE del lado más estrecho
        de la vista. anguloVista es el ángulo vertical de la cámara (grados)
        y aspecto, ancho/alto de la vista: si es más alta que ancha, el
        lado estrecho es el horizontal.

        No se aleja más que la vista general del cerebro
        (distanciaVistaGeneral) salvo que haga falta para que la parcela
        quepa entera (FRACCION_MAXIMA).
        """
        tangente = np.tan(np.radians(anguloVista) / 2.0)

        if 0.0 < aspecto < 1.0:
            tangente *= aspecto

        tangente = max(tangente, 1e-3)

        distancia = radio / (cls.FRACCION_ENCUADRE * tangente)

        if distanciaVistaGeneral:
            distancia = min(distancia, distanciaVistaGeneral)

        return max(
            distancia,
            radio / (cls.FRACCION_MAXIMA * tangente),
            cls.DISTANCIA_MINIMA
        )

    def _obtenerThreeDView(self):
        try:
            layoutManager = slicer.app.layoutManager()
            if layoutManager is None:
                return None
            return layoutManager.threeDWidget(0).threeDView()
        except Exception:
            return None

    def cerrar(self):
        """Cierra el panel de resultados y libera la interacción de esta vista."""
        if self.resultsDockWidget is not None:
            try:
                slicer.util.mainWindow().removeDockWidget(
                    self.resultsDockWidget
                )
            except Exception:
                pass
            try:
                self.resultsDockWidget.deleteLater()
            except Exception:
                pass

        self.resultsDockWidget = None
        self.resultsLayout = None
        self.controlsGroup = None
        self.controlsLayout = None
        self.opacitySlider = None
        self.opacityValueLabel = None
        self.resultsTable = None
        self.regionInfoLabel = None
        self.clearSelectionButton = None
        self.tableRows = []
        self.selectedMLNode = None
        self._savedCameraState = None

    # ==============================================================
    # LIMPIAR VISUALIZACIÓN ANTERIOR
    # ==============================================================

    def limpiarVisualizacionAnterior(self):
        """
        Elimina de la escena la corteza y las regiones ML de cualquier
        visualización anterior, sea de este paciente o de otro.

        Solo se muestra un paciente a la vez: seleccionarRegion oculta
        las regiones de esta instancia (self.mlModels), así que las de
        una visualización anterior seguirían visibles al seleccionar.
        """

        # Liberar selección/panel anterior.
        self.cerrar()

        # Regiones ML (atributo MLLabel) y corteza (MLCorteza) de esta
        # instancia o de otra anterior, también tras recargar el módulo.
        # Por nombre, la corteza de este paciente creada por versiones
        # que no ponían el atributo.
        nombresCorteza = {
            f"{self.subjectDir.name}_LH_Pial",
            f"{self.subjectDir.name}_RH_Pial",
        }

        anteriores = [
            nodo
            for nodo in slicer.util.getNodesByClass("vtkMRMLModelNode")
            if nodo.GetAttribute("MLLabel") is not None
            or nodo.GetAttribute("MLCorteza") is not None
            or nodo.GetName() in nombresCorteza
        ]

        for nodo in anteriores:

            print(
                f"[Limpieza] Eliminando {nodo.GetName()}"
            )

            slicer.mrmlScene.RemoveNode(
                nodo
            )

        self.mlModels = []

    # ==============================================================
    # EJECUCIÓN COMPLETA
    # ==============================================================

    def ejecutar(self):
        """
        Ejecuta la visualización completa.
        """

        print("")
        print(
            "=" * 70
        )

        print(
            "VISUALIZACIÓN ML - DESTRIEUX"
        )

        print(
            "=" * 70
        )

        print(
            f"Subject:\n"
            f"{self.subjectDir}"
        )

        print(
            f"LH Pial:\n"
            f"{self.lhPialFile}"
        )

        print(
            f"RH Pial:\n"
            f"{self.rhPialFile}"
        )

        print(
            f"LH ANNOT:\n"
            f"{self.lhAnnotFile}"
        )

        print(
            f"RH ANNOT:\n"
            f"{self.rhAnnotFile}"
        )

        print(
            f"Predicciones:\n"
            f"{self.predictionsFile}"
        )

        # ----------------------------------------------------------
        # 1. Limpiar resultado anterior
        # ----------------------------------------------------------

        self.limpiarVisualizacionAnterior()

        # ----------------------------------------------------------
        # 2. Leer predicciones
        # ----------------------------------------------------------

        self.leerPredicciones()

        # ----------------------------------------------------------
        # 3. Crear corteza real de FreeSurfer
        # ----------------------------------------------------------

        self.crearCortezaCompleta()

        # ----------------------------------------------------------
        # 4. Preparar vista 3D
        #
        # Por ahora la visualización se limita exclusivamente a la
        # corteza cerebral. Las estructuras subcorticales no se
        # generan ni se cargan.
        # ----------------------------------------------------------

        self.prepararVista3D()
        self._guardarVistaExteriorBase()

        # ----------------------------------------------------------
        # 5. Crear tabla de resultados ML
        # ----------------------------------------------------------

        self.crearPanelResultados()
        self.poblarTablaResultados()

        print(
            "[Tabla ML] ✓ Tabla de resultados preparada."
        )

        print("")
        print(
            "=" * 70
        )

        print(
            "VISUALIZACIÓN COMPLETADA"
        )

        print(
            "=" * 70
        )

        return {
            "lh": self.lhModel,
            "rh": self.rhModel,
            "ml": self.mlModels
        }