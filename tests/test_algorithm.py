import os
import shutil
import tempfile
import unittest

from tests.utilities import TRIANGLE, make_layer, sample_layer  # starts QGIS
from qgis.core import (
    QgsProcessingContext, QgsProcessingException, QgsProcessingFeatureSourceDefinition,
    QgsProcessingFeedback, QgsProject, QgsVectorLayer,
)

from MinimumBoundingBox import core
from MinimumBoundingBox.algorithm import MinimumBoundingGeometryAlgorithm as Alg


def run(params, context=None):
    """Run the algorithm directly; returns the output layer (or file path)."""
    alg = Alg()
    alg.initAlgorithm({})
    context = context or QgsProcessingContext()
    params = dict(params)
    params.setdefault(Alg.OUTPUT, "TEMPORARY_OUTPUT")
    results, ok = alg.run(params, context, QgsProcessingFeedback(),
                          catchExceptions=False)
    assert ok
    out = results[Alg.OUTPUT]
    if os.path.exists(out.split("|")[0]):
        return out
    # Take ownership, otherwise the layer dies with the context.
    return context.takeResultLayer(out)


def by_name(layer):
    return {f["name"]: f for f in layer.getFeatures()}


class AlgorithmTest(unittest.TestCase):
    def setUp(self):
        self.layer = sample_layer()

    def test_per_feature_with_measurements(self):
        out = run({Alg.INPUT: self.layer, Alg.GEOMETRY_TYPE: core.ENVELOPE,
                   Alg.FIELDS: ["name"]})
        self.assertEqual(out.featureCount(), 3)
        self.assertEqual(out.fields().names(),
                         list(core.EXTENT_FIELDS) + list(core.MEASURE_FIELDS) + ["name"])
        tri = by_name(out)["triangle"]
        self.assertAlmostEqual(tri["max_x"], 4)
        self.assertAlmostEqual(tri["area"], 12)
        self.assertAlmostEqual(tri["fill_ratio"], 0.5)

    def test_every_geometry_type_produces_polygons(self):
        for gtype, label in enumerate(core.GEOMETRY_TYPES):
            out = run({Alg.INPUT: self.layer, Alg.GEOMETRY_TYPE: gtype})
            self.assertEqual(out.featureCount(), 3, label)
            for f in out.getFeatures():
                self.assertGreater(f.geometry().area(), 0, label)

    def test_without_measurements(self):
        out = run({Alg.INPUT: self.layer, Alg.ADD_MEASUREMENTS: False})
        self.assertEqual(out.fields().names(), list(core.EXTENT_FIELDS))

    def test_group_by(self):
        out = run({Alg.INPUT: self.layer, Alg.GROUP_FIELD: "grp",
                   Alg.FIELDS: ["grp", "name"]})   # grp listed twice on purpose
        self.assertEqual(out.fields().names().count("grp"), 1)
        groups = {f["grp"]: f for f in out.getFeatures()}
        self.assertEqual(set(groups), {0, 1})
        g0 = groups[0]  # triangle (0..4) + L-shape (20..24)
        self.assertAlmostEqual(g0["min_x"], 0)
        self.assertAlmostEqual(g0["max_x"], 24)
        self.assertAlmostEqual(g0["fill_ratio"], (6 + 7) / (24 * 4))
        self.assertEqual(g0["name"], "triangle")  # first feature of the group

    def test_features_without_geometry_are_skipped(self):
        layer = make_layer([(TRIANGLE, ["a", 0]), (None, ["b", 0])])
        out = run({Alg.INPUT: layer})
        self.assertEqual(out.featureCount(), 1)

    def test_selected_features_only(self):
        project = QgsProject()
        project.addMapLayer(self.layer)
        self.layer.selectByExpression("\"name\" = 'diamond'")
        context = QgsProcessingContext()
        context.setProject(project)
        out = run({Alg.INPUT: QgsProcessingFeatureSourceDefinition(self.layer.id(), True)},
                  context)
        self.assertEqual(out.featureCount(), 1)

    def test_unknown_field_raises(self):
        with self.assertRaises(QgsProcessingException):
            run({Alg.INPUT: self.layer, Alg.FIELDS: ["nope"]})

    def test_geopackage_output(self):
        tmp = tempfile.mkdtemp()
        try:
            path = os.path.join(tmp, "boxes.gpkg")
            out = run({Alg.INPUT: self.layer, Alg.GEOMETRY_TYPE: core.ORIENTED,
                       Alg.FIELDS: ["name"], Alg.OUTPUT: path})
            saved = QgsVectorLayer(out, "boxes", "ogr")
            self.assertTrue(saved.isValid())
            self.assertEqual(saved.featureCount(), 3)
            self.assertAlmostEqual(by_name(saved)["diamond"]["fill_ratio"], 1, places=6)
            del saved
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
