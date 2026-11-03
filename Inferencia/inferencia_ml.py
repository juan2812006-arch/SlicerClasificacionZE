"""Puente entre la extensión de Slicer y el modelo de SOZ (soz_inferencia.py).

Lee <sujeto>/caracteristicas/caracteristicas_modelo.csv, ejecuta el modelo y deja en la carpeta del sujeto:
  - predicciones_soz_modelo.csv: tabla del modelo en el formato del proyecto (';', decimal ','): region_destrieux,
    puntaje_soz, origen y probabilidad_soz (probabilidad calibrada). Es la referencia clínica.
  - predicciones_epileptogenicidad.csv: 'label,probabilidad' con etiquetas ctx_lh_/ctx_rh_, el formato que lee
    VisualizacionML. La columna probabilidad es la "probabilidad visual": 1 en las regiones que el modelo marcó como
    SOZ y, en las demás, su peso de propagación (0,6 x / 0,3 x desde las marcadas) dividido por el de la marcada más
    alta, así que nunca pasa de 0,6. Solo entran las regiones con valor > 0; las lejanas quedan en gris.

No importa slicer ni pandas al cargarse, así que se puede importar antes de instalar las dependencias y probar
fuera de Slicer.
"""
import csv
import warnings
from importlib import metadata
from pathlib import Path

INFERENCIA_DIR = Path(__file__).resolve().parent
MODELO_FILE = INFERENCIA_DIR / "soz_extratrees_sEEG_15pacientes.joblib"

# Debe coincidir con modelo["versiones"]["scikit-learn"] del .joblib para que prediga igual que en el entrenamiento.
VERSION_SKLEARN = "1.9.1"

# distribución de pip -> requisito que se instala si falta.
DEPENDENCIAS = {
    "pandas": "pandas",
    "joblib": "joblib",
    "scikit-learn": f"scikit-learn=={VERSION_SKLEARN}",
    "nibabel": "nibabel",  # superficies y anotaciones de FreeSurfer (VisualizacionML)
}

ARCHIVO_MODELO = "predicciones_soz_modelo.csv"
ARCHIVO_VISUAL = "predicciones_epileptogenicidad.csv"
PREFIJOS = {"L": "ctx_lh_", "R": "ctx_rh_"}
MARCADA = "SOZ marcada (modelo)"  # valor de 'origen' en salida_simple

_modelo = None


def dependenciasFaltantes():
    """Requisitos de pip que faltan o tienen otra versión (sin importarlos, para no fijar una versión vieja)."""
    faltan = []
    for distribucion, requisito in DEPENDENCIAS.items():
        try:
            instalada = metadata.version(distribucion)
        except metadata.PackageNotFoundError:
            faltan.append(requisito)
            continue
        if "==" in requisito and instalada != requisito.split("==")[1]:
            faltan.append(requisito)
    return faltan


def leerCaracteristicas(ruta):
    """CSV de características con ';' y decimal ',' (formato del proyecto) o con ',' y decimal '.'."""
    import pandas as pd

    ruta = Path(ruta)
    with ruta.open("r", encoding="utf-8-sig") as archivo:
        cabecera = archivo.readline()
    if ";" in cabecera:
        return pd.read_csv(ruta, encoding="utf-8-sig", sep=";", decimal=",")
    return pd.read_csv(ruta, encoding="utf-8-sig", sep=",", decimal=".")


def validarCaracteristicas(ruta):
    """Comprueba el CSV de características antes de lanzar FreeSurfer, que tarda horas.

    Devuelve el número de parcelas implantadas; lanza ValueError con un mensaje para el usuario si el archivo no
    sirve para el modelo.
    """
    import soz_inferencia

    modelo = cargarModelo()
    try:
        tabla = soz_inferencia._leer(leerCaracteristicas(ruta), modelo["features"])
    except (ValueError, UnicodeDecodeError) as e:
        raise ValueError(f"El archivo de características no tiene el formato esperado: {e}") from e
    esperadas = {r for par in modelo["vecinos"] for r in par}
    desconocidas = sorted(set(tabla["region_destrieux"]) - esperadas)
    if desconocidas:
        raise ValueError("Hay regiones con un nombre que no es del atlas Destrieux (se espera '<región> L' o "
                         f"'<región> R'): {', '.join(desconocidas[:5])}")
    implantadas = int(tabla[soz_inferencia.SEEG].notna().any(axis=1).sum())
    if implantadas == 0:
        raise ValueError("Ninguna región tiene valores sEEG: el modelo solo puntúa las regiones implantadas.")
    return implantadas


