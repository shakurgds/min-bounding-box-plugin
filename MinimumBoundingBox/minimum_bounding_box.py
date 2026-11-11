"""Minimum Bounding Box - QGIS plugin.

Compatible with QGIS 3.40+ (Qt5) and QGIS 4.x (Qt6).
All Qt enums use their fully scoped names, which work in both PyQt5 and PyQt6.
The dialog is a friendly front end; the work is done by the Processing
algorithm in algorithm.py, which is also available in the Processing Toolbox.
"""
import os.path

from qgis.PyQt.QtWidgets import (
    QDialog, QProgressDialog,
    QVBoxLayout, QLabel, QComboBox, QPushButton,
    QDialogButtonBox, QListWidget, QListWidgetItem,
    QCheckBox, QFileDialog, QHBoxLayout, QLineEdit,
    QToolButton, QGroupBox
)
from qgis.PyQt.QtCore import QObject, Qt
from qgis.PyQt.QtGui import QIcon

# QAction lives in QtGui on Qt6 and in QtWidgets on Qt5.
try:
    from qgis.PyQt.QtGui import QAction
except ImportError:
    from qgis.PyQt.QtWidgets import QAction

from qgis.core import (
    Qgis, QgsApplication, QgsMapLayer, QgsProcessingContext,
    QgsProcessingFeatureSourceDefinition,
    QgsProcessingFeedback, QgsProject, QgsVectorLayer
)
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox

from . import core
from .algorithm import MinimumBoundingGeometryAlgorithm as Alg
from .provider import ALGORITHM_ID, MinimumBoundingBoxProvider


CHECKED = Qt.CheckState.Checked
UNCHECKED = Qt.CheckState.Unchecked
OK_CANCEL = (QDialogButtonBox.StandardButton.Ok
             | QDialogButtonBox.StandardButton.Cancel)


class FieldSelectorDialog(QDialog):
    def __init__(self, layer, preselected=None, parent=None):
        super().__init__(parent)
        self.layer = layer
        self.preselected = set(preselected or [])
        self.setWindowTitle("Select Fields")
        self.setup_ui()
        self.setMinimumWidth(400)
        self.setMinimumHeight(500)

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        self.field_list = QListWidget()
        self.field_list.setMinimumHeight(300)
        layout.addWidget(self.field_list)
        layout.addSpacing(10)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.select_all_btn = QPushButton("Select All")
        self.clear_btn = QPushButton("Clear Selection")
        self.toggle_btn = QPushButton("Toggle Selection")
        for btn in (self.select_all_btn, self.clear_btn, self.toggle_btn):
            btn.setMinimumWidth(100)
            btn.setMinimumHeight(30)
            button_layout.addWidget(btn)
        self.select_all_btn.clicked.connect(self.select_all)
        self.clear_btn.clicked.connect(self.clear_selection)
        self.toggle_btn.clicked.connect(self.toggle_selection)
        layout.addLayout(button_layout)
        layout.addSpacing(10)

        self.button_box = QDialogButtonBox(OK_CANCEL)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

        if self.layer:
            for field in self.layer.fields():
                item = QListWidgetItem(field.name())
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    CHECKED if field.name() in self.preselected else UNCHECKED)
                self.field_list.addItem(item)

    def _items(self):
        return [self.field_list.item(i) for i in range(self.field_list.count())]

    def select_all(self):
        for item in self._items():
            item.setCheckState(CHECKED)

    def clear_selection(self):
        for item in self._items():
            item.setCheckState(UNCHECKED)

    def toggle_selection(self):
        for item in self._items():
            item.setCheckState(
                CHECKED if item.checkState() == UNCHECKED else UNCHECKED)

    def get_selected_fields(self):
        return [i.text() for i in self._items() if i.checkState() == CHECKED]


class MBBDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Minimum Bounding Box")
        self.selected_fields = []
        self.setup_ui()
        self.setMinimumWidth(500)
        self.setMinimumHeight(400)

    def setup_ui(self):
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        # Layer selection
        layout.addWidget(QLabel("Select Input Layer:"))
        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(Qgis.LayerFilter.VectorLayer)
        self.layer_combo.setMinimumHeight(30)
        layout.addWidget(self.layer_combo)
        self.selected_only = QCheckBox("Selected features only")
        layout.addWidget(self.selected_only)
        layout.addSpacing(10)

        # Geometry type selection
        layout.addWidget(QLabel("Select Geometry Type:"))
        self.geometry_type = QComboBox()
        self.geometry_type.addItems(core.GEOMETRY_TYPES)
        self.geometry_type.setMinimumHeight(30)
        layout.addWidget(self.geometry_type)
        layout.addSpacing(10)

        # Grouping options
        group_box = QGroupBox("Grouping Options")
        group_layout = QVBoxLayout()
        self.group_check = QCheckBox("Group by field")
        group_layout.addWidget(self.group_check)
        self.group_field = QgsFieldComboBox()
        self.group_field.setEnabled(False)
        self.group_check.toggled.connect(self.group_field.setEnabled)
        group_layout.addWidget(self.group_field)
        group_box.setLayout(group_layout)
        layout.addWidget(group_box)
        layout.addSpacing(10)

        # Field selection
        field_layout = QHBoxLayout()
        field_layout.setSpacing(10)
        self.field_label = QLabel("Selected Fields: 0")
        self.field_button = QToolButton()
        self.field_button.setText("...")
        self.field_button.setMinimumWidth(40)
        self.field_button.setMinimumHeight(30)
        self.field_button.clicked.connect(self.show_field_selector)
        field_layout.addWidget(self.field_label)
        field_layout.addWidget(self.field_button)
        field_layout.addStretch()
        layout.addLayout(field_layout)

        # Measurements
        self.measure_check = QCheckBox(
            "Add measurement fields (width, height, angle, area, perimeter, fill ratio)")
        self.measure_check.setChecked(True)
        layout.addWidget(self.measure_check)
        layout.addSpacing(10)

        # Output
        layout.addWidget(QLabel("Output (leave empty for memory layer):"))
        output_layout = QHBoxLayout()
        output_layout.setSpacing(10)
        self.output_path = QLineEdit()
        self.output_path.setPlaceholderText("Layer name or file path...")
        self.output_path.setMinimumHeight(30)
        output_layout.addWidget(self.output_path)
        self.browse_button = QPushButton("Browse...")
        self.browse_button.setMinimumWidth(80)
        self.browse_button.setMinimumHeight(30)
        self.browse_button.clicked.connect(self.browse_output)
        output_layout.addWidget(self.browse_button)
        layout.addLayout(output_layout)
        layout.addSpacing(20)

        self.button_box = QDialogButtonBox(OK_CANCEL)
        for button in self.button_box.buttons():
            button.setMinimumWidth(80)
            button.setMinimumHeight(30)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

        # Keep the group-field combo and selected fields in sync with the layer
        self.layer_combo.layerChanged.connect(self.on_layer_changed)
        self.on_layer_changed(self.layer_combo.currentLayer())

    def on_layer_changed(self, layer):
        self.group_field.setLayer(layer)
        self.selected_fields = []
        self.field_label.setText("Selected Fields: 0")
        has_selection = bool(layer) and layer.selectedFeatureCount() > 0
        self.selected_only.setEnabled(has_selection)
        self.selected_only.setChecked(False)

    def browse_output(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Output Layer", "",
            "GeoPackage (*.gpkg);;Shapefile (*.shp)"
        )
        if file_path:
            self.output_path.setText(file_path)

    def show_field_selector(self):
        layer = self.layer_combo.currentLayer()
        if not layer:
            return
        dialog = FieldSelectorDialog(layer, self.selected_fields, self)
        if dialog.exec():
            self.selected_fields = dialog.get_selected_fields()
            self.field_label.setText(
                f"Selected Fields: {len(self.selected_fields)}")

    def get_selected_fields(self):
        return self.selected_fields

    def get_output_info(self):
        path = self.output_path.text().strip()
        if path.lower().endswith((".gpkg", ".shp")):
            return True, path
        return False, path or "Minimum_Bounding_Box"

    def algorithm_parameters(self):
        """Translate the dialog state into Processing parameters."""
        layer = self.layer_combo.currentLayer()
        is_file, output = self.get_output_info()
        group_field = (self.group_field.currentField()
                       if self.group_check.isChecked() else None)
        source = layer
        if layer is not None and self.selected_only.isChecked():
            source = QgsProcessingFeatureSourceDefinition(layer.id(), True)
        return {
            Alg.INPUT: source,
            Alg.GEOMETRY_TYPE: self.geometry_type.currentIndex(),
            Alg.GROUP_FIELD: group_field,
            Alg.FIELDS: self.get_selected_fields(),
            Alg.ADD_MEASUREMENTS: self.measure_check.isChecked(),
            Alg.OUTPUT: output if is_file else "memory:",
        }, is_file, output


