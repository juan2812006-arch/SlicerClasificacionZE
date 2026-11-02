import re
from pathlib import Path

import numpy as np
import qt
import slicer
import vtk
from vtk.util.numpy_support import numpy_to_vtk


# ----------------------------------------------------------------------
# FUNCIONES PURAS (sin Slicer), fáciles de probar por separado
# ----------------------------------------------------------------------

# <prefijo><n1>-<prefijo><n2>; el prefijo puede ser cualquier texto (C, TB',
# LA_, H2_...) porque los nombres cambian de un paciente a otro.
_RE_CANAL = re.compile(r"^(.+?)(\d+)\s*-\s*(.+?)(\d+)$")
_RE_NUMERO = re.compile(r"-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")


_RE_CONTACTO = re.compile(r"^([^-]+?)(\d+)$")


def leerDipolos(path, columna="World"):
    """
    Lee el .tsv de electrodos (Channel, SCS, MNI, World, ...).

    Cada fila puede ser un canal bipolar ('A1-A2', punto medio entre dos
    contactos) o un contacto suelto ('A1'). Devuelve, por electrodo:

        {electrodo: {"bi":   [(n1, n2, punto_medio_mm), ...],
                     "mono": {numero: punto_mm, ...}}}
    """
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    lines = [ln for ln in lines if ln.strip()]
    if len(lines) < 2:
        raise ValueError(f"El archivo está vacío: {path}")

    header = [h.strip() for h in lines[0].split("\t")]
    minusculas = [h.lower() for h in header]
    if columna.lower() not in minusculas:
        raise ValueError(
            f"No se encontró la columna de coordenadas '{columna}'. "
            f"Columnas encontradas: {header}"
        )
    iCoord = minusculas.index(columna.lower())
    # Columna de nombres: 'Channel' si existe; si no, la primera columna.
    iCanal = minusculas.index("channel") if "channel" in minusculas else 0

    electrodos = {}
    ignorados = []
    for ln in lines[1:]:
        cols = ln.split("\t")
        if len(cols) <= max(iCanal, iCoord):
            continue

        nombre = cols[iCanal].strip().strip("'\" ")
        valores = [float(v) for v in _RE_NUMERO.findall(cols[iCoord])]
        if len(valores) != 3:
            ignorados.append(nombre)
            continue
        punto = np.array(valores)

        m = _RE_CANAL.match(nombre)
        if m is not None and m.group(1) == m.group(3):
            if int(m.group(4)) != int(m.group(2)) + 1:
                ignorados.append(nombre)
                continue
            e = electrodos.setdefault(m.group(1), {"bi": [], "mono": {}})
            e["bi"].append((int(m.group(2)), int(m.group(4)), punto))
            continue

        m = _RE_CONTACTO.match(nombre)
        if m is not None:
            e = electrodos.setdefault(m.group(1), {"bi": [], "mono": {}})
            e["mono"][int(m.group(2))] = punto
            continue

        ignorados.append(nombre)

    if ignorados:
        print(f"[Barras] ⚠ Filas ignoradas (formato no reconocido): {ignorados}")

    for e in electrodos.values():
        e["bi"].sort(key=lambda t: t[0])

    # Si vienen en metros (valores < 0.5 en todo el archivo), pasar a mm.
    todos = [
        abs(p).max()
        for e in electrodos.values()
        for p in [c[2] for c in e["bi"]] + list(e["mono"].values())
    ]
    if todos and max(todos) < 0.5:
        print("[Barras] Coordenadas en metros: convirtiendo a mm.")
        for e in electrodos.values():
            e["bi"] = [(a, b, p * 1000.0) for a, b, p in e["bi"]]
            e["mono"] = {n: p * 1000.0 for n, p in e["mono"].items()}
    return electrodos


def _contactosDeTramo(tramo):
    """
    Un tramo es una cadena de canales consecutivos (n, n+1), (n+1, n+2)...
    Con puntos medios m_j se recuperan sus k+1 contactos:
    c_0 = m_0 - (m_1-m_0)/2, c_j = (m_{j-1}+m_j)/2, c_k = m_{k-1}+(m_{k-1}-m_{k-2})/2
    """
    k = len(tramo)
    m = [t[2] for t in tramo]
    nums = [tramo[0][0]] + [t[1] for t in tramo]
    c = [m[0] - (m[1] - m[0]) / 2.0]
    c += [(m[j - 1] + m[j]) / 2.0 for j in range(1, k)]
    c += [m[k - 1] + (m[k - 1] - m[k - 2]) / 2.0]
    return list(zip(nums, c))