def cargarModelo():
    """Carga el modelo una sola vez por sesión."""
    global _modelo
    if _modelo is None:
        if not MODELO_FILE.exists():
            raise FileNotFoundError(f"No se encontró el modelo:\n{MODELO_FILE}")
        import soz_inferencia
        _modelo = soz_inferencia.cargar_modelo(MODELO_FILE)
    return _modelo


def etiquetaVisual(region):
    """'G_and_S_frontomargin L' -> 'ctx_lh_G_and_S_frontomargin'."""
    nombre, _, hemisferio = str(region).strip().rpartition(" ")
    if hemisferio not in PREFIJOS or not nombre:
        raise ValueError(f"Región sin hemisferio ' L'/' R': {region!r}")
    return PREFIJOS[hemisferio] + nombre


def probabilidadVisual(origen, peso, peso_maximo):
    """1 si el modelo marcó la región como SOZ; si no, peso_mapa / el de la marcada más alta (0 = sin relación).

    Se divide sin restar el mínimo (a diferencia de puntaje_soz) para que una vecina nunca quede en 0 solo por ser
    la más baja del paciente.
    """
    if origen == MARCADA:
        return 1.0
    if not peso == peso or not peso_maximo > 0:  # NaN o sin peso en el paciente
        return 0.0
    return float(peso) / float(peso_maximo)


def escribirCsvVisual(simple, ruta):
    """Escribe label,probabilidad (probabilidad visual) solo con las regiones de valor > 0."""
    peso_maximo = simple["probabilidad_soz"].max()
    filas = []
    for region, origen, peso in zip(simple["region_destrieux"], simple["origen"], simple["probabilidad_soz"]):
        visual = probabilidadVisual(origen, peso, peso_maximo)
        if visual > 0:
            filas.append((etiquetaVisual(region), min(visual, 1.0)))
    with Path(ruta).open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["label", "probabilidad"])
        escritor.writerows((label, f"{p:.6f}") for label, p in filas)
    return len(filas)


def ejecutarInferencia(subjectDir):
    """Ejecuta el modelo para el sujeto y escribe los dos CSV. Devuelve un resumen para la interfaz.

    "marcadas" son las regiones que el modelo clasifica como epileptogénicas (probabilidad visual 1), en el orden de
    salida_simple. La interfaz no muestra la probabilidad calibrada: solo queda en predicciones_soz_modelo.csv.
    """
    import soz_inferencia

    subjectDir = Path(subjectDir)
    featuresFile = subjectDir / "caracteristicas" / "caracteristicas_modelo.csv"
    archivoModelo = subjectDir / ARCHIVO_MODELO
    archivoVisual = subjectDir / ARCHIVO_VISUAL

    # Sin predicciones viejas: si la inferencia falla, la visualización no muestra otro resultado.
    for ruta in (archivoModelo, archivoVisual):
        if ruta.exists():
            ruta.unlink()

    if not featuresFile.exists():
        raise FileNotFoundError(f"No se encontró el archivo de características:\n{featuresFile}")

    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        modelo = cargarModelo()
        detalle = soz_inferencia.predecir(leerCaracteristicas(featuresFile), modelo, detallada=True)
    simple = soz_inferencia.salida_simple(detalle)

    soz_inferencia.guardar_csv(simple, archivoModelo)
    n_mostradas = escribirCsvVisual(simple, archivoVisual)

    marcadas = list(simple.loc[simple["origen"] == MARCADA, "region_destrieux"])
    return {
        "n_implantadas": int(detalle["implantada"].sum()),
        "n_marcadas": len(marcadas),
        "n_mostradas": n_mostradas,
        "marcadas": marcadas,
        "avisos": [str(a.message) for a in avisos],
        "archivo_modelo": archivoModelo,
        "archivo_visual": archivoVisual,
    }
