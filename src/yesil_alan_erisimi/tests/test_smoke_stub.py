# -*- coding: utf-8 -*-
"""
Smoke test verifying imports, threshold parsing, target facility blue point symbology,
100% English defaults, and 5-language report generation in EPSG:5253.
"""
import importlib
import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
PKG = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_QGS_APP = None


def setUpModule():
    global _QGS_APP
    if QgsApplication.instance() is None:
        _QGS_APP = QgsApplication([], False)
        _QGS_APP.initQgis()


class TestSmoke(unittest.TestCase):
    def test_imports(self):
        for mod in (
            "compat",
            "i18n",
            "network",
            "report",
            "outputs",
            "analysis_task",
            "gui_dialog",
            "green_access_plugin",
        ):
            importlib.import_module(f"{PKG}.{mod}")

    def test_parse_thresholds(self):
        g = importlib.import_module(f"{PKG}.gui_dialog")
        self.assertEqual(g.parse_thresholds("500"), [500.0])
        self.assertEqual(g.parse_thresholds("1000, 300;500 m"), [300.0, 500.0, 1000.0])
        self.assertEqual(g.parse_thresholds("1.000, 2.500"), [1000.0, 2500.0])
        self.assertEqual(g.parse_thresholds("0.5, 250"), [0.5, 250.0])
        with self.assertRaises(ValueError):
            g.parse_thresholds("abc")
        with self.assertRaises(ValueError):
            g.parse_thresholds("1,2,3,4,5,6,7,8,9,10,11,12")

    def test_report_and_labels_multilingual(self):
        net = importlib.import_module(f"{PKG}.network")
        rep = importlib.import_module(f"{PKG}.report")
        out = importlib.import_module(f"{PKG}.outputs")

        roads = [(i, [(0, i * 100), (400, i * 100)]) for i in range(5)] + [
            (10 + i, [(i * 100, 0), (i * 100, 400)]) for i in range(5)
        ]
        params = {
            "thresholds": [200, 500],
            "gap_tol": 15,
            "node_crossings": True,
            "use_weight": True,
            "weight_label": "population",
            "max_snap": 100,
        }
        res = net.analyze(
            roads,
            [{"id": 1, "centroid": (0, 0), "ring": [], "area_m2": 25000.0}],
            [(1, 100, 100, 3.0), (2, 400, 400, 7.0)],
            params,
        )

        # English Report (default)
        html_en = rep.build_report_html(res, params, 1.23, "EPSG:5253 Standard", lang="en")
        self.assertIn("Reached Blocks/Bldgs", html_en)
        self.assertIn("Zero Hallucination Standard", html_en)
        self.assertIn("10.1287/opre.12.3.450", html_en)

        # Turkish Report
        html_tr = rep.build_report_html(res, params, 1.23, "EPSG:5253 Standardı", lang="tr")
        self.assertIn("Erişen Ada/Bina", html_tr)
        self.assertIn("%", html_tr)

        # Chinese Report
        html_zh = rep.build_report_html(res, params, 1.23, "EPSG:5253", lang="zh")
        self.assertIn("可达街区/建筑", html_zh)

        # Spanish Report
        html_es = rep.build_report_html(res, params, 1.23, "EPSG:5253", lang="es")
        self.assertIn("Manzanas/Edif. Alcanzados", html_es)

        # Indonesian Report
        html_id = rep.build_report_html(res, params, 1.23, "EPSG:5253", lang="id")
        self.assertIn("Blok/Bangunan Terjangkau", html_id)

        # Formatting
        self.assertEqual(rep.fmt_num(12345.678, 1, lang="tr"), "12.345,7")
        self.assertEqual(rep.fmt_num(12345.678, 1, lang="en"), "12,345.7")

        labels_en, none_lbl, _ = out.class_labels([300, 500, 1000], lang="en")
        self.assertEqual(labels_en, ["0–300 m", "300–500 m", "500–1000 m"])
        self.assertIn("Unreached", none_lbl)
        self.assertEqual(len(out.threshold_colors(3)), 3)

    def test_blue_target_facility_symbol_and_english_gui(self):
        out = importlib.import_module(f"{PKG}.outputs")
        g = importlib.import_module(f"{PKG}.gui_dialog")

        crs = QgsCoordinateReferenceSystem("EPSG:5253")
        proj = QgsProject.instance()
        proj.clear()
        proj.setCrs(crs)

        park_poly = QgsGeometry.fromPolygonXY([[
            QgsPointXY(500000, 4250000),
            QgsPointXY(500050, 4250000),
            QgsPointXY(500050, 4250050),
            QgsPointXY(500000, 4250050),
            QgsPointXY(500000, 4250000),
        ]])
        result = {
            "thresholds": [250.0, 500.0],
            "buildings": [(1, 500100.0, 4250000.0, 10.0, 120.0, 1, 4.0)],
            "bldg_geoms": {},
            "service": {},
            "polygons": {},
            "circles": {},
            "park_geoms": {1: park_poly},
            "allocations": {
                1: {"area_m2": 2500.0, "buildings": 1, "weight": 10.0, "mean_dist": 120.0}
            },
            "building_connectors": [],
            "bridges": [],
            "access_points": [(1, 500025.0, 4250000.0, 0.0)],
            "stats": {"speed_mps": 1.333},
        }
        created = out.build_layers(
            result,
            {"generate_polygons": False, "generate_circles": False, "add_debug": True},
            crs,
            proj,
            "Test Accessibility Group",
            lang="en",
        )
        # First layer at the top of the group must be the Target Facility Blue Point layer
        self.assertEqual(created[0], "Target Facility Allocation Summary")
        pt_layers = proj.mapLayersByName("Target Facility Allocation Summary")
        self.assertEqual(len(pt_layers), 1)
        sym = pt_layers[0].renderer().symbol()
        self.assertEqual(sym.color().name().lower(), "#2563eb")
        self.assertGreaterEqual(sym.size(), 5.0)
        proj.clear()

        # Verify default GUI startup language is English ("en")
        dlg = g.GreenAccessDockWidget(None)
        self.assertEqual(dlg._current_lang, "en")
        self.assertEqual(dlg.windowTitle(), "Accessibility Analysis")
        dlg.close()

        # Verify metadata.txt passes strict QGIS ConfigParser interpolation check
        import configparser
        cp = configparser.ConfigParser()
        meta_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "metadata.txt")
        cp.read(meta_path, encoding="utf-8")
        for sec in cp.sections():
            for _k, _v in cp.items(sec):
                pass
        self.assertEqual(cp.get("general", "name"), "Accessibility Analysis")
        self.assertEqual(cp.get("general", "supportsQt6"), "True")


if __name__ == "__main__":
    unittest.main()