def reconstruirContactos(entrada):
    """
    A partir de las filas de un electrodo ({"bi": [...], "mono": {...}})
    devuelve [(numero, xyz), ...] ordenado, o None si no se puede.
    Un contacto suelto manda sobre el reconstruido desde un canal bipolar.
    """
    canales = entrada["bi"]
    contactos = {}

    if canales:
        tramos, actual = [], [canales[0]]
        for ch in canales[1:]:
            if ch[0] == actual[-1][1]:
                actual.append(ch)
            else:
                tramos.append(actual)
                actual = [ch]
        tramos.append(actual)

        largos = [t for t in tramos if len(t) >= 2]
        paso = (largos[0][1][2] - largos[0][0][2]) if largos else None

        for tramo in tramos:
            if len(tramo) >= 2:
                pares = _contactosDeTramo(tramo)
            elif paso is not None:
                medio = tramo[0][2]
                pares = [
                    (tramo[0][0], medio - paso / 2.0),
                    (tramo[0][1], medio + paso / 2.0),
                ]
            else:
                pares = []
            for n, p in pares:
                contactos[n] = p

    contactos.update(entrada["mono"])
    if len(contactos) < 2:
        return None
    return sorted(contactos.items())


def matrizWorldATkras(origFile):
    """
    Matriz 4x4 que lleva coordenadas 'World' (RAS de escáner, mm) del T1 a
    tkRAS de FreeSurfer, que es el espacio de las superficies lh/rh.pial.
    """
    import nibabel as nib

    img = nib.load(str(origFile))
    tkr = np.asarray(img.header.get_vox2ras_tkr(), dtype=np.float64)
    scanner = np.asarray(img.affine, dtype=np.float64)
    return tkr @ np.linalg.inv(scanner)


def _matrizRotacion(origen, destino):
    """Rotación 3x3 que lleva el vector unitario origen sobre destino."""
    a = np.asarray(origen, dtype=float)
    b = np.asarray(destino, dtype=float)
    v = np.cross(a, b)
    c = float(np.dot(a, b))
    s = np.linalg.norm(v)
    if s < 1e-9:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    k = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
    return np.eye(3) + k + k @ k * ((1.0 - c) / (s * s))



# ----------------------------------------------------------------------
# VALIDACIÓN Y AJUSTE DEL REGISTRO CONTRA LA CORTEZA
# ----------------------------------------------------------------------

def crearMascaraCerebro(polys, paso=1.0, margen=8.0):
    """
    Rasteriza la unión de superficies cerradas (lh/rh.pial) en una máscara
    binaria. Devuelve (mascara[x, y, z], origen, paso).
    """
    from vtk.util.numpy_support import vtk_to_numpy

    b = np.array([p.GetBounds() for p in polys], dtype=float)
    lo = b[:, 0::2].min(axis=0) - margen
    hi = b[:, 1::2].max(axis=0) + margen
    dims = np.ceil((hi - lo) / paso).astype(int) + 1
    mascara = np.zeros(tuple(dims), dtype=bool)

    for poly in polys:
        img = vtk.vtkImageData()
        img.SetOrigin(*[float(v) for v in lo])
        img.SetSpacing(paso, paso, paso)
        img.SetDimensions(*[int(d) for d in dims])
        img.AllocateScalars(vtk.VTK_UNSIGNED_CHAR, 1)
        img.GetPointData().GetScalars().Fill(1)

        conv = vtk.vtkPolyDataToImageStencil()
        conv.SetInputData(poly)
        conv.SetOutputOrigin(*[float(v) for v in lo])
        conv.SetOutputSpacing(paso, paso, paso)
        conv.SetOutputWholeExtent(img.GetExtent())
        conv.Update()

        stencil = vtk.vtkImageStencil()
        stencil.SetInputData(img)
        stencil.SetStencilConnection(conv.GetOutputPort())
        stencil.ReverseStencilOff()
        stencil.SetBackgroundValue(0)
        stencil.Update()

        arr = vtk_to_numpy(stencil.GetOutput().GetPointData().GetScalars())
        arr = arr.reshape(dims[2], dims[1], dims[0]).transpose(2, 1, 0)
        mascara |= arr.astype(bool)

    return mascara, lo, paso


