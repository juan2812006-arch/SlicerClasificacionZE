"""Inferencia de la SOZ por parcela Destrieux para la extensión de Slicer (modelo exportado por 13_exportar_slicer.py
o 14_exportar_slicer_15pacientes.py).

Módulo autónomo: no necesita el paquete `epi`, solo numpy, pandas, scipy, scikit-learn y joblib. Reproduce
epi.prediccion.predecir_paciente + salida_simple para UN paciente con el Extra Trees de solo sEEG (IMP-T-Q):
  1. implantada = la parcela tiene algún valor sEEG (antes de enmascarar);
  2. un marcador constante en el paciente (p. ej. EI = 0 en todas) no está disponible -> NaN;
  3. cada marcador pasa a percentil dentro del paciente, solo con las parcelas implantadas;
  4. el pipeline guardado (imputación con indicador + escalado + Extra Trees) da p;
  5. percentil de p -> probabilidad recalibrada ("rango") y marca de SOZ (umbral relativo);
  6. peso_mapa: las marcadas conservan su probabilidad; las demás reciben 0,6 × la de la marcada vecina más alta,
     0,3 × la de segundo orden y 0 lejos.

Uso:
    import soz_inferencia
    modelo = soz_inferencia.cargar_modelo("soz_extratrees_sEEG_sin0391.joblib")  # una vez
    tabla = soz_inferencia.predecir("paciente.csv", modelo)  # o un DataFrame con region_destrieux + seeg_*
(con los 15 pacientes: "soz_extratrees_sEEG_15pacientes.joblib"). La entrada son las 148 regiones con los nombres
del proyecto ('<etiqueta Destrieux> L' / 'R'). El rendimiento esperado es el del LOPO (AUROC media por paciente
0,875 [IC 95 % 0,804–0,935]): ordena las parcelas, no da una probabilidad segura.
"""
import warnings

import joblib
import numpy as np
import pandas as pd
import sklearn
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import shortest_path

N_PARCELAS = 148
SEEG = ["seeg_EI_valor", "seeg_HFO_valor", "seeg_ER_valor", "seeg_SE_valor"]
PESOS = {0: 1.0, 1: 0.6, 2: 0.3}  # orden de vecindad -> factor del peso_mapa (0 = la propia parcela)
CSV = {"sep": ";", "decimal": ","}  # formato de los CSV del proyecto


def cargar_modelo(ruta) -> dict:
    """Carga el modelo exportado. joblib usa pickle: abrir solo archivos generados por este proyecto."""
    modelo = joblib.load(ruta)
    entrenado = modelo["versiones"]["scikit-learn"]
    if sklearn.__version__ != entrenado:
        warnings.warn(f"scikit-learn {sklearn.__version__} instalado, pero el modelo se entrenó con {entrenado}: "
                      f"instala esa versión para que prediga igual")
    return modelo


def _leer(entrada, features) -> pd.DataFrame:
    """CSV del proyecto (';', decimal ',') o DataFrame; valida columnas, 148 regiones únicas y números."""
    if isinstance(entrada, pd.DataFrame):
        df = entrada.copy()
    else:
        df = pd.read_csv(entrada, encoding="utf-8-sig", **CSV)
        if df.shape[1] == 1:
            raise ValueError(f"{entrada}: se leyó una sola columna; ¿el separador no es ';'?")
    faltan = {"region_destrieux", *SEEG, *features} - set(df.columns)
    if faltan:
        raise ValueError(f"faltan columnas {sorted(faltan)}")
    if len(df) != N_PARCELAS or df["region_destrieux"].duplicated().any():
        raise ValueError(f"se esperaban {N_PARCELAS} regiones únicas, hay {df['region_destrieux'].nunique()}")
    no_numericas = [c for c in {*SEEG, *features} if not pd.api.types.is_numeric_dtype(df[c])]
    if no_numericas:
        raise ValueError(f"columnas con texto donde se esperaban números: {no_numericas} "
                         "(¿decimales con punto en vez de coma?)")
    return df.reset_index(drop=True)


def _distancias(pares, regiones) -> pd.DataFrame:
    """Saltos entre cada par de regiones (0 = la misma; inf = sin camino, p. ej. el otro hemisferio)."""
    regiones = list(regiones)
    a, b = (list(x) for x in zip(*pares))
    desconocidas = (set(a) | set(b)) - set(regiones)
    if desconocidas:
        raise ValueError(f"La vecindad nombra regiones que no están en la tabla: {sorted(desconocidas)[:5]}")
    posicion = pd.Series(range(len(regiones)), index=regiones)
    i, j = posicion.loc[a].to_numpy(), posicion.loc[b].to_numpy()
    grafo = coo_matrix((np.ones(len(i)), (i, j)), shape=(len(regiones), len(regiones)))
    return pd.DataFrame(shortest_path(grafo, directed=False, unweighted=True), index=regiones, columns=regiones)


