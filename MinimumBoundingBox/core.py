"""Geometry and measurement logic shared by the dialog and the Processing algorithm.

No GUI code here, so it can be unit-tested headless on QGIS 3.40+ and QGIS 4.
"""
import math

from qgis.PyQt.QtCore import QMetaType
from qgis.core import Qgis, QgsField, QgsFields, QgsGeometry

ENVELOPE, ORIENTED, CIRCLE, CONVEX_HULL = range(4)
GEOMETRY_TYPES = [
    "Envelope (Bounding Box)",
    "Minimum Oriented Rectangle",
    "Circle",
    "Convex Hull",
]

EXTENT_FIELDS = ("min_x", "min_y", "max_x", "max_y", "extent")
MEASURE_FIELDS = ("width", "height", "angle", "area", "perimeter", "fill_ratio")
RESERVED_FIELDS = EXTENT_FIELDS + MEASURE_FIELDS


def combine(geometries):
    """Union the non-empty geometries; None if there is nothing to bound."""
    geoms = [g for g in geometries if g is not None and not g.isNull() and not g.isEmpty()]
    if not geoms:
        return None
    combined = geoms[0] if len(geoms) == 1 else QgsGeometry.unaryUnion(geoms)
    if combined is None or combined.isNull() or combined.isEmpty():
        return None
    return combined


def bounding_geometry(geom, geometry_type):
    """Return (bounding polygon, measurements dict), or (None, None).

    Measurements are in the layer's CRS units:
      width, height  - side lengths (circle: diameter); oriented rectangle uses
                       QGIS's own width/height of the rotated box
      angle          - rotation in degrees clockwise from north (0 unless oriented)
      area, perimeter- of the bounding geometry
      fill_ratio     - source polygon area / bounding area (None for points/lines)
    """
    if geom is None or geom.isEmpty():
        return None, None

    angle = 0.0
    if geometry_type == ENVELOPE:
        rect = geom.boundingBox()
        out = QgsGeometry.fromRect(rect)
        width, height = rect.width(), rect.height()
    elif geometry_type == ORIENTED:
        out, _area, angle, width, height = geom.orientedMinimumBoundingBox()
    elif geometry_type == CIRCLE:
        out, _center, radius = geom.minimalEnclosingCircle()
        width = height = 2 * radius
    elif geometry_type == CONVEX_HULL:
        out = geom.convexHull()
        rect = out.boundingBox() if out else None
        width, height = (rect.width(), rect.height()) if rect else (0.0, 0.0)
    else:
        raise ValueError(f"Unknown geometry type: {geometry_type}")

    # Output layer is polygon: skip degenerate results (point/line hulls etc.)
    if out is None or out.isEmpty() or out.type() != Qgis.GeometryType.Polygon:
        return None, None

    area = out.area()
    fill_ratio = None
    if geom.type() == Qgis.GeometryType.Polygon and area > 0:
        fill_ratio = geom.area() / area

    measures = {
        "width": float(width),
        "height": float(height),
        "angle": float(angle) if math.isfinite(angle) else 0.0,
        "area": area,
        "perimeter": out.length(),
        "fill_ratio": fill_ratio,
    }
    return out, measures


def extent_values(geom):
    bbox = geom.boundingBox()
    return [bbox.xMinimum(), bbox.yMinimum(), bbox.xMaximum(), bbox.yMaximum(),
            bbox.toString()]


def clean_field_selection(selected, group_field):
    """Drop the group field (added separately) and names clashing with output columns."""
    seen, result = set(), []
    for name in selected or []:
        if name and name != group_field and name not in RESERVED_FIELDS and name not in seen:
            seen.add(name)
            result.append(name)
    return result


def build_fields(source_fields, group_field, selected_fields, add_measures):
    fields = QgsFields()
    for name in EXTENT_FIELDS[:4]:
        fields.append(QgsField(name, QMetaType.Type.Double))
    fields.append(QgsField("extent", QMetaType.Type.QString))
    if add_measures:
        for name in MEASURE_FIELDS:
            fields.append(QgsField(name, QMetaType.Type.Double))
    for name in ([group_field] if group_field else []) + list(selected_fields):
        fields.append(QgsField(source_fields.field(name)))
    return fields


def build_attributes(out_geom, measures, add_measures, group_field, group_value,
                     first_feature, selected_fields):
    attrs = extent_values(out_geom)
    if add_measures:
        attrs.extend(measures[name] for name in MEASURE_FIELDS)
    if group_field:
        attrs.append(group_value)
    attrs.extend(first_feature[name] for name in selected_fields)
    return attrs
