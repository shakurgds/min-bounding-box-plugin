import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingProvider

from .algorithm import MinimumBoundingGeometryAlgorithm

PROVIDER_ID = "minimumboundingbox"
ALGORITHM_ID = f"{PROVIDER_ID}:minimumboundinggeometry"


class MinimumBoundingBoxProvider(QgsProcessingProvider):
    def id(self):
        return PROVIDER_ID

    def name(self):
        return "Minimum Bounding Box"

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "Icon.png"))

    def loadAlgorithms(self):
        self.addAlgorithm(MinimumBoundingGeometryAlgorithm())
