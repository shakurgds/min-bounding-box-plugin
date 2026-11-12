"""Processing algorithm: minimum bounding geometry with measurements.

Usable from the Processing Toolbox, Graphical Modeler, batch mode and
processing.run("minimumboundingbox:minimumboundinggeometry", {...}).
"""
import os

from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    Qgis, QgsFeature, QgsFeatureSink, QgsProcessingAlgorithm,
    QgsProcessingException, QgsProcessingParameterBoolean,
    QgsProcessingParameterEnum, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterFeatureSource, QgsProcessingParameterField,
)

from . import core


class MinimumBoundingGeometryAlgorithm(QgsProcessingAlgorithm):
    INPUT = "INPUT"
    GEOMETRY_TYPE = "GEOMETRY_TYPE"
    GROUP_FIELD = "GROUP_FIELD"
    FIELDS = "FIELDS"
    ADD_MEASUREMENTS = "ADD_MEASUREMENTS"
    OUTPUT = "OUTPUT"

    def name(self):
        return "minimumboundinggeometry"

    def displayName(self):
        return "Minimum bounding geometry (with measurements)"

    def group(self):
        return ""

    def groupId(self):
        return ""

    def icon(self):
        return QIcon(os.path.join(os.path.dirname(__file__), "Icon.png"))

    def shortHelpString(self):
        return (
            "Creates a bounding geometry (envelope, minimum oriented rectangle, "
            "circle or convex hull) for each feature, or for each group of "
            "features sharing a value in the group field.\n\n"
            "Output columns: min_x, min_y, max_x, max_y, extent and, optionally, "
            "width, height, angle (degrees clockwise from north, oriented "
            "rectangle only), area, perimeter and fill_ratio (source polygon "
            "area / bounding area; 1 = the shape fills its box, empty for "
            "points and lines).\n\n"
            "Measurements are in the input layer's CRS units. Reproject a "
            "geographic (degree) layer first for metres."
        )

    def createInstance(self):
        return MinimumBoundingGeometryAlgorithm()

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterFeatureSource(
            self.INPUT, "Input layer",
            [Qgis.ProcessingSourceType.VectorAnyGeometry]))
        self.addParameter(QgsProcessingParameterEnum(
            self.GEOMETRY_TYPE, "Geometry type",
            options=core.GEOMETRY_TYPES, defaultValue=core.ENVELOPE))
        self.addParameter(QgsProcessingParameterField(
            self.GROUP_FIELD, "Group by field",
            parentLayerParameterName=self.INPUT, optional=True))
        self.addParameter(QgsProcessingParameterField(
            self.FIELDS, "Attributes to copy (from the first feature of each group)",
            parentLayerParameterName=self.INPUT, allowMultiple=True,
            optional=True))
        self.addParameter(QgsProcessingParameterBoolean(
            self.ADD_MEASUREMENTS,
            "Add measurement fields (width, height, angle, area, perimeter, fill ratio)",
            defaultValue=True))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Bounding geometries",
            Qgis.ProcessingSourceType.VectorPolygon))

    def _strings(self, parameters, name, context):
        # parameterAsFields was deprecated in favour of parameterAsStrings
        fn = getattr(self, "parameterAsStrings", None) or self.parameterAsFields
        return list(fn(parameters, name, context) or [])

    def processAlgorithm(self, parameters, context, feedback):
        source = self.parameterAsSource(parameters, self.INPUT, context)
        if source is None:
            raise QgsProcessingException(
                self.invalidSourceError(parameters, self.INPUT))

        geometry_type = self.parameterAsEnum(parameters, self.GEOMETRY_TYPE, context)
        group_field = self.parameterAsString(parameters, self.GROUP_FIELD, context) or None
        add_measures = self.parameterAsBool(parameters, self.ADD_MEASUREMENTS, context)
        selected = core.clean_field_selection(
            self._strings(parameters, self.FIELDS, context), group_field)

        src_fields = source.fields()
        for name in ([group_field] if group_field else []) + selected:
            if src_fields.indexOf(name) < 0:
                raise QgsProcessingException(f"Field not found: {name}")

        fields = core.build_fields(src_fields, group_field, selected, add_measures)
        sink, dest_id = self.parameterAsSink(
            parameters, self.OUTPUT, context, fields,
            Qgis.WkbType.Polygon, source.sourceCrs())
        if sink is None:
            raise QgsProcessingException(
                self.invalidSinkError(parameters, self.OUTPUT))

        total = source.featureCount()
        step = 100.0 / total if total and total > 0 else 0

        # (group value, [geometries], first feature) batches
        if group_field:
            groups = {}
            for i, f in enumerate(source.getFeatures()):
                if feedback.isCanceled():
                    break
                entry = groups.setdefault(f[group_field], ([], QgsFeature(f)))
                if f.hasGeometry():
                    entry[0].append(f.geometry())
                feedback.setProgress(i * step * 0.5)
            batches = [(k, g, f) for k, (g, f) in groups.items()]
            base, step = 50.0, (50.0 / len(batches) if batches else 0)
        else:
            batches = ((None, [f.geometry()] if f.hasGeometry() else [], f)
                       for f in source.getFeatures())
            base = 0.0

        written = skipped = 0
        for i, (group_value, geoms, first) in enumerate(batches):
            if feedback.isCanceled():
                break
            feedback.setProgress(base + i * step)

            out, measures = core.bounding_geometry(core.combine(geoms), geometry_type)
            if out is None:
                skipped += 1
                continue

            feat = QgsFeature(fields)
            feat.setGeometry(out)
            feat.setAttributes(core.build_attributes(
                out, measures, add_measures, group_field, group_value,
                first, selected))
            sink.addFeature(feat, QgsFeatureSink.Flag.FastInsert)
            written += 1

        if skipped:
            feedback.pushWarning(
                f"{skipped} feature(s)/group(s) skipped: no geometry, or the "
                "result was not a polygon (e.g. convex hull of a single point).")
        feedback.pushInfo(f"{written} bounding geometries written.")
        return {self.OUTPUT: dest_id}
