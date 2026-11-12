"""Plugin-level checks: Qt5/Qt6 imports, dialogs, provider registration."""
import unittest

from tests.utilities import sample_layer  # starts QGIS
from qgis.core import QgsApplication, QgsProcessingContext, QgsProcessingFeedback

import MinimumBoundingBox
from MinimumBoundingBox import minimum_bounding_box as mbb
from MinimumBoundingBox.provider import ALGORITHM_ID, PROVIDER_ID


class _Bar:
    def pushMessage(self, *args, **kwargs):
        pass


class StubIface:
    """Just enough of QgisInterface for initGui/unload."""
    def __init__(self):
        self.menu_actions, self.toolbar_actions = [], []

    def mainWindow(self):
        return None

    def messageBar(self):
        return _Bar()

    def addPluginToMenu(self, menu, action):
        self.menu_actions.append(action)

    def removePluginMenu(self, menu, action):
        self.menu_actions.remove(action)

    def addToolBarIcon(self, action):
        self.toolbar_actions.append(action)

    def removeToolBarIcon(self, action):
        self.toolbar_actions.remove(action)


def registry():
    return QgsApplication.processingRegistry()


class DialogTest(unittest.TestCase):
    def test_main_dialog_defaults(self):
        dlg = mbb.MBBDialog()
        params, is_file, output = dlg.algorithm_parameters()
        self.assertFalse(is_file)
        self.assertEqual(output, "Minimum_Bounding_Box")
        self.assertEqual(params[mbb.Alg.OUTPUT], "memory:")
        self.assertIsNone(params[mbb.Alg.GROUP_FIELD])
        self.assertTrue(params[mbb.Alg.ADD_MEASUREMENTS])
        dlg.output_path.setText("C:/tmp/out.GPKG")
        self.assertEqual(dlg.get_output_info(), (True, "C:/tmp/out.GPKG"))
        dlg.deleteLater()

    def test_field_selector(self):
        dlg = mbb.FieldSelectorDialog(sample_layer(), ["grp"])
        self.assertEqual(dlg.get_selected_fields(), ["grp"])
        dlg.toggle_selection()
        self.assertEqual(dlg.get_selected_fields(), ["name"])
        dlg.select_all()
        self.assertEqual(dlg.get_selected_fields(), ["name", "grp"])
        dlg.clear_selection()
        self.assertEqual(dlg.get_selected_fields(), [])
        dlg.deleteLater()


@unittest.skipIf(registry().providerById(PROVIDER_ID) is not None,
                 "installed plugin already registered the provider (running inside QGIS)")
class LifecycleTest(unittest.TestCase):
    def test_init_gui_registers_and_unload_removes(self):
        iface = StubIface()
        plugin = MinimumBoundingBox.classFactory(iface)
        plugin.initGui()
        try:
            self.assertEqual(len(iface.menu_actions), 1)
            self.assertIsNotNone(registry().providerById(PROVIDER_ID))
            alg = registry().createAlgorithmById(ALGORITHM_ID)
            self.assertIsNotNone(alg)
            _, ok = alg.run({"INPUT": sample_layer(), "GEOMETRY_TYPE": 1,
                             "OUTPUT": "TEMPORARY_OUTPUT"},
                            QgsProcessingContext(), QgsProcessingFeedback())
            self.assertTrue(ok)

            # The path the dialog uses: processing.run + progress dialog
            layer = plugin.run_algorithm({
                "INPUT": sample_layer(), "GEOMETRY_TYPE": 2, "GROUP_FIELD": "grp",
                "FIELDS": ["name"], "ADD_MEASUREMENTS": True, "OUTPUT": "memory:"})
            self.assertEqual(layer.featureCount(), 2)
            self.assertIn("fill_ratio", layer.fields().names())
        finally:
            plugin.unload()
        self.assertEqual(iface.menu_actions, [])
        self.assertEqual(iface.toolbar_actions, [])
        self.assertIsNone(registry().providerById(PROVIDER_ID))


if __name__ == "__main__":
    unittest.main()