def _peso_mapa(probabilidad: pd.Series, distancia: pd.DataFrame) -> pd.Series:
    """max(probabilidad propia, 0,6 × la de sus vecinas, 0,3 × la de sus vecinas de segundo orden)."""
    p = probabilidad.dropna()
    d = distancia.loc[p.index].to_numpy()
    factor = np.select([d == k for k in PESOS], list(PESOS.values()), default=0.0)
    return pd.Series((factor * p.to_numpy()[:, None]).max(axis=0, initial=0.0), index=distancia.columns)


def predecir(entrada, modelo: dict, detallada=False) -> pd.DataFrame:
    """Tabla final de las 148 regiones (region_destrieux, puntaje_soz, origen, probabilidad_soz).

    entrada: ruta a un CSV del paciente o un DataFrame con region_destrieux y las 4 columnas seeg_*.
    detallada=True devuelve en cambio la tabla completa: implantada, p_modelo, percentil, probabilidad, soz_predicha,
    orden y peso_mapa (la tabla final se obtiene de ella con salida_simple).
    """
    features = modelo["features"]
    recal = modelo["recalibracion"]
    if recal["metodo"] != "rango":
        raise ValueError(f"recalibración {recal['metodo']!r} no soportada: este módulo solo aplica 'rango'")
    df = _leer(entrada, features)
    implantada = df[SEEG].notna().any(axis=1).to_numpy()  # antes de enmascarar, como en el entrenamiento
    if not implantada.any():
        raise ValueError("ninguna parcela con sEEG: el modelo solo puntúa parcelas implantadas")
    no_disponibles = [c for c in features if df[c].nunique() <= 1]  # constante o vacía: no informa
    if no_disponibles:
        warnings.warn(f"features no disponibles, se imputan como en el entrenamiento: {no_disponibles}")
        df[no_disponibles] = np.nan
    X = df.loc[implantada, features].rank(pct=True)  # percentil dentro del paciente; los NaN se conservan
    p = modelo["pipeline"].predict_proba(X)[:, 1]
    percentil = pd.Series(p).rank(pct=True).to_numpy()  # 1 = la parcela implantada más sospechosa

    salida = df[["region_destrieux"]].assign(implantada=implantada)
    salida.loc[implantada, "p_modelo"] = p
    salida.loc[implantada, "percentil"] = percentil
    salida.loc[implantada, "probabilidad"] = 1 / (1 + np.exp(-(recal["a"] + recal["b"] * percentil)))
    salida["soz_predicha"] = ((salida["percentil"] >= modelo["umbral_relativo"]).astype("Int64")
                              .where(salida["implantada"]))
    salida["orden"] = salida["percentil"].rank(ascending=False, method="min").astype("Int64")
    distancia = _distancias(modelo["vecinos"], salida["region_destrieux"])
    por_region = salida.set_index("region_destrieux")
    marcada = por_region["soz_predicha"].eq(1).fillna(False).astype(bool)
    propagada = _peso_mapa(por_region.loc[marcada, "probabilidad"], distancia)  # solo desde las marcadas
    salida["peso_mapa"] = propagada.where(~marcada, por_region["probabilidad"]).to_numpy()
    salida = salida.sort_values(["orden", "peso_mapa"], ascending=[True, False], na_position="last",
                                ignore_index=True)
    return salida if detallada else salida_simple(salida)


def salida_simple(salida: pd.DataFrame) -> pd.DataFrame:
    """Las 148 regiones para el lector: puntaje_soz, origen y probabilidad_soz; primero las marcadas como SOZ.

    puntaje_soz: peso_mapa reescalado de 0 a 1 en el paciente (1 = su región más sospechosa); no es probabilidad.
    origen: "SOZ marcada (modelo)" o "propagación" (0,6 × / 0,3 × desde las marcadas).
    probabilidad_soz: peso_mapa sin reescalar, la probabilidad calibrada (la más sospechosa ronda 0,6).
    """
    marcada = salida["soz_predicha"].eq(1).fillna(False).astype(bool)
    peso = salida["peso_mapa"]
    s = pd.DataFrame({"region_destrieux": salida["region_destrieux"],
                      "puntaje_soz": (peso - peso.min()) / (peso.max() - peso.min()),
                      "origen": marcada.map({True: "SOZ marcada (modelo)", False: "propagación"}),
                      "probabilidad_soz": peso, "_m": marcada})
    return s.sort_values(["_m", "puntaje_soz"], ascending=False, ignore_index=True).drop(columns="_m")


def guardar_csv(tabla: pd.DataFrame, ruta) -> None:
    """CSV en el formato del proyecto (';', decimal ','), con BOM para que Excel en español lo abra bien."""
    tabla.to_csv(ruta, encoding="utf-8-sig", index=False, **CSV)