def mapaProfundidad(mascara, paso):
    """Distancia (mm) de cada vóxel interior a la superficie; 0 fuera."""
    try:
        from scipy import ndimage
        return ndimage.distance_transform_edt(mascara) * paso
    except ImportError:
        return mascara.astype(float) * paso


def _muestrear(mapa, origen, paso, pts):
    idx = np.rint((pts - origen) / paso).astype(int)
    ok = np.all((idx >= 0) & (idx < np.array(mapa.shape)), axis=-1)
    out = np.zeros(pts.shape[:-1])
    ii = idx[ok]
    out[ok] = mapa[ii[:, 0], ii[:, 1], ii[:, 2]]
    return out


def mapaDistanciaExterior(mascara, paso):
    """Distancia (mm) de cada vóxel exterior a la superficie; 0 dentro."""
    try:
        from scipy import ndimage
        return ndimage.distance_transform_edt(~mascara) * paso
    except ImportError:
        return np.zeros(mascara.shape)


def clasificarPuntos(pts, polys):
    """
    Para cada punto (tkRAS) devuelve (dentro[bool], distFuera[mm]) respecto
    a la unión de superficies pial. distFuera es 0 si el punto está dentro.
    Los puntos fuera de la rejilla (muy lejos) cuentan como fuera.
    """
    mascara, origen, paso = crearMascaraCerebro(polys)
    dentro = _muestrear(mapaProfundidad(mascara, paso), origen, paso, pts) > 0
    dist = _muestrear(mapaDistanciaExterior(mascara, paso), origen, paso, pts)
    dist = np.where(dentro, 0.0, dist)
    return dentro, dist


def fraccionDentro(pts, profundidad, origen, paso):
    """Fracción de puntos que caen dentro de la corteza."""
    return float(np.mean(_muestrear(profundidad, origen, paso, pts) > 0))


def evaluarRegistro(ptsTk, polys):
    """
    Fracción de contactos (en tkRAS) que caen dentro de las superficies pial.
    Con el T1 correcto del paciente suele estar entre 0.7 y 0.95; si es muy
    baja, los electrodos no corresponden a la anatomía de este sujeto.
    """
    mascara, origen, paso = crearMascaraCerebro(polys)
    return fraccionDentro(ptsTk, mapaProfundidad(mascara, paso), origen, paso)


# ----------------------------------------------------------------------
# VISUALIZACIÓN
# ----------------------------------------------------------------------

