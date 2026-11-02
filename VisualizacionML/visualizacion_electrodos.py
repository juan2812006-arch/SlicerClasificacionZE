import csv
from pathlib import Path

import numpy as np
import qt
import slicer
import vtk
from vtk.util.numpy_support import vtk_to_numpy


def leerNombresArchivoEEG(path):
    """
    Nombres de electrodos del archivo del sujeto, sin duplicados y en el
    orden del archivo.

    CSV admitido (con o sin encabezado electrode/electrodo/name/nombre/
    channel/canal; se usa la primera columna):
        electrode
        Fp1
        Fp2
        ...

    TXT: un nombre por línea.
    """
    path = Path(path)
    names = []

    if path.suffix.lower() == ".txt":
        with path.open("r", encoding="utf-8-sig") as f:
            for line in f:
                name = line.strip()
                if name:
                    names.append(name)
    else:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))

        if not rows:
            return []

        # Detecta si existe encabezado.
        first = [cell.strip() for cell in rows[0]]
        header_words = {"electrode", "electrodo", "name", "nombre", "channel", "canal"}

        start = 1 if any(cell.lower() in header_words for cell in first) else 0

        for row in rows[start:]:
            if not row:
                continue
            name = row[0].strip()
            if name:
                names.append(name)

    # Elimina duplicados conservando orden y limpia espacios.
    unique = []
    seen = set()
    for name in names:
        clean = name.strip()
        if clean and clean not in seen:
            unique.append(clean)
            seen.add(clean)

    return unique


