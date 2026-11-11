"""Run the test suite inside a running QGIS (3.40+ or 4.x).

In the QGIS Python Console:
    import runpy; runpy.run_path(r"<path to repo>\tests\run_in_qgis.py")

Tests use their own in-memory layers and never touch your open project.
"""
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PREFIXES = ("MinimumBoundingBox", "tests")


def _ours(name):
    return any(name == p or name.startswith(p + ".") for p in PREFIXES)


def main():
    # Make sure we test this checkout, not an installed copy of the plugin.
    saved = {k: v for k, v in sys.modules.items() if _ours(k)}
    for k in saved:
        del sys.modules[k]
    sys.path.insert(0, str(REPO))
    try:
        suite = unittest.defaultTestLoader.discover(
            str(REPO / "tests"), top_level_dir=str(REPO))
        return unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
    finally:
        sys.path.remove(str(REPO))
        for k in [k for k in sys.modules if _ours(k)]:
            del sys.modules[k]
        sys.modules.update(saved)


result = main()
print("\nALL TESTS PASSED" if result.wasSuccessful() else
      f"\nFAILURES: {len(result.failures)}  ERRORS: {len(result.errors)}")
