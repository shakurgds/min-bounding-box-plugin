import math
import unittest

from tests.utilities import DIAMOND, L_SHAPE, TRIANGLE  # starts QGIS
from qgis.core import Qgis, QgsGeometry

from MinimumBoundingBox import core


def g(wkt):
    return QgsGeometry.fromWkt(wkt)


class BoundingGeometryTest(unittest.TestCase):
    def test_envelope(self):
        out, m = core.bounding_geometry(g(TRIANGLE), core.ENVELOPE)
        self.assertEqual(out.type(), Qgis.GeometryType.Polygon)
        self.assertAlmostEqual(m["width"], 4)
        self.assertAlmostEqual(m["height"], 3)
        self.assertAlmostEqual(m["angle"], 0)
        self.assertAlmostEqual(m["area"], 12)
        self.assertAlmostEqual(m["perimeter"], 14)
        self.assertAlmostEqual(m["fill_ratio"], 0.5)

    def test_oriented_rectangle_fits_rotated_square(self):
        _, env_m = core.bounding_geometry(g(DIAMOND), core.ENVELOPE)
        out, m = core.bounding_geometry(g(DIAMOND), core.ORIENTED)
        self.assertIsInstance(out, QgsGeometry)  # was a tuple before 2.0
        self.assertAlmostEqual(env_m["area"], 4)
        self.assertAlmostEqual(m["area"], 2, places=6)
        self.assertAlmostEqual(m["fill_ratio"], 1, places=6)
        self.assertAlmostEqual(m["width"] * m["height"], 2, places=6)
        self.assertAlmostEqual(m["angle"] % 90, 45, places=4)

    def test_oriented_never_larger_than_envelope(self):
        for wkt in (TRIANGLE, DIAMOND, L_SHAPE):
            _, env = core.bounding_geometry(g(wkt), core.ENVELOPE)
            _, ori = core.bounding_geometry(g(wkt), core.ORIENTED)
            self.assertLessEqual(ori["area"], env["area"] + 1e-9, wkt)

    def test_circle(self):
        rect = "POLYGON((0 0, 4 0, 4 3, 0 3, 0 0))"   # diagonal 5 -> radius 2.5
        out, m = core.bounding_geometry(g(rect), core.CIRCLE)
        self.assertEqual(out.type(), Qgis.GeometryType.Polygon)
        self.assertAlmostEqual(m["width"], 5, places=6)
        self.assertAlmostEqual(m["height"], 5, places=6)
        self.assertAlmostEqual(m["area"], math.pi * 6.25, delta=0.02 * math.pi * 6.25)

    def test_convex_hull(self):
        out, m = core.bounding_geometry(g(L_SHAPE), core.CONVEX_HULL)
        self.assertAlmostEqual(m["area"], 11.5)
        self.assertAlmostEqual(m["fill_ratio"], 7 / 11.5)
        self.assertTrue(out.contains(g(L_SHAPE).centroid()))

    def test_lines_have_no_fill_ratio(self):
        _, m = core.bounding_geometry(g("LINESTRING(0 0, 4 3)"), core.ENVELOPE)
        self.assertAlmostEqual(m["area"], 12)
        self.assertIsNone(m["fill_ratio"])

    def test_degenerate_results_are_skipped(self):
        self.assertEqual(core.bounding_geometry(g("POINT(1 1)"), core.CONVEX_HULL), (None, None))
        self.assertEqual(core.bounding_geometry(None, core.ENVELOPE), (None, None))
        self.assertEqual(core.bounding_geometry(QgsGeometry(), core.ENVELOPE), (None, None))

    def test_point_cloud(self):
        _, m = core.bounding_geometry(g("MULTIPOINT((0 0),(4 0),(2 3))"), core.CONVEX_HULL)
        self.assertAlmostEqual(m["area"], 6)
        self.assertIsNone(m["fill_ratio"])

    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            core.bounding_geometry(g(TRIANGLE), 99)


class HelpersTest(unittest.TestCase):
    def test_combine(self):
        self.assertIsNone(core.combine([]))
        self.assertIsNone(core.combine([None, QgsGeometry()]))
        one = core.combine([None, g(TRIANGLE)])
        self.assertAlmostEqual(one.area(), 6)
        both = core.combine([g(TRIANGLE), g(DIAMOND)])
        self.assertAlmostEqual(both.area(), 8)
        self.assertAlmostEqual(both.boundingBox().width(), 12)

    def test_clean_field_selection(self):
        self.assertEqual(
            core.clean_field_selection(["name", "grp", "min_x", "area", "name", ""], "grp"),
            ["name"])
        self.assertEqual(core.clean_field_selection(None, None), [])


if __name__ == "__main__":
    unittest.main()