class VisualizacionElectrodosBarra:
    """
    Dibuja electrodos de profundidad (sEEG) como barras delgadas con
    contactos anulares, a partir del .tsv de canales bipolares.

    Interfaz equivalente a VisualizacionElectrodos:
        ejecutar(), setVisible(), isVisible(), crearControlVisibilidad(),
        cerrar()
    """

    COLOR_BARRA = (0.55, 0.55, 0.58)       # gris
    COLOR_CONTACTO = (1.0, 1.0, 1.0)       # blanco
    COLOR_ETIQUETA = (0.95, 0.95, 0.60)
    OPACIDAD_CORTEZA = 0.35
    UMBRAL_REGISTRO = 0.50    # por debajo, se avisa que no coincide con la corteza

    RADIO_BARRA = 0.35        # mm
    RADIO_CONTACTO = 0.60     # mm
    LARGO_CONTACTO = 2.0      # mm
    EXTENSION_BARRA = 1.5     # mm extra en cada extremo

    def __init__(self, subjectDir, dipolosFile, lhModel=None, rhModel=None,
                 columna="World"):
        self.subjectDir = Path(subjectDir)
        self.dipolosFile = Path(dipolosFile)
        self.lhModel = lhModel
        self.rhModel = rhModel
        self.columna = columna
        self.registro = None       # fracción de contactos dentro de la corteza
        self._dentro = np.ones(0, dtype=bool)
        self._distFuera = np.zeros(0)
        self._contactosVisibles = None   # filtro 'solo dentro' (threshold)
        self.origFile = self.subjectDir / "mri" / "orig.mgz"

        self.barraActor = None
        self.contactosActor = None
        self._textActors = []
        self._electrodos = {}      # nombre -> [(numero, xyz tkRAS), ...]
        self._listaElectrodos = []
        self._contactos = []       # (electrodo, numero, xyz) por contactId
        self._barraPoly = None
        self._contactosPoly = None
        self._visible = True
        self._hoverObserverTag = None
        self._hoverInteractor = None
        self._hoverInfoLabel = None
        self._picker = None

    # ------------------------------------------------------------------
    # DATOS
    # ------------------------------------------------------------------

    def cargarElectrodos(self):
        canales = leerDipolos(self.dipolosFile, self.columna)

        # Contactos en coordenadas World (RAS de escáner del T1).
        mundo = {}
        for nombre, lista in canales.items():
            contactos = reconstruirContactos(lista)
            if contactos is None or len(contactos) < 2:
                print(f"[Barras] ⚠ Electrodo {nombre} omitido: datos insuficientes")
                continue
            mundo[nombre] = contactos

        if not mundo:
            self._electrodos, self._listaElectrodos, self._contactos = {}, [], []
            return

        M = self._matrizOrig()

        self._electrodos = {
            nombre: [(n, (M @ np.append(p, 1.0))[:3]) for n, p in contactos]
            for nombre, contactos in mundo.items()
        }
        self._listaElectrodos = list(self._electrodos.keys())
        self._contactos = [
            (e, n, p)
            for e in self._listaElectrodos
            for n, p in self._electrodos[e]
        ]
        self._clasificar()

    def _matrizOrig(self):
        """World → tkRAS con el orig.mgz del sujeto."""
        if not self.origFile.exists():
            raise FileNotFoundError(
                f"No existe {self.origFile}: sin el T1 conformado del "
                "pipeline no se puede pasar World → tkRAS."
            )
        M = matrizWorldATkras(self.origFile)
        print(f"[Barras] World → tkRAS con {self.origFile}")
        print(f"[Barras] c_ras (World − tkRAS): {np.round(-M[:3, 3], 2)} mm")
        return M

    def _clasificar(self):
        """
        Compara cada contacto con la corteza del propio sujeto (superficies
        pial): dentro / a cuántos mm fuera. No mueve ningún contacto.
        """
        n = len(self._contactos)
        self._dentro = np.ones(n, dtype=bool)
        self._distFuera = np.zeros(n)

        polys = []
        for model in (self.lhModel, self.rhModel):
            try:
                polys.append(model.GetPolyData())
            except Exception:
                pass
        if not polys or n == 0:
            return

        pts = np.array([p for _, _, p in self._contactos])
        try:
            self._dentro, self._distFuera = clasificarPuntos(pts, polys)
        except Exception as exc:
            print(f"[Barras] ⚠ No se pudo validar el registro: {exc}")
            return

        frac = float(np.mean(self._dentro))
        self.registro = frac
        fuera = self._distFuera[~self._dentro]
        print(f"[Barras] {100 * frac:.0f}% de los contactos caen dentro de la corteza")
        if len(fuera):
            print(
                f"[Barras] {len(fuera)} contactos fuera de la superficie pial: "
                f"mediana {np.median(fuera):.1f} mm, máximo {fuera.max():.1f} mm"
            )
        if frac < self.UMBRAL_REGISTRO:
            print(
                "[Barras] ⚠ Muy pocos contactos caen dentro de la corteza: el "
                "archivo de electrodos probablemente no corresponde al T1 con "
                "el que se procesó este sujeto (otro paciente o espacio distinto)."
            )

    # ------------------------------------------------------------------
    # ACTORES VTK
    # ------------------------------------------------------------------

    def _obtenerThreeDView(self):
        try:
            layoutManager = slicer.app.layoutManager()
            if layoutManager is None:
                return None
            widget = layoutManager.threeDWidget(0)
            return widget.threeDView() if widget is not None else None
        except Exception:
            return None

    def _obtenerRenderer(self):
        view = self._obtenerThreeDView()
        if view is None or view.renderWindow() is None:
            return None
        return view.renderWindow().GetRenderers().GetFirstRenderer()

    @staticmethod
    def _conAtributos(poly, electrodoId, contactoId, color, dentro=1):
        n = poly.GetNumberOfCells()
        for nombre, valor in (("electrodoId", electrodoId),
                              ("contactoId", contactoId),
                              ("dentro", int(dentro))):
            arr = numpy_to_vtk(np.full(n, valor, dtype=np.int32), deep=True)
            arr.SetName(nombre)
            poly.GetCellData().AddArray(arr)

        rgb = np.tile(
            np.array([int(c * 255) for c in color], dtype=np.uint8), (n, 1)
        )
        colores = numpy_to_vtk(rgb, deep=True)
        colores.SetName("Colors")
        poly.GetCellData().SetScalars(colores)
        return poly

    def _crearBarra(self, p1, p2, electrodoId):
        direccion = p2 - p1
        largo = np.linalg.norm(direccion)
        if largo > 1e-9:
            direccion = direccion / largo
        a = p1 - direccion * self.EXTENSION_BARRA
        b = p2 + direccion * self.EXTENSION_BARRA

        linea = vtk.vtkLineSource()
        linea.SetPoint1(*[float(v) for v in a])
        linea.SetPoint2(*[float(v) for v in b])

        tubo = vtk.vtkTubeFilter()
        tubo.SetInputConnection(linea.GetOutputPort())
        tubo.SetRadius(self.RADIO_BARRA)
        tubo.SetNumberOfSides(12)
        tubo.CappingOn()
        tubo.Update()

        poly = vtk.vtkPolyData()
        poly.DeepCopy(tubo.GetOutput())
        poly.GetCellData().Initialize()
        return self._conAtributos(poly, electrodoId, -1, self.COLOR_BARRA)

    def _crearContacto(self, centro, direccion, electrodoId, contactoId, color,
                       dentro=1):
        cil = vtk.vtkCylinderSource()           # eje a lo largo de Y
        cil.SetRadius(self.RADIO_CONTACTO)
        cil.SetHeight(self.LARGO_CONTACTO)
        cil.SetResolution(16)
        cil.Update()

        R = _matrizRotacion([0.0, 1.0, 0.0], direccion)
        m = vtk.vtkMatrix4x4()
        for i in range(3):
            for j in range(3):
                m.SetElement(i, j, float(R[i, j]))
            m.SetElement(i, 3, float(centro[i]))
        transform = vtk.vtkTransform()
        transform.SetMatrix(m)

        tf = vtk.vtkTransformPolyDataFilter()
        tf.SetInputData(cil.GetOutput())
        tf.SetTransform(transform)
        tf.Update()

        poly = vtk.vtkPolyData()
        poly.DeepCopy(tf.GetOutput())
        poly.GetCellData().Initialize()
        return self._conAtributos(poly, electrodoId, contactoId, color, dentro)

    def crearBarras(self):
        renderer = self._obtenerRenderer()
        if renderer is None:
            raise RuntimeError("No se encontró el renderer 3D de Slicer.")

        barras = vtk.vtkAppendPolyData()
        contactos = vtk.vtkAppendPolyData()
        contactoId = 0

        for eId, nombre in enumerate(self._listaElectrodos):
            lista = self._electrodos[nombre]
            pts = [p for _, p in lista]
            color = self.COLOR_CONTACTO

            barras.AddInputData(self._crearBarra(pts[0], pts[-1], eId))

            direccion = pts[-1] - pts[0]
            direccion = direccion / max(np.linalg.norm(direccion), 1e-9)
            for _, p in lista:
                contactos.AddInputData(
                    self._crearContacto(
                        p, direccion, eId, contactoId, color,
                        bool(self._dentro[contactoId])
                    )
                )
                contactoId += 1

        barras.Update()
        contactos.Update()
        self._barraPoly = barras.GetOutput()
        self._contactosPoly = contactos.GetOutput()

        self.barraActor = self._crearActor(self._barraPoly)
        self.contactosActor = self._crearActor(self._contactosPoly)

        # Filtro opcional: solo contactos dentro de la superficie pial.
        umbral = vtk.vtkThreshold()
        umbral.SetInputData(self._contactosPoly)
        umbral.SetInputArrayToProcess(
            0, 0, 0, vtk.vtkDataObject.FIELD_ASSOCIATION_CELLS, "dentro"
        )
        umbral.SetLowerThreshold(0.5)
        umbral.SetUpperThreshold(1.5)
        umbral.SetThresholdFunction(vtk.vtkThreshold.THRESHOLD_BETWEEN)
        geometria = vtk.vtkGeometryFilter()
        geometria.SetInputConnection(umbral.GetOutputPort())
        self._contactosVisibles = geometria
        renderer.AddActor(self.barraActor)
        renderer.AddActor(self.contactosActor)

        self._instalarHover(renderer)
        self._visible = True

        view = self._obtenerThreeDView()
        if view is not None:
            try:
                # Las barras opacas deben verse a través de la corteza.
                view.mrmlViewNode().SetUseDepthPeeling(1)
            except Exception:
                pass
            view.forceRender()

        print(
            f"[Barras] ✓ {len(self._listaElectrodos)} electrodos, "
            f"{len(self._contactos)} contactos representados."
        )

    @staticmethod
    def _crearActor(poly):
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly)
        mapper.SetScalarModeToUseCellData()
        mapper.SetColorModeToDirectScalars()
        mapper.ScalarVisibilityOn()

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetAmbient(0.30)
        actor.GetProperty().SetDiffuse(0.70)
        actor.GetProperty().SetSpecular(0.30)
        actor.GetProperty().SetSpecularPower(30)
        actor.PickableOn()
        return actor

    # ------------------------------------------------------------------
    # HOVER
    # ------------------------------------------------------------------

    def _textoHover(self, dataset, cellId):
        cellData = dataset.GetCellData()
        eId = int(cellData.GetArray("electrodoId").GetValue(cellId))
        cId = int(cellData.GetArray("contactoId").GetValue(cellId))
        nombre = self._listaElectrodos[eId]

        if cId >= 0:
            _, numero, p = self._contactos[cId]
            total = len(self._electrodos[nombre])
            return (
                f"Electrodo SEEG: <b>{nombre}</b> — contacto "
                f"<b>{nombre}{numero}</b> ({numero}/{total}) "
                f"· tkRAS ({p[0]:.1f}, {p[1]:.1f}, {p[2]:.1f}) mm"
            )
        total = len(self._electrodos[nombre])
        return f"Electrodo SEEG: <b>{nombre}</b> ({total} contactos)"

    def _instalarHover(self, renderer):
        view = self._obtenerThreeDView()
        if view is None:
            return
        interactor = view.renderWindow().GetInteractor()
        if interactor is None:
            return

        self._picker = vtk.vtkCellPicker()
        self._picker.SetTolerance(0.01)
        self._picker.PickFromListOn()          # ignora la corteza
        self._picker.AddPickList(self.barraActor)
        self._picker.AddPickList(self.contactosActor)

        self._hoverInfoLabel = qt.QLabel("Electrodo SEEG: —")
        self._hoverInfoLabel.setMinimumHeight(28)
        self._hoverInfoLabel.setWordWrap(True)
        self._hoverInfoLabel.setStyleSheet(
            "padding: 6px; border: 1px solid #cccccc;"
        )

        def onMouseMove(caller, event):
            if not self._visible or self.barraActor is None:
                return
            try:
                x, y = interactor.GetEventPosition()
                self._picker.Pick(x, y, 0, renderer)
                actor = self._picker.GetActor()
                cellId = self._picker.GetCellId()
                dataset = self._picker.GetDataSet()
                if actor is not None and cellId >= 0 and dataset is not None:
                    self._hoverInfoLabel.setText(self._textoHover(dataset, cellId))
                else:
                    self._hoverInfoLabel.setText("Electrodo SEEG: —")
            except Exception:
                if self._hoverInfoLabel is not None:
                    self._hoverInfoLabel.setText("Electrodo SEEG: —")

        self._hoverInteractor = interactor
        self._hoverObserverTag = interactor.AddObserver(
            vtk.vtkCommand.MouseMoveEvent, onMouseMove
        )

    # ------------------------------------------------------------------
    # VISIBILIDAD / PANEL
    # ------------------------------------------------------------------

    def setVisible(self, visible):
        self._visible = bool(visible)
        for actor in (self.barraActor, self.contactosActor, *self._textActors):
            if actor is not None:
                actor.SetVisibility(self._visible)

        if self._hoverInfoLabel is not None:
            self._hoverInfoLabel.setText(
                "Electrodo SEEG: —" if self._visible else "SEEG oculto"
            )

        view = self._obtenerThreeDView()
        if view is not None:
            view.forceRender()

    def mostrarContactosFuera(self, mostrar):
        """Muestra u oculta los contactos que quedan fuera de la superficie pial."""
        if self.contactosActor is None or self._contactosVisibles is None:
            return
        mapper = self.contactosActor.GetMapper()
        if mostrar:
            mapper.SetInputData(self._contactosPoly)
        else:
            self._contactosVisibles.Update()
            mapper.SetInputConnection(self._contactosVisibles.GetOutputPort())
        view = self._obtenerThreeDView()
        if view is not None:
            view.forceRender()

    def isVisible(self):
        return self._visible

    def crearControlVisibilidad(self, parentLayout):
        checkbox = qt.QCheckBox("Mostrar electrodos SEEG (barras)")
        checkbox.checked = True
        checkbox.toggled.connect(self.setVisible)
        parentLayout.addWidget(checkbox)

        nFuera = int(np.sum(~self._dentro))
        if nFuera:
            fueraCaja = qt.QCheckBox(
                f"Mostrar los {nFuera} contactos fuera de la superficie pial"
            )
            fueraCaja.checked = True
            fueraCaja.toggled.connect(self.mostrarContactosFuera)
            parentLayout.addWidget(fueraCaja)

        if self.registro is not None:
            frac = self.registro
            if frac < self.UMBRAL_REGISTRO:
                texto = (
                    f"⚠ Solo {100 * frac:.0f}% de los contactos cae dentro de la "
                    "corteza: el archivo SEEG probablemente no corresponde al "
                    "T1 de este sujeto."
                )
                estilo = "color: #b00020; font-size: 11px;"
            else:
                fuera = self._distFuera[~self._dentro]
                texto = (
                    f"Registro SEEG: {100 * frac:.0f}% de los contactos "
                    "dentro de la corteza"
                )
                if len(fuera):
                    texto += (
                        f"; los {len(fuera)} restantes quedan a una mediana de "
                        f"{np.median(fuera):.1f} mm (máx. {fuera.max():.1f} mm) "
                        "de la superficie pial"
                    )
                estilo = "color: #666666; font-size: 11px;"
            info = qt.QLabel(texto)
            info.setWordWrap(True)
            info.setStyleSheet(estilo)
            parentLayout.addWidget(info)

        if self._hoverInfoLabel is not None:
            parentLayout.addWidget(self._hoverInfoLabel)
        return checkbox

    # ------------------------------------------------------------------
    # EJECUCIÓN
    # ------------------------------------------------------------------

    def ejecutar(self):
        print("")
        print("=" * 70)
        print("VISUALIZACIÓN SEEG EN BARRAS")
        print("=" * 70)

        if not self.dipolosFile.exists():
            print(f"[Barras] ⚠ No existe el archivo de electrodos: {self.dipolosFile}")
            return False
        try:
            self.cargarElectrodos()
        except Exception as exc:
            print(f"[Barras] ⚠ No se pudo cargar el archivo: {exc}")
            return False

        if not self._electrodos:
            print("[Barras] ⚠ No hay electrodos válidos en el archivo.")
            return False

        self.crearBarras()
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
            for actor in (self.barraActor, self.contactosActor, *self._textActors):
                if actor is not None:
                    renderer.RemoveActor(actor)
            try:
                renderer.GetRenderWindow().Render()
            except Exception:
                pass

        self.barraActor = None
        self.contactosActor = None
        self._textActors = []
        self._electrodos = {}
        self._listaElectrodos = []
        self._contactos = []
        self._barraPoly = None
        self._contactosPoly = None