class MinimumBoundingBox(QObject):
    def __init__(self, iface):
        super().__init__()
        self.iface = iface
        self.actions = []
        self.provider = None
        self.menu = "Minimum Bounding Box"
        self.plugin_dir = os.path.dirname(__file__)

    def initProcessing(self):
        self.provider = MinimumBoundingBoxProvider()
        QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()
        icon_path = os.path.join(self.plugin_dir, "Icon.png")
        self.action = QAction(
            QIcon(icon_path),
            "Create Minimum Bounding Box",
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)
        self.iface.addPluginToMenu(self.menu, self.action)
        self.iface.addToolBarIcon(self.action)
        self.actions.append(self.action)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu, action)
            self.iface.removeToolBarIcon(action)
        self.actions = []
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None

    def run(self):
        dialog = MBBDialog(self.iface.mainWindow())
        if not dialog.exec():
            return

        if not dialog.layer_combo.currentLayer():
            self.show_error("No layer selected")
            return
        if dialog.group_check.isChecked() and not dialog.group_field.currentField():
            self.show_error("Choose a field to group by")
            return

        params, is_file, output = dialog.algorithm_parameters()
        try:
            layer = self.run_algorithm(params)
        except Exception as e:  # noqa: BLE001 - surface any error to the user
            self.show_error(str(e))
            return
        if layer is None:  # cancelled
            return

        if isinstance(layer, QgsMapLayer):
            layer.setName(output)
        else:  # file output: Processing returns the path
            name = os.path.splitext(os.path.basename(output))[0]
            layer = QgsVectorLayer(layer, name, "ogr")
            if not layer.isValid():
                self.show_error("Failed to load the saved layer")
                return
        QgsProject.instance().addMapLayer(layer)
        self.iface.messageBar().pushMessage(
            "Success", "Minimum bounding geometries created successfully",
            level=Qgis.MessageLevel.Success, duration=5
        )

    def run_algorithm(self, params):
        """Run the Processing algorithm with a cancellable progress dialog.

        Returns the output layer (memory) or path (file), or None if cancelled.
        """
        import processing

        progress = QProgressDialog(
            "Creating minimum bounding geometries...", "Cancel",
            0, 100, self.iface.mainWindow())
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        feedback = QgsProcessingFeedback()

        def on_progress(value):
            progress.setValue(int(value))
            if progress.wasCanceled():
                feedback.cancel()

        feedback.progressChanged.connect(on_progress)
        context = QgsProcessingContext()
        context.setProject(QgsProject.instance())
        try:
            result = processing.run(ALGORITHM_ID, params,
                                    context=context, feedback=feedback)
        finally:
            progress.close()
        if feedback.isCanceled():
            return None
        return result["OUTPUT"]

    def show_error(self, message):
        self.iface.messageBar().pushMessage(
            "Error", message, level=Qgis.MessageLevel.Critical, duration=5
        )
