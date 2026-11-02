"""Genera los datos SINTÉTICOS de demostración de Visualizacion/Resources/Demo/.

No son datos de ningún paciente. Sirven para las pruebas de usabilidad y para
probar la extensión sin esperar las horas de FreeSurfer: el sujeto de
demostración es fsaverage (incluido en toda instalación de FreeSurfer).

  - caracteristicas_demo.csv: las 148 regiones Destrieux con valores sEEG
    simulados en 21 parcelas implantadas (lóbulo temporal y frontal izquierdo),
    más altos en el polo temporal, el parahipocampo y la temporal inferior.
  - eeg_superficie_demo.csv: 19 electrodos del sistema 10-20.
  - seeg_dipolos_demo.tsv: 3 electrodos de profundidad (canales bipolares) en
    coordenadas World de fsaverage/mri/orig.mgz, que entran en la corteza.

Uso (desde la carpeta Visualizacion_epilepsia):
  /Applications/Slicer.app/Contents/MacOS/Slicer --no-splash --no-main-window \
      --python-script Docs/herramientas/generar_datos_demo.py \
      /Applications/freesurfer/8.2.0/subjects/fsaverage
"""
import csv
import sys
from pathlib import Path

import nibabel as nib
import numpy as np

RAIZ = Path(__file__).resolve().parents[2]
DESTINO = RAIZ / "Visualizacion" / "Resources" / "Demo"
sys.path.insert(0, str(RAIZ / "Inferencia"))

import inferencia_ml  # noqa: E402
import soz_inferencia  # noqa: E402

# Foco simulado: estas parcelas reciben los valores más altos.
FOCO = ["Pole_temporal L", "G_oc-temp_med-Parahip L", "G_temporal_inf L"]

# Electrodos SEEG: nombre -> parcela de entrada (hemisferio izquierdo).
ELECTRODOS = {"TP": "Pole_temporal", "TM": "G_temporal_middle", "FM": "G_front_middle"}
CONTACTOS = 10
PASO_MM = 3.5

EEG_1020 = ["Fp1", "Fp2", "F7", "F3", "Fz", "F4", "F8", "T7", "C3", "Cz",
            "C4", "T8", "P7", "P3", "Pz", "P4", "P8", "O1", "O2"]


def caracteristicas(rng):
    modelo = inferencia_ml.cargarModelo()
    regiones = sorted({r for par in modelo["vecinos"] for r in par})
    implantadas = [
        r for r in regiones
        if r.endswith(" L") and any(t in r for t in ("temp", "Temp", "Parahip", "front_middle", "front_inf"))
    ][:30]
    for r in FOCO:
        assert r in implantadas, r

    with (DESTINO / "caracteristicas_demo.csv").open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.writer(f, delimiter=";")
        escritor.writerow(["region_destrieux", *soz_inferencia.SEEG])
        for r in regiones:
            if r not in implantadas:
                escritor.writerow([r, "", "", "", ""])
                continue
            base = 0.75 if r in FOCO else 0.25
            valores = np.clip(base + rng.normal(0, 0.1, len(soz_inferencia.SEEG)), 0.01, 1.0)
            escritor.writerow([r, *[f"{v:.4f}".replace(".", ",") for v in valores]])
    return len(implantadas)


def seeg(fsaverage):
    vertices, _ = nib.freesurfer.read_geometry(str(fsaverage / "surf" / "lh.pial"))
    etiquetas, _, nombres = nib.freesurfer.read_annot(str(fsaverage / "label" / "lh.aparc.a2009s.annot"))
    nombres = [n.decode() if isinstance(n, bytes) else n for n in nombres]
    centro = vertices.mean(axis=0)

    img = nib.load(str(fsaverage / "mri" / "orig.mgz"))
    tkr = np.asarray(img.header.get_vox2ras_tkr(), dtype=float)
    tkrAWorld = np.asarray(img.affine, dtype=float) @ np.linalg.inv(tkr)

    filas = []
    for electrodo, region in ELECTRODOS.items():
        puntos = vertices[etiquetas == nombres.index(region)]
        entrada = puntos[np.argmin(np.linalg.norm(puntos - puntos.mean(axis=0), axis=1))]
        direccion = (centro - entrada) / np.linalg.norm(centro - entrada)
        contactos = [entrada + direccion * (1.0 + PASO_MM * k) for k in range(CONTACTOS)]
        for n in range(1, CONTACTOS):
            medio = (contactos[n - 1] + contactos[n]) / 2.0
            mundo = (tkrAWorld @ np.append(medio, 1.0))[:3]
            filas.append((f"{electrodo}{n}-{electrodo}{n + 1}", mundo))

    with (DESTINO / "seeg_dipolos_demo.tsv").open("w", encoding="utf-8", newline="") as f:
        f.write("Channel\tWorld\n")
        for canal, p in filas:
            f.write(f"{canal}\t{p[0]:.3f} {p[1]:.3f} {p[2]:.3f}\n")
    return len(filas)


def eeg():
    (DESTINO / "eeg_superficie_demo.csv").write_text(
        "electrode\n" + "\n".join(EEG_1020) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    fsaverage = Path(sys.argv[-1])
    DESTINO.mkdir(parents=True, exist_ok=True)
    print("Parcelas implantadas:", caracteristicas(np.random.default_rng(20261102)))
    print("Canales SEEG:", seeg(fsaverage))
    eeg()
    print("Datos de demostración en", DESTINO)
    try:
        import slicer
        slicer.app.exit(0)
    except ImportError:
        pass