class VisualizacionElectrodos:
    """
    Visualización esquemática de EEG de superficie usando las posiciones
    estándar del sistema internacional 10-20 / 10-10.

    IMPORTANTE:
    - Las coordenadas estándar son posiciones idealizadas.
    - No representan la digitización real del paciente.
    - Las posiciones se adaptan a la geometría individual de la corteza
      FreeSurfer mediante un elipsoide exterior, de modo que los puntos
      queden alrededor de la corteza y no dentro de ella.
    """

    # Coordenadas del montage estándar MNE standard_1020, en metros.
    # Se incluyen únicamente los electrodos que utiliza el proyecto.
    # Ejes del montage: X izquierda/derecha, Y anterior/posterior,
    # Z inferior/superior.
    STANDARD_1020 = {
        "Fp1": (-0.0294367, 0.0839171, -0.0069900),
        "Fp2": (0.0298723, 0.0848959, -0.0070800),
        "F3": (-0.0502438, 0.0531112, 0.0421920),
        "F4": (0.0518362, 0.0543048, 0.0408140),
        "C3": (-0.0653581, -0.0116317, 0.0643580),
        "C4": (0.0671179, -0.0109003, 0.0635800),
        "P3": (-0.0530073, -0.0787878, 0.0559400),
        "P4": (0.0556667, -0.0785602, 0.0565610),
        "O1": (-0.0294134, -0.1124490, 0.0088390),
        "O2": (0.0298426, -0.1121560, 0.0088000),
        "F7": (-0.0702629, 0.0424743, -0.0114200),
        "F8": (0.0730431, 0.0444217, -0.0120000),
        "T7": (-0.0841611, -0.0160187, -0.0093460),
        "T8": (0.0850799, -0.0150203, -0.0094900),
        "P7": (-0.0724343, -0.0734527, -0.0024870),
        "P8": (0.0730557, -0.0730683, -0.0025400),
        "Fz": (0.0003122, 0.0585120, 0.0664620),
        "Cz": (0.0004009, -0.0091670, 0.1002440),
        "Pz": (0.0003247, -0.0811150, 0.0826150),
        "F9": (-0.0701019, 0.0416523, -0.0499520),
        "F10": (0.0721141, 0.0420667, -0.0504520),
        "P9": (-0.0730093, -0.0737657, -0.0409980),
        "P10": (0.0738947, -0.0743903, -0.0412200),
        "T9": (-0.0858941, -0.0158287, -0.0482830),
        "T10": (0.0855599, -0.0163613, -0.0482710),
    }

    # Orden definido para que la visualización sea reproducible.
    DEFAULT_ORDER = [
        "Fp1", "Fp2",
        "F7", "F3", "Fz", "F4", "F8",
        "F9", "T9", "T7", "C3", "Cz", "C4", "T8", "T10", "F10",
        "P9", "P7", "P3", "Pz", "P4", "P8", "P10",
        "O1", "O2",
    ]

    def __init__(self, subjectDir, lhModel=None, rhModel=None):
        self.subjectDir = Path(subjectDir)
        self.lhModel = lhModel
        self.rhModel = rhModel

        self.eegActor = None
        self.eegMapper = None
        self.eegGlyph = None
        self._electrodeCellIds = []
        self._textActors = []
        self._positions = {}
        self._loadedNames = []
        self._electrodeCellIds = []
        self._visible = True
        self._hoverObserverTag = None
        self._hoverInteractor = None
        self._hoverInfoLabel = None
        self._picker = None

        self.eegFiles = [
            self.subjectDir / "electrodos" / "eeg_superficie.csv",
        ]

    # ------------------------------------------------------------------
    # LECTURA DE ELECTRODOS DEL SUJETO
    # ------------------------------------------------------------------

    def localizarArchivoEEG(self):
        for path in self.eegFiles:
            if path.exists():
                return path
        return None

    def leerElectrodos(self):
        """
        Lee los nombres de electrodos del sujeto (ver leerNombresArchivoEEG)
        y deja solo los del montage estándar, en el orden del proyecto.
        """
        path = self.localizarArchivoEEG()
        if path is None:
            raise FileNotFoundError(
                "No se encontró el archivo EEG del sujeto en:\n"
                f"{self.eegFiles[0]}"
            )

        unique = leerNombresArchivoEEG(path)

        unsupported = [name for name in unique if name not in self.STANDARD_1020]
        if unsupported:
            print(
                "[EEG] ⚠ Electrodos no incluidos en el montage estándar "
                f"y omitidos: {unsupported}"
            )

        supported = [name for name in unique if name in self.STANDARD_1020]

        # Reordenar según el montage definido por el proyecto.
        order = {name: i for i, name in enumerate(self.DEFAULT_ORDER)}
        supported.sort(key=lambda name: order.get(name, 999))

        self._loadedNames = supported
        return supported

    # ------------------------------------------------------------------
    # GEOMETRÍA DE LA CORTEZA
    # ------------------------------------------------------------------

    def obtenerPuntosCorteza(self):
        points = []

        for model in (self.lhModel, self.rhModel):
            if model is None or model.GetPolyData() is None:
                continue

            polyData = model.GetPolyData()
            vtkPoints = polyData.GetPoints()
            if vtkPoints is None or vtkPoints.GetNumberOfPoints() == 0:
                continue

            data = vtk_to_numpy(vtkPoints.GetData())
            if data.size:
                points.append(np.asarray(data, dtype=np.float64))

        if not points:
            raise RuntimeError("No hay superficies corticales disponibles para posicionar el EEG.")

        return np.vstack(points)

    def calcularMarcoCorteza(self):
        points = self.obtenerPuntosCorteza()

        # Centro y semiejes del volumen cortical combinado.
        pmin = np.min(points, axis=0)
        pmax = np.max(points, axis=0)
        center = (pmin + pmax) / 2.0
        halfRange = (pmax - pmin) / 2.0

        # Margen exterior para representar el cuero cabelludo de manera
        # esquemática sin disponer todavía de la superficie de scalp.
        margin = np.array([18.0, 18.0, 18.0], dtype=np.float64)
        radii = np.maximum(halfRange + margin, 25.0)

        return center, radii

    # ------------------------------------------------------------------
    # TRANSFORMACIÓN DEL MONTAGE ESTÁNDAR AL SUJETO
    # ------------------------------------------------------------------

    def _calcularElipsoideExterior(self):
        """Calcula un elipsoide exterior a la corteza para representar el scalp.

        No usamos la pial como superficie de proyección porque los electrodos
        EEG de superficie están sobre el cuero cabelludo, no sobre la corteza.
        El elipsoide conserva la geometría relativa del montage estándar y
        permite una distribución suave y ordenada.
        """
        points = self.obtenerPuntosCorteza()
        pmin = np.min(points, axis=0)
        pmax = np.max(points, axis=0)
        center = (pmin + pmax) / 2.0
        half_range = (pmax - pmin) / 2.0

        # Margen exterior para aproximar la superficie del cuero cabelludo.
        # Se usa el mismo margen base en los tres ejes para no deformar
        # artificialmente el montage.
        base_margin = max(float(np.min(half_range)) * 0.22, 14.0)
        radii = half_range + base_margin

        # Evita ejes degenerados en casos de superficies incompletas.
        radii = np.maximum(radii, 30.0)
        return center, radii

    def _posicionEnElipsoide(self, standard_position, center, radii):
        """Mapea una dirección estándar a la frontera de un elipsoide."""
        direction = np.asarray(standard_position, dtype=np.float64).copy()

        # En el montaje estándar idealizado, los electrodos de la línea media
        # deben compartir exactamente el mismo plano sagital (x = 0).
        # MNE proporciona pequeñas diferencias numéricas en x; aquí se
        # corrigen explícitamente para preservar esa característica anatómica.
        midline_names = {"Fz", "Cz", "Pz"}
        if hasattr(self, '_currentElectrodeName') and self._currentElectrodeName in midline_names:
            direction[0] = 0.0

        norm = np.linalg.norm(direction)
        if norm < 1e-12:
            direction = np.array([0.0, 0.0, 1.0], dtype=np.float64)
            norm = 1.0

        # El punto estándar define la dirección; t lleva esa dirección hasta
        # la superficie del elipsoide. Así no se hace una escala independiente
        # por electrodo y se conserva la organización espacial del montage.
        unit = direction / norm
        denom = (
            (unit[0] / radii[0]) ** 2
            + (unit[1] / radii[1]) ** 2
            + (unit[2] / radii[2]) ** 2
        )

        if denom < 1e-15:
            surface = center + np.array([0.0, 0.0, radii[2]])
        else:
            t = 1.0 / np.sqrt(denom)
            surface = center + unit * t

        # Un pequeño desplazamiento hacia afuera evita que el marcador
        # coincida exactamente con el elipsoide/corteza visual.
        outward = surface - center
        outward_norm = np.linalg.norm(outward)
        if outward_norm < 1e-12:
            outward = np.array([0.0, 0.0, 1.0], dtype=np.float64)
            outward_norm = 1.0

        scalp_gap = float(np.clip(np.min(radii) * 0.025, 4.0, 8.0))
        return surface + outward / outward_norm * scalp_gap

    def calcularPosiciones(self):
        """Calcula posiciones EEG sobre un elipsoide exterior individual."""
        if not self._loadedNames:
            return {}

        center, radii = self._calcularElipsoideExterior()
        positions = {}

        for name in self._loadedNames:
            self._currentElectrodeName = name
            standard_position = self.STANDARD_1020[name]
            positions[name] = self._posicionEnElipsoide(
                standard_position,
                center,
                radii
            )

        self._currentElectrodeName = None
        self._positions = positions
        return positions

    # ------------------------------------------------------------------
    # CREACIÓN DE ACTORES VTK
    # ------------------------------------------------------------------

    def _obtenerRenderer(self):
        layoutManager = slicer.app.layoutManager()
        if layoutManager is None:
            return None
        widget = layoutManager.threeDWidget(0)
        if widget is None:
            return None
        view = widget.threeDView()
        if view is None:
            return None
        renderWindow = view.renderWindow()
        if renderWindow is None:
            return None
        return renderWindow.GetRenderers().GetFirstRenderer()

    def crearEEG(self):
        if not self._positions:
            return

        renderer = self._obtenerRenderer()
        if renderer is None:
            raise RuntimeError("No se encontró el renderer 3D de Slicer.")

        # --------------------------------------------------------------
        # Crear un disco plano para cada electrodo.
        # Cada disco queda tangente a una envolvente exterior del sujeto,
        # por lo que visualmente se comporta como un electrodo de EEG de
        # superficie y no como una esfera.
        # --------------------------------------------------------------
        points = vtk.vtkPoints()
        polygons = vtk.vtkCellArray()
        self._electrodeCellIds = []

        radius = self._calcularRadioPunto() * 1.35
        sides = 24

        center, radii = self._calcularElipsoideExterior()

        for electrodeIndex, name in enumerate(self._loadedNames):
            pos = np.asarray(self._positions[name], dtype=np.float64)

            # Normal exterior de la envolvente elipsoidal en este punto.
            delta = pos - center
            normal = np.array([
                delta[0] / (radii[0] ** 2),
                delta[1] / (radii[1] ** 2),
                delta[2] / (radii[2] ** 2),
            ], dtype=np.float64)

            normalNorm = np.linalg.norm(normal)
            if normalNorm < 1e-12:
                normal = np.array([0.0, 0.0, 1.0], dtype=np.float64)
            else:
                normal /= normalNorm

            # Construir dos vectores tangentes ortogonales al normal.
            reference = np.array([0.0, 0.0, 1.0], dtype=np.float64)
            if abs(float(np.dot(reference, normal))) > 0.90:
                reference = np.array([1.0, 0.0, 0.0], dtype=np.float64)

            tangent1 = np.cross(normal, reference)
            tangent1Norm = np.linalg.norm(tangent1)
            if tangent1Norm < 1e-12:
                tangent1 = np.array([1.0, 0.0, 0.0], dtype=np.float64)
                tangent1Norm = 1.0
            tangent1 /= tangent1Norm

            tangent2 = np.cross(normal, tangent1)
            tangent2Norm = np.linalg.norm(tangent2)
            if tangent2Norm < 1e-12:
                tangent2 = np.array([0.0, 1.0, 0.0], dtype=np.float64)
            else:
                tangent2 /= tangent2Norm

            ids = vtk.vtkIdList()

            for side in range(sides):
                angle = 2.0 * np.pi * side / sides
                point = (
                    pos
                    + radius * np.cos(angle) * tangent1
                    + radius * np.sin(angle) * tangent2
                )

                pointId = points.InsertNextPoint(
                    float(point[0]),
                    float(point[1]),
                    float(point[2]),
                )
                ids.InsertNextId(pointId)

            # Una celda poligonal cerrada = un disco por electrodo.
            polygons.InsertNextCell(ids)
            self._electrodeCellIds.append(electrodeIndex)

        polyData = vtk.vtkPolyData()
        polyData.SetPoints(points)
        polyData.SetPolys(polygons)
        polyData.BuildCells()
        polyData.BuildLinks()

        # Normales para mejorar la apariencia de cada disco.
        normalsFilter = vtk.vtkPolyDataNormals()
        normalsFilter.SetInputData(polyData)
        normalsFilter.ComputePointNormalsOn()
        normalsFilter.ComputeCellNormalsOn()
        normalsFilter.ConsistencyOn()
        normalsFilter.SplittingOff()
        normalsFilter.Update()

        self.eegPolyData = normalsFilter.GetOutput()

        self.eegMapper = vtk.vtkPolyDataMapper()
        self.eegMapper.SetInputData(self.eegPolyData)
        self.eegMapper.ScalarVisibilityOff()

        self.eegActor = vtk.vtkActor()
        self.eegActor.SetMapper(self.eegMapper)

        # Celeste claro para diferenciar los electrodos del modelo cortical.
        self.eegActor.GetProperty().SetColor(0.45, 0.85, 1.0)
        self.eegActor.GetProperty().SetAmbient(0.30)
        self.eegActor.GetProperty().SetDiffuse(0.70)
        self.eegActor.GetProperty().SetSpecular(0.20)
        self.eegActor.GetProperty().SetSpecularPower(20)
        self.eegActor.SetVisibility(True)
        self.eegActor.PickableOn()

        renderer.AddActor(self.eegActor)

        # Los nombres no se dibujan directamente sobre el cerebro.
        # Se muestran únicamente al pasar el cursor sobre el disco.
        self._instalarHover(renderer)
        self._visible = True

        view = slicer.app.layoutManager().threeDWidget(0).threeDView()
        if view is not None:
            view.forceRender()

        print(
            f"[EEG] ✓ {len(self._loadedNames)} electrodos de superficie "
            "representados como discos con montage estándar."
        )

    def _calcularRadioPunto(self):
        _, radii = self.calcularMarcoCorteza()
        base = float(np.min(radii))
        return float(np.clip(base * 0.015, 1.2, 2.5))

    def _obtenerThreeDView(self):
        try:
            layoutManager = slicer.app.layoutManager()
            if layoutManager is None:
                return None
            widget = layoutManager.threeDWidget(0)
            if widget is None:
                return None
            return widget.threeDView()
        except Exception:
            return None

    def _instalarHover(self, renderer):
        """Instala picking de mouse para mostrar el nombre del electrodo."""
        view = self._obtenerThreeDView()
        if view is None:
            return

        interactor = view.renderWindow().GetInteractor()
        if interactor is None:
            return

        self._picker = vtk.vtkCellPicker()
        self._picker.SetTolerance(0.005)

        self._hoverInfoLabel = qt.QLabel("Electrodo EEG: —")
        self._hoverInfoLabel.setMinimumHeight(28)
        self._hoverInfoLabel.setStyleSheet(
            "padding: 6px; border: 1px solid #cccccc;"
        )

        def onMouseMove(caller, event):
            if not self._visible or self.eegActor is None:
                return

            try:
                eventPosition = interactor.GetEventPosition()
                self._picker.Pick(
                    eventPosition[0],
                    eventPosition[1],
                    0,
                    renderer
                )

                pickedActor = self._picker.GetActor()
                cellId = self._picker.GetCellId()

                if pickedActor == self.eegActor and cellId >= 0:
                    if cellId < len(self._electrodeCellIds):
                        electrodeIndex = self._electrodeCellIds[cellId]
                        if electrodeIndex < len(self._loadedNames):
                            name = self._loadedNames[electrodeIndex]
                            self._hoverInfoLabel.setText(
                                f"Electrodo EEG: <b>{name}</b>"
                            )
                            return

                self._hoverInfoLabel.setText(
                    "Electrodo EEG: —"
                )

            except Exception:
                if self._hoverInfoLabel is not None:
                    self._hoverInfoLabel.setText("Electrodo EEG: —")

        self._hoverInteractor = interactor
        self._hoverObserverTag = interactor.AddObserver(
            vtk.vtkCommand.MouseMoveEvent,
            onMouseMove
        )

    # ------------------------------------------------------------------
    # INFORMACIÓN / VISIBILIDAD
    # ------------------------------------------------------------------


    # ------------------------------------------------------------------

    def setVisible(self, visible):
        self._visible = bool(visible)

        if self.eegActor is not None:
            self.eegActor.SetVisibility(self._visible)

        for actor in self._textActors:
            actor.SetVisibility(self._visible)

        if self._hoverInfoLabel is not None:
            self._hoverInfoLabel.setText(
                "Electrodo EEG: —" if self._visible else "EEG de superficie oculto"
            )

        try:
            view = slicer.app.layoutManager().threeDWidget(0).threeDView()
            if view is not None:
                view.forceRender()
        except Exception:
            pass

    def isVisible(self):
        return self._visible

    # ------------------------------------------------------------------
    # PANEL AUXILIAR
    # ------------------------------------------------------------------

    def crearControlVisibilidad(self, parentLayout):
        checkbox = qt.QCheckBox(
            "Mostrar EEG de superficie"
        )
        checkbox.checked = True
        checkbox.toggled.connect(self.setVisible)
        parentLayout.addWidget(checkbox)

        if self._hoverInfoLabel is not None:
            parentLayout.addWidget(self._hoverInfoLabel)

        return checkbox

    # ------------------------------------------------------------------
    # EJECUCIÓN
    # ------------------------------------------------------------------

    def ejecutar(self):
        print("")
        print("=" * 70)
        print("VISUALIZACIÓN EEG DE SUPERFICIE")
        print("=" * 70)

        path = self.localizarArchivoEEG()
        if path is None:
            print(
                "[EEG] ⚠ No se encontró la lista del sujeto. "
                "No se dibujará el EEG todavía."
            )
            print(
                "[EEG] Coloca el archivo en:"
            )
            print(
                self.subjectDir / "electrodos" / "eeg_superficie.csv"
            )
            return False

        self.leerElectrodos()

        if not self._loadedNames:
            print("[EEG] ⚠ No hay electrodos compatibles con standard_1020.")
            return False

        self.calcularPosiciones()
        self.crearEEG()

        print("=" * 70)
        return True

    def cerrar(self):
        if self._hoverInteractor is not None and self._hoverObserverTag is not None:
            try:
                self._hoverInteractor.RemoveObserver(self._hoverObserverTag)
            except Exception:
                pass

        self._hoverObserverTag = None
        self._hoverInteractor = None
        self._picker = None

        if self._hoverInfoLabel is not None:
            try:
                self._hoverInfoLabel.deleteLater()
            except Exception:
                pass
        self._hoverInfoLabel = None

        renderer = self._obtenerRenderer()
        if renderer is not None:
            if self.eegActor is not None:
                renderer.RemoveActor(self.eegActor)

            for actor in self._textActors:
                renderer.RemoveActor(actor)

            try:
                renderer.GetRenderWindow().Render()
            except Exception:
                pass

        self.eegActor = None
        self.eegMapper = None
        self.eegGlyph = None
        self._electrodeCellIds = []
        self._textActors = []
        self._positions = {}
        self._loadedNames = []
        self._electrodeCellIds = []
