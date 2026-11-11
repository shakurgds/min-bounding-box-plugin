# Minimum Bounding Box (QGIS plugin)

Create bounding geometries for features in a vector layer: **envelope**, **minimum oriented rectangle**, **circle** or **convex hull**. You can make one per feature or one per group of features. Works in **QGIS 3.40+ and QGIS 4**.

Every output feature gets `min_x`, `min_y`, `max_x`, `max_y` and `extent` columns. Optionally it also gets these measurements, in the layer's CRS units:

| Column | Meaning |
|---|---|
| `width`, `height` | Side lengths of the bounding shape (circle: diameter) |
| `angle` | Rotation in degrees clockwise from north (minimum oriented rectangle only, otherwise 0) |
| `area`, `perimeter` | Of the bounding shape |
| `fill_ratio` | Source polygon area ÷ bounding area. 1 = fills its box completely, so this is a quick compactness / shape index. Empty for points and lines. |

Reproject a geographic (degree) layer to a projected CRS first if you want metres.

## Use it

- **Dialog:** *Plugins → Minimum Bounding Box → Create Minimum Bounding Box*, or the toolbar icon.
- **Processing Toolbox:** *Minimum Bounding Box → Minimum bounding geometry (with measurements)*. It works in the Graphical Modeler and in batch mode.
- **Python:**

```python
processing.run("minimumboundingbox:minimumboundinggeometry", {
    "INPUT": layer,
    "GEOMETRY_TYPE": 1,          # 0 envelope, 1 oriented rectangle, 2 circle, 3 convex hull
    "GROUP_FIELD": None,         # or a field name
    "FIELDS": ["name"],          # attributes to copy
    "ADD_MEASUREMENTS": True,
    "OUTPUT": "TEMPORARY_OUTPUT",
})
```

## Tests

The tests create their own in-memory layers and never touch your project.

**Inside QGIS** (Python Console):

```python
import runpy; runpy.run_path(r"C:\path\to\min-bounding-box-plugin\tests\run_in_qgis.py")
```

**Headless**, with the Python that ships with QGIS (on Windows, the `python-qgis*.bat` in the QGIS `bin` folder):

```
python-qgis.bat -m unittest discover -s tests -t . -v
```

Run it from the repository root.
