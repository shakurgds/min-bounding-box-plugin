"""Shared test helpers. Works headless (python -m unittest) and inside QGIS."""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from qgis.core import QgsApplication  # noqa: E402

_APP = None


def ensure_app():
    """Start a QgsApplication when not already running inside QGIS."""
    global _APP
    if QgsApplication.instance() is None:
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from qgis.testing import start_app
        _APP = start_app()
        # Headless: QGIS's bundled plugins (incl. processing) aren't on sys.path
        plugins = os.path.join(QgsApplication.pkgDataPath(), "python", "plugins")
        if os.path.isdir(plugins) and plugins not in sys.path:
            sys.path.append(plugins)
    try:  # needed for processing.run() in headless runs; no-op inside QGIS
        from processing.core.Processing import Processing
        Processing.initialize()
    except Exception:  # noqa: BLE001
        pass


ensure_app()

from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer  # noqa: E402

DEFAULT_FIELDS = "field=name:string&field=grp:integer"


def make_layer(rows, geom_type="Polygon", crs="EPSG:32638", fields=DEFAULT_FIELDS):
    """rows: list of (wkt or None, [attributes])."""
    layer = QgsVectorLayer(f"{geom_type}?crs={crs}&{fields}", "test", "memory")
    assert layer.isValid()
    feats = []
    for wkt, attrs in rows:
        f = QgsFeature(layer.fields())
        if wkt:
            f.setGeometry(QgsGeometry.fromWkt(wkt))
        f.setAttributes(attrs)
        feats.append(f)
    layer.dataProvider().addFeatures(feats)
    layer.updateExtents()
    return layer


TRIANGLE = "POLYGON((0 0, 4 0, 0 3, 0 0))"                       # area 6
DIAMOND = "POLYGON((10 1, 11 0, 12 1, 11 2, 10 1))"               # 45 deg square, area 2
L_SHAPE = "POLYGON((20 0, 24 0, 24 1, 21 1, 21 4, 20 4, 20 0))"   # area 7


def sample_layer():
    return make_layer([
        (TRIANGLE, ["triangle", 0]),
        (DIAMOND, ["diamond", 1]),
        (L_SHAPE, ["lshape", 0]),
    ])
