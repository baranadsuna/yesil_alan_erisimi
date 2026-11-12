# -*- coding: utf-8 -*-
"""
Smoke test verifying imports, threshold parsing, and multilingual report generation.
"""
import importlib
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
PKG = os.path.basename(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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
        self.assertIn("Reached Buildings", html_en)
        self.assertIn("Zero Hallucination Standard", html_en)
        self.assertIn("10.1287/opre.12.3.450", html_en)

        # Turkish Report
        html_tr = rep.build_report_html(res, params, 1.23, "EPSG:5253 Standardı", lang="tr")
        self.assertIn("Erişen Bina", html_tr)
        self.assertIn("%", html_tr)

        # Chinese Report
        html_zh = rep.build_report_html(res, params, 1.23, "EPSG:5253", lang="zh")
        self.assertIn("可达建筑", html_zh)

        # Spanish Report
        html_es = rep.build_report_html(res, params, 1.23, "EPSG:5253", lang="es")
        self.assertIn("Edificios Alcanzados", html_es)

        # Indonesian Report
        html_id = rep.build_report_html(res, params, 1.23, "EPSG:5253", lang="id")
        self.assertIn("Bangunan Terjangkau", html_id)

        # Formatting
        self.assertEqual(rep.fmt_num(12345.678, 1, lang="tr"), "12.345,7")
        self.assertEqual(rep.fmt_num(12345.678, 1, lang="en"), "12,345.7")

        labels_en, none_lbl, _ = out.class_labels([300, 500, 1000], lang="en")
        self.assertEqual(labels_en, ["0–300 m", "300–500 m", "500–1000 m"])
        self.assertIn("Unreached", none_lbl)
        self.assertEqual(len(out.threshold_colors(3)), 3)


if __name__ == "__main__":
    unittest.main()
